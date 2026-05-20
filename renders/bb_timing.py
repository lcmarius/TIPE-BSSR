"""Temps de Branch-and-Bound vs n (slide 8).

Compare le coût en temps d'un B&B exhaustif (avec prune capacitaire + LB
min-edge) à celui d'une heuristique gloutonne `method1`, sur des instances
synthétiques croissantes. Met en évidence l'explosion combinatoire qui
motive le passage aux heuristiques en Partie III.

Sortie : `renders/bb_timing.png` + cache JSON `renders/bb_timing_data.json`.

Usage :
    python -m renders.bb_timing                  # calcule + rend
    python -m renders.bb_timing --from-cache     # rend depuis cache
"""

import argparse
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

from dataclasses import dataclass

from src.objects.station import Station, TargetedStation
from renders._presstyle import apply_style, palette as P, figsize, save_pres


# Dépendances inline — on n'importe NI matplotlib (renders.render_sweep le pull
# au top-level) NI osmnx/networkx (src.solver.map les pull). Les workers Modal
# n'embarquent que la stdlib + src.objects.
@dataclass
class GeoPoint:
    latitude: float
    longitude: float


class SyntheticMap:
    def __init__(self, speed_kmh: float = 20.0):
        self._m_per_s = speed_kmh * 1000 / 3600

    def get_time(self, fr, to) -> float:
        dx = (fr.longitude - to.longitude) * 1000.0
        dy = (fr.latitude  - to.latitude)  * 1000.0
        return math.hypot(dx, dy) / self._m_per_s


N_VALUES        = [4, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20]
INSTANCES_PER_N = 20
SEED            = 2026
CAPACITY        = 25
TRUCK_CAPACITY  = 30
BUDGET_S        = 180.0    # 3 min par instance
NODE_BUDGET     = 10**12   # de fait illimite — seul le temps borne

OUT_NAME  = "bb_timing"                       # → pres/fig/bb_timing.pdf
OUT_CACHE = Path("renders/bb_timing_data.json")

COL_BB   = P.deficit       # rouge : courbe d'explosion B&B
COL_TO   = P.deficit_dark  # rouge foncé : marqueurs timeout
TEXT     = P.tdark
sys.setrecursionlimit(50_000)


# ============================================================================
# Generateur d'instances : garantit n stations toutes a gap != 0
# (sinon `n` affiche est trompeur — la difficulte depend du n effectif).
# ============================================================================

def _nonzero_balanced_gaps(n: int, capacity: int, rdm: random.Random) -> list[int]:
    """n gaps dans [-cap/2, -1] U [1, cap/2] sommant a 0 (sans aucun zero)."""
    max_gap = capacity // 2
    for _ in range(200):
        gaps = [rdm.choice([-1, 1]) * rdm.randint(1, max_gap) for _ in range(n)]
        for _adj in range(300):
            s = sum(gaps)
            if s == 0:
                return gaps
            delta = -1 if s > 0 else 1
            order = list(range(n))
            rdm.shuffle(order)
            for i in order:
                new = gaps[i] + delta
                if new == 0 or abs(new) > max_gap:
                    continue
                gaps[i] = new
                break
            else:
                break
    raise RuntimeError(f"impossible de generer {n} gaps non nuls sommant a 0")


def generate_clean_instance(n: int, capacity: int, seed: int,
                            side_km: float = 5.0
                            ) -> tuple[list[TargetedStation], Station]:
    """n stations uniformes dans un carre + depot au centre, tous gaps != 0."""
    rdm   = random.Random(seed)
    half  = side_km / 2.0
    depot = Station(0, "depot", 0, "", 0.0, 0.0)
    gaps  = _nonzero_balanced_gaps(n, capacity, rdm)
    stations: list[TargetedStation] = []
    for i in range(n):
        x = rdm.uniform(-half, half)
        y = rdm.uniform(-half, half)
        target = capacity // 2
        count  = max(0, min(capacity, target + gaps[i]))
        target = count - gaps[i]
        if not (0 <= target <= capacity):
            target = max(0, min(capacity, target))
            count  = target + gaps[i]
        s = Station(i + 1, f"S{i+1}", capacity, "", x, y)
        stations.append(TargetedStation.from_station(s, count, target))
    return stations, depot


# ============================================================================
# Branch-and-Bound exhaustif (TSP + capacite BSSR)
# ============================================================================

def build_dist(stations, depot):
    """Retourne la matrice n*n (0 = depot, 1..n = stations) et la liste des gaps."""
    sm   = SyntheticMap()
    pts  = [depot] + stations
    n    = len(pts)
    # SyntheticMap consomme des GeoPoint (latitude/longitude), pas des Station
    geos = [GeoPoint(p.lat, p.long) for p in pts]
    d    = [[0.0] * n for _ in range(n)]
    for i, a in enumerate(geos):
        for j, b in enumerate(geos):
            if i != j:
                d[i][j] = sm.get_time(a, b)
    gaps = [0] + [s.bike_gap() for s in stations]
    return d, gaps


def bnb_solve(d: list[list[float]], gaps: list[int], capacity: int,
              budget_s: float = BUDGET_S, node_budget: int = NODE_BUDGET
              ) -> tuple[float, float, bool, int]:
    """B&B DFS avec pruning min-edge + faisabilite capacitaire.

    Retourne (best_cost, elapsed_s, timed_out, n_nodes).
    """
    n = len(d)
    # min outgoing edge par sommet — sert au lower bound
    min_out = [min(d[i][j] for j in range(n) if j != i) for i in range(n)]

    best_ref = [math.inf]
    nodes    = [0]
    flag_to  = [False]
    start    = time.perf_counter()

    def dfs(cur: int, load: int, cost: float, visited: int) -> None:
        if flag_to[0]:
            return
        nodes[0] += 1
        # Vérification du budget toutes les ~1e5 expansions
        if nodes[0] & 0xFFFF == 0:
            if time.perf_counter() - start > budget_s:
                flag_to[0] = True
                return
            if nodes[0] > node_budget:
                flag_to[0] = True
                return

        full_mask = (1 << n) - 1
        if visited == full_mask:
            total = cost + d[cur][0]
            if total < best_ref[0]:
                best_ref[0] = total
            return

        # Lower bound : coût accumulé + somme des min_out pour chaque sommet
        # non visité + min_out depot (retour).
        lb = cost
        m  = visited ^ full_mask        # bits des non visites
        while m:
            k  = (m & -m).bit_length() - 1
            lb += min_out[k]
            m &= m - 1
        lb += min_out[0]
        if lb >= best_ref[0]:
            return

        # Branche par voisin le plus proche d'abord pour trouver vite une bonne UB
        cands = []
        for k in range(1, n):
            if not (visited >> k) & 1:
                new_load = load + gaps[k]
                if 0 <= new_load <= capacity:
                    cands.append((d[cur][k], k, new_load))
        cands.sort()
        for dk, k, new_load in cands:
            if cost + dk >= best_ref[0]:
                break
            dfs(k, new_load, cost + dk, visited | (1 << k))

    dfs(0, 0, 0.0, 1)
    return best_ref[0], time.perf_counter() - start, flag_to[0], nodes[0]


# ============================================================================
# Sweep
# ============================================================================

def run_sweep() -> dict:
    """Sweep séquentiel local — pour Modal voir bb_timing_modal.py."""
    rows = []
    for n in N_VALUES:
        bb_times, bb_to_count = [], 0
        for k in range(INSTANCES_PER_N):
            seed = SEED + 1000 * n + k
            stations, depot = generate_clean_instance(n, CAPACITY, seed)
            d, gaps = build_dist(stations, depot)
            cost, t_bb, to, nodes = bnb_solve(d, gaps, TRUCK_CAPACITY)
            if not to:
                bb_times.append(t_bb)
            else:
                bb_to_count += 1
            print(f"  n={n:3d} inst {k+1}/{INSTANCES_PER_N} : "
                  f"B&B {t_bb:7.3f}s {'(TO)' if to else '    '} "
                  f"nodes={nodes:>10d}")
        row = _row_from_clean(n, bb_times, bb_to_count, INSTANCES_PER_N)
        rows.append(row)
        if row["bb_median"] is not None:
            print(f"  n={n:3d} : médiane={row['bb_median']:.3f}s  "
                  f"({row['n_clean']}/{INSTANCES_PER_N} finies)")
        else:
            print(f"  n={n:3d} : TOUS TO ({INSTANCES_PER_N})")
    return {"rows": rows, "instances_per_n": INSTANCES_PER_N, "budget_s": BUDGET_S}


def _row_from_clean(n: int, clean_times: list[float], n_to: int,
                    n_total: int) -> dict:
    """Construit la ligne d'agregation par n : stats sur les instances finies."""
    if clean_times:
        return {
            "n":         n,
            "n_total":   n_total,
            "n_clean":   len(clean_times),
            "bb_to":     n_to,
            "bb_median": statistics.median(clean_times),
            "bb_mean":   statistics.fmean(clean_times),
            "bb_min":    min(clean_times),
            "bb_max":    max(clean_times),
        }
    return {
        "n":         n,
        "n_total":   n_total,
        "n_clean":   0,
        "bb_to":     n_to,
        "bb_median": None,
        "bb_mean":   None,
        "bb_min":    None,
        "bb_max":    None,
    }


# ============================================================================
# Rendu
# ============================================================================

def _fmt_dur(s: float) -> str:
    """Formatage humain d'une durée en secondes."""
    if s < 60:           return f"{s:.1f} s"
    if s < 3600:         return f"{s/60:.1f} min"
    if s < 86400:        return f"{s/3600:.1f} h"
    if s < 86400 * 365:  return f"{s/86400:.1f} j"
    return f"{s/86400/365:.1f} ans"


def render(data: dict) -> None:
    import matplotlib.pyplot as plt  # lazy : pas requis par les workers

    apply_style()

    rows_clean = [r for r in data["rows"]
                  if r.get("n_clean", 0) >= max(1, r.get("n_total", 1) // 2)
                  and r.get("bb_median") is not None]
    ns      = [r["n"]         for r in rows_clean]
    bb_med  = [r["bb_median"] for r in rows_clean]
    bb_min  = [r["bb_min"]    for r in rows_clean]
    bb_max  = [r["bb_max"]    for r in rows_clean]

    fig, ax = plt.subplots(figsize=figsize("std"))

    ax.fill_between(ns, bb_min, bb_max, color=COL_BB, alpha=0.18, linewidth=0,
                    zorder=2)
    ax.plot(ns, bb_med, color=COL_BB, lw=2.0, marker="o", ms=5,
            label="Branch-and-Bound (mesuré, médiane)", zorder=4)

    # ────────────────────────────────────────────────────────────────────
    # Fit exponentiel sur les points "propres" (aucun timeout) :
    #   log(t) ≈ a·n + b   ⇒   t ≈ exp(b) · exp(a)^n
    # On extrapole en pointille de la derniere mesure jusqu'a n_target.
    # ────────────────────────────────────────────────────────────────────
    fit_pts  = [(r["n"], r["bb_median"]) for r in rows_clean
                if r["bb_median"] > 0]
    if len(fit_pts) >= 3:
        log_ts = [math.log(t) for _, t in fit_pts]
        xs     = [n for n, _ in fit_pts]
        mean_n = statistics.fmean(xs)
        mean_y = statistics.fmean(log_ts)
        num = sum((x - mean_n) * (y - mean_y) for x, y in zip(xs, log_ts))
        den = sum((x - mean_n) ** 2 for x in xs)
        slope     = num / den
        intercept = mean_y - slope * mean_n
        factor    = math.exp(slope)

        n_last_clean = xs[-1]
        n_target     = 30
        ext_ns       = list(range(n_last_clean, n_target + 1))
        ext_ys       = [math.exp(intercept + slope * n) for n in ext_ns]
        ax.plot(ext_ns, ext_ys, color=COL_TO, lw=1.6, ls="--", alpha=0.85,
                zorder=3,
                label="extrapolation")

        # Label sous l'extrémité de la courbe extrapolée (pas dessus) — évite
        # la superposition avec la pointe et la légende "extrapolation".
        ax.annotate(f"≈ {_fmt_dur(ext_ys[-1])}\nà n=30",
                    xy=(ext_ns[-1], ext_ys[-1]),
                    xytext=(0, -28), textcoords="offset points",
                    fontsize=9.5, color=COL_BB, fontweight="bold",
                    ha="center", va="top")

    ax.set_yscale("log")
    ax.set_xlabel("Nombre de stations  n")
    ax.set_ylabel("Temps de résolution (échelle log)")
    ax.set_xticks(list(range(4, 31, 2)))
    ax.set_xlim(3.5, 30.5)
    ax.grid(True, alpha=0.5, which="both")

    ax.legend(loc="upper left", fontsize=8.5)

    fig.tight_layout()
    save_pres(fig, OUT_NAME)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--from-cache", action="store_true",
                   help="rend depuis le cache JSON sans recalculer")
    args = p.parse_args()

    if args.from_cache and OUT_CACHE.exists():
        with open(OUT_CACHE) as f:
            data = json.load(f)
        print(f"lu : {OUT_CACHE}")
    else:
        data = run_sweep()
        with open(OUT_CACHE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"cache écrit : {OUT_CACHE}")

    render(data)


if __name__ == "__main__":
    main()
