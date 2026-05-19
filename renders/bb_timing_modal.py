"""Sweep B&B vs n distribué sur Modal.com (slide 8).

Architecture : 1 conteneur Modal (16 vCPU), multiprocessing interne pour
paralléliser les (n, instance_idx) tasks sur les workers. Le rendu se
fait localement à partir du JSON rapatrié.

Setup (une fois) :
    pip install modal
    modal token new

Lancement (~2 min) :
    modal run renders/bb_timing_modal.py

Rendu seul depuis cache local :
    python -m renders.bb_timing_modal --from-cache
"""

import argparse
import json
import os
import statistics
from pathlib import Path

import modal


APP_NAME    = "bicloo-bb-timing"
RENDER_OUT  = "renders/bb_timing.png"
CACHE_LOCAL = "renders/bb_timing_data.json"

# Paramètres du sweep — alignés avec bb_timing.py local
N_VALUES        = [4, 6, 8, 10, 12, 13, 14, 15, 16, 17, 18, 19, 20]
INSTANCES_PER_N = 20
SEED            = 2026
CAPACITY        = 25
TRUCK_CAPACITY  = 30
BUDGET_S        = 180.0    # 3 min par instance
N_WORKERS       = 32       # vCPUs (max non-enterprise)


app = modal.App(APP_NAME)

image = (
    modal.Image.debian_slim(python_version="3.12")
    # On n'a besoin de rien pour les workers (B&B = stdlib pur). Pas de
    # matplotlib/osmnx ici : le rendu se fait localement.
    .add_local_dir("src",     "/app/src",     copy=True,
                   ignore=["__pycache__/**"])
    .add_local_dir("renders", "/app/renders", copy=True,
                   ignore=["*.png", "*.pdf", "*.pkl", "*.json",
                           "sweep/**", "simulate/**", "__pycache__/**"])
    .workdir("/app")
)


# ────────────────────────────────────────────────────────────────────────────
# Worker module-level (picklable par Pool.map)
# ────────────────────────────────────────────────────────────────────────────

def _solve_one(task: dict) -> dict:
    """Résout une instance synthétique (n, k) avec B&B + budget temps."""
    import sys
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")
    from renders.bb_timing import (
        generate_clean_instance, build_dist, bnb_solve,
    )
    n    = task["n"]
    k    = task["k"]
    seed = SEED + 1000 * n + k
    stations, depot = generate_clean_instance(n, CAPACITY, seed)
    d, gaps         = build_dist(stations, depot)
    cost, t, to, nodes = bnb_solve(d, gaps, TRUCK_CAPACITY, budget_s=BUDGET_S)
    print(f"  n={n:2d} k={k:2d} : {t:7.2f}s {'(TO)' if to else '    '} "
          f"nodes={nodes:>10d}", flush=True)
    return {"n": n, "k": k, "cost": cost, "time": t,
            "timed_out": to, "nodes": nodes}


@app.function(
    image   = image,
    cpu     = N_WORKERS,
    memory  = 16384,
    timeout = 7200,
)
def run_sweep_remote() -> list[dict]:
    """Lance toutes les tasks sur 1 conteneur, Pool multiprocessing interne."""
    import sys
    import time
    from datetime import datetime
    from multiprocessing import Pool, cpu_count

    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    tasks = [{"n": n, "k": k}
             for n in N_VALUES
             for k in range(INSTANCES_PER_N)]
    nw = min(N_WORKERS, cpu_count())
    print(f"[{datetime.now():%H:%M:%S}] {len(tasks)} tâches sur {nw} workers "
          f"(CPU dispo : {cpu_count()})")
    start = time.perf_counter()
    with Pool(nw) as pool:
        results = pool.map(_solve_one, tasks)
    elapsed = time.perf_counter() - start
    print(f"[{datetime.now():%H:%M:%S}] Sweep fini en {elapsed:.1f}s "
          f"(speedup théorique {len(tasks) * BUDGET_S / elapsed:.1f}×)")
    return results


# ────────────────────────────────────────────────────────────────────────────
# Agrégation : (n, k) → moyennes / min / max / timeouts par n
# ────────────────────────────────────────────────────────────────────────────

def aggregate(results: list[dict]) -> dict:
    """Agrege par n en gardant les statistiques sur les instances finies seules.
    La mediane sur instances finies est plus parlante que la moyenne quand
    quelques TO sont presents."""
    from renders.bb_timing import _row_from_clean

    by_n: dict[int, list[dict]] = {}
    for r in results:
        by_n.setdefault(r["n"], []).append(r)
    rows = []
    for n in sorted(by_n):
        rs = by_n[n]
        clean_times = [r["time"] for r in rs if not r["timed_out"]]
        n_to        = sum(int(r["timed_out"]) for r in rs)
        rows.append(_row_from_clean(n, clean_times, n_to, len(rs)))
    return {"rows": rows,
            "instances_per_n": INSTANCES_PER_N,
            "budget_s":        BUDGET_S}


# ────────────────────────────────────────────────────────────────────────────
# Entrypoint local Modal
# ────────────────────────────────────────────────────────────────────────────

@app.local_entrypoint()
def main():
    print("Lancement du sweep B&B sur Modal...")
    raw  = run_sweep_remote.remote()
    data = aggregate(raw)
    with open(CACHE_LOCAL, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Cache écrit : {CACHE_LOCAL}")
    # Rendu local
    from renders.bb_timing import render
    render(data)


# ────────────────────────────────────────────────────────────────────────────
# CLI standalone (--from-cache) : rejoue le rendu sans toucher à Modal
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--from-cache", action="store_true",
                   help=f"Rejoue le rendu depuis {CACHE_LOCAL}")
    args = p.parse_args()
    if not args.from_cache:
        raise SystemExit(
            "Pour lancer le sweep : modal run renders/bb_timing_modal.py\n"
            "Pour rejouer le rendu seul : --from-cache"
        )
    if not os.path.exists(CACHE_LOCAL):
        raise SystemExit(f"Cache introuvable : {CACHE_LOCAL}")
    with open(CACHE_LOCAL) as f:
        data = json.load(f)
    from renders.bb_timing import render
    render(data)
