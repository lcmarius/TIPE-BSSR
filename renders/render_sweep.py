"""Courbe rapport d'approximation vs taille du problème (sweep en n).

Produit `ratio_vs_n.png` : une courbe par algorithme, abscisse = n stations,
ordonnée = ratio moyen `temps / borne_inf` calculé sur K instances aléatoires
de même taille.

Usage :
    python -m renders.render_sweep                     # calcule + rend
    python -m renders.render_sweep --from-cache        # rend depuis cache
    python -m renders.render_sweep --n-values 5 10 30 80 120 --instances 20
"""

import argparse
import json
import math
import os
import random
import statistics
from datetime import datetime

import matplotlib.pyplot as plt

from renders._presstyle import apply_style, palette as P, figsize as fsize, save_pres
from src.objects.station import Station, TargetedStation
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.builder.method2 import method2
from src.solver.algorithm.incrementer.ils import ils
from src.solver.algorithm.incrementer.opt2 import opt2
from src.solver.algorithm.incrementer.or_opt import or_opt
from src.solver.graph import SolvingStationGraph
from src.solver.reviewer import review_solution


DEFAULT_N_VALUES  = [2, 5, 10, 15, 20, 30, 40, 60, 80, 100, 120]
DEFAULT_INSTANCES = 15
DEFAULT_SEED      = 2026
DEFAULT_OUT       = "renders/sweep"
CAPACITY          = 25
TRUCK_CAPACITY    = 30
ILS_MAX_ITER      = 20


# ============================================================================
# Génération d'instances synthétiques (carré euclidien + vitesse constante)
# ============================================================================

class SyntheticMap:
    """Duck-type compatible avec `src.solver.map.Map`.

    Coordonnées (lat, long) interprétées comme planes en km autour de (0, 0)
    — à 5 km on perd <0.01 % par rapport à Haversine, sans intérêt pour un
    benchmark où seul le ratio sol/LB compte.
    """
    def __init__(self, speed_kmh: float = 20.0):
        self._m_per_s = speed_kmh * 1000 / 3600
        self.graph = None
        self._node_cache: dict = {}

    def get_time(self, fr, to) -> float:
        dx = (fr.longitude - to.longitude) * 1000.0
        dy = (fr.latitude  - to.latitude)  * 1000.0
        return math.hypot(dx, dy) / self._m_per_s


def _balanced_gaps(n: int, capacity: int, rdm: random.Random) -> list[int]:
    """n gaps entiers dans [-capacity/2, capacity/2] sommant à 0."""
    max_gap = capacity // 2
    gaps = [rdm.randint(-max_gap, max_gap) for _ in range(n)]
    safety = 100 * n
    while sum(gaps) != 0 and safety > 0:
        delta = -1 if sum(gaps) > 0 else 1
        for i in rdm.sample(range(n), n):
            if abs(gaps[i] + delta) <= max_gap:
                gaps[i] += delta
                break
        else:
            break
        safety -= 1
    if sum(gaps) != 0:
        gaps[0] -= sum(gaps)
    return gaps


def generate_instance(n: int, capacity: int, seed: int,
                      side_km: float = 5.0) -> tuple[list[TargetedStation], Station, TargetedStation]:
    """n stations uniformes dans un carré + dépôt au centre, gaps équilibrés."""
    rdm = random.Random(seed)
    half = side_km / 2.0
    depot = Station(0, "depot", 0, "", 0.0, 0.0)
    depot_t = TargetedStation.from_station(depot, 0, 0)
    gaps = _balanced_gaps(n, capacity, rdm)
    targeted: list[TargetedStation] = []
    for i in range(n):
        x = rdm.uniform(-half, half)
        y = rdm.uniform(-half, half)
        gap = gaps[i]
        target = capacity // 2
        count = max(0, min(capacity, target + gap))
        target = count - gap
        if not (0 <= target <= capacity):
            target = max(0, min(capacity, target))
            count = target + gap
        s = Station(i + 1, f"S{i+1}", capacity, "", x, y)
        targeted.append(TargetedStation.from_station(s, count, target))
    return targeted, depot, depot_t


def _run_all_configs_on_instance(targeted, depot, depot_targeted,
                                  truck: int, configs):
    """Renvoie {name: ratio} ; None par config en cas d'échec."""
    synth_map = SyntheticMap()
    shared_cache: dict | None = None
    out: dict[str, float | None] = {}
    for name, builder_fn, improvers in configs:
        g = SolvingStationGraph(synth_map, depot)
        g.station_map[0] = depot_targeted
        for t in targeted:
            if t.bike_gap() != 0:
                g.add_station(t)
        if shared_cache is not None:
            g.time_cache = shared_cache
        g.preload_times()
        try:
            builder_fn(g, truck)
            for imp in improvers:
                imp(g, truck)
            metrics = review_solution(g, truck)
            out[name] = metrics.ratio
        except Exception:
            out[name] = None
        shared_cache = g.time_cache
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--n-values",  type=int, nargs="+", default=DEFAULT_N_VALUES,
                   help="Tailles de problème à balayer (ex : --n-values 5 20 60 120)")
    p.add_argument("--instances", type=int, default=DEFAULT_INSTANCES,
                   help="Nombre d'instances aléatoires par valeur de n")
    p.add_argument("--capacity",  type=int, default=CAPACITY,
                   help="Capacité par station")
    p.add_argument("--truck",     type=int, default=TRUCK_CAPACITY,
                   help="Capacité du camion")
    p.add_argument("--seed",      type=int, default=DEFAULT_SEED)
    p.add_argument("--out-dir",   default=DEFAULT_OUT)
    p.add_argument("--from-cache", action="store_true",
                   help="Réutilise sweep_data.json présent dans --out-dir (saute le calcul)")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    cache_path = os.path.join(args.out_dir, "sweep_data.json")

    def imp_opt2 (g, c): opt2  (g, c, max_iterations=500)
    def imp_oropt(g, c): or_opt(g, c, max_iterations=500)
    def imp_ils  (g, c): ils   (g, c, max_iterations=ILS_MAX_ITER)

    configs = [
        ("method1 seul",             method1, []),
        ("method1 + OPT_2",          method1, [imp_opt2]),
        ("method1 + OR_OPT",         method1, [imp_oropt]),
        ("method1 + OPT_2 + OR_OPT", method1, [imp_opt2, imp_oropt]),
        ("method1 + ILS",            method1, [imp_ils]),
        ("method2 seul",             method2, []),
        ("method2 + OPT_2",          method2, [imp_opt2]),
        ("method2 + OR_OPT",         method2, [imp_oropt]),
        ("method2 + OPT_2 + OR_OPT", method2, [imp_opt2, imp_oropt]),
        ("method2 + ILS",            method2, [imp_ils]),
    ]
    config_names = [c[0] for c in configs]

    # mean_ratios[name][i_n] = ratio moyen sur les instances de taille n_values[i_n]
    # stdev_ratios pareil. Indéfini → None.
    mean_ratios:  dict[str, list[float | None]] = {n: [] for n in config_names}
    stdev_ratios: dict[str, list[float]]        = {n: [] for n in config_names}

    if args.from_cache and os.path.exists(cache_path):
        print(f"[{datetime.now():%H:%M:%S}] Chargement cache {cache_path}")
        with open(cache_path) as f:
            cached = json.load(f)
        args.n_values = cached["n_values"]
        mean_ratios   = cached["mean_ratios"]
        stdev_ratios  = cached["stdev_ratios"]
        if "instances" in cached:
            args.instances = cached["instances"]
        # Continue directement au rendu : on saute la boucle de calcul.
        _render_only(args, mean_ratios, stdev_ratios, config_names)
        return

    print(f"[{datetime.now():%H:%M:%S}] Sweep n ∈ {args.n_values}  ·  "
          f"{args.instances} instances/n  ·  {len(configs)} configs")

    for n in args.n_values:
        print(f"[{datetime.now():%H:%M:%S}] n = {n:3d}  ({args.instances} instances)")
        ratios_for_n: dict[str, list[float]] = {name: [] for name in config_names}
        n_active_min = n
        for i in range(args.instances):
            seed = args.seed + i + 1000 * n  # décale entre n pour décorréler
            try:
                targeted, depot, depot_targeted = generate_instance(
                    n, args.capacity, seed)
            except Exception as exc:
                print(f"  instance {i+1}/{args.instances}  ÉCHEC génération ({exc})")
                continue
            n_active = sum(1 for t in targeted if t.bike_gap() != 0)
            n_active_min = min(n_active_min, n_active)
            results = _run_all_configs_on_instance(
                targeted, depot, depot_targeted, args.truck, configs)
            for name, r in results.items():
                if r is not None:
                    ratios_for_n[name].append(r)

        # Synthèse pour ce n.
        print(f"  actifs : ≥ {n_active_min}/{n} stations")
        for name in config_names:
            rs = ratios_for_n[name]
            if rs:
                m = statistics.fmean(rs)
                s = statistics.pstdev(rs) if len(rs) > 1 else 0.0
            else:
                m, s = None, 0.0
            mean_ratios[name].append(m)
            stdev_ratios[name].append(s)
            if m is not None:
                print(f"    {name:30s}  mean={m:.3f}×  σ={s:.3f}  (n_succ={len(rs)})")
            else:
                print(f"    {name:30s}  ÉCHEC total")

    # Sauvegarde des données calculées en JSON pour ré-itération rapide
    # du rendu (--from-cache lit ce fichier au lieu de tout recalculer).
    with open(cache_path, "w") as f:
        json.dump({
            "n_values":     args.n_values,
            "config_names": config_names,
            "instances":    args.instances,
            "mean_ratios":  mean_ratios,
            "stdev_ratios": stdev_ratios,
        }, f, indent=2)
    print(f"[{datetime.now():%H:%M:%S}] Cache écrit : {cache_path}")

    _render_only(args, mean_ratios, stdev_ratios, config_names)


# Palette alignée sur pres/main.tex : famille method1 en dégradé bleu (depot),
# famille method2 en dégradé orange (accent). Gradient = amélioration croissante.
LOCAL_COLORS = {
    "method1 seul":             "#7fa8e0",
    "method1 + OPT_2":          P.depot,
    "method1 + OR_OPT":         "#4d7fc3",
    "method1 + OPT_2 + OR_OPT": P.depot_dark,
    "method1 + ILS":            "#0b2a5c",
    "method2 seul":             "#ffb070",
    "method2 + OPT_2":          P.accent,
    "method2 + OR_OPT":         "#ff8a30",
    "method2 + OPT_2 + OR_OPT": P.accent_dark,
    "method2 + ILS":            "#5c2a00",
}


def _setup_axis(ax, x_max, y_min, y_max):
    # Bande verte « optimum » (sous y=1)
    ax.axhspan(y_min, 1.0, facecolor=P.surplus, edgecolor="none",
               alpha=0.10, zorder=0)
    ax.axhline(1.0, color=P.surplus_dark, lw=1.6, alpha=0.9, zorder=1)
    ax.text(x_max * 0.99, (y_min + 1.0) / 2,
            "  optimale  ",
            ha='right', va='center', fontsize=7.5,
            color=P.surplus_dark, style='italic', fontweight='bold')
    ax.set_xlabel("Nombre de stations  n")
    ax.set_xlim(0, x_max * 1.40)   # marge droite étendue pour absorber les labels
    ax.set_ylim(y_min, y_max)
    ax.grid(True, alpha=0.5)


def _plot_family(ax, n_values, mean_ratios, family, band_ratios=None,
                 min_label_gap=None):
    """family : liste de (cfg_name, short_label). ILS = trait épais.

    band_ratios : optionnel, dict {cfg_name: [σ_n]} → fill_between ±σ.
    min_label_gap : écart vertical minimum entre 2 labels de courbes (en
        unités y). Quand des courbes convergent à grand n, leurs labels
        sinon se chevauchent. None = auto (5 % de l'amplitude y).
    """
    # 1ère passe : on collecte les séries valides + leur y_final
    items = []
    for cfg_name, short in family:
        ys_full = mean_ratios.get(cfg_name, [])
        xs       = [n for n, y in zip(n_values, ys_full) if y is not None]
        ys_clean = [y for y in ys_full if y is not None]
        if not ys_clean:
            continue
        items.append({
            'cfg':    cfg_name,
            'short':  short,
            'xs':     xs,
            'ys':     ys_clean,
            'ys_full': ys_full,
            'color':  LOCAL_COLORS.get(cfg_name, "#888"),
            'is_ils': "ILS" in cfg_name,
            'y_final': ys_clean[-1],
        })
    if not items:
        return

    # Dédup vertical des labels : on les empile par y croissant et on force
    # un écart minimum. Sinon 5 courbes convergent → labels stackés.
    # On équilibre autour du barycentre des y_final pour éviter qu'un seul
    # label dégueule en haut quand toutes les courbes sont serrées.
    if min_label_gap is None:
        y_lo, y_hi = ax.get_ylim()
        min_label_gap = 0.07 * (y_hi - y_lo)
    sorted_items = sorted(items, key=lambda d: d['y_final'])

    # Pass 1 : empile vers le haut depuis le plus bas
    ys_up = [sorted_items[0]['y_final']]
    for i in range(1, len(sorted_items)):
        ys_up.append(max(sorted_items[i]['y_final'], ys_up[-1] + min_label_gap))

    # Pass 2 : si on a poussé vers le haut, on recentre le bloc autour de
    # la moyenne des y_final originaux (équilibre haut/bas).
    n = len(sorted_items)
    avg_orig = sum(d['y_final'] for d in sorted_items) / n
    avg_up   = sum(ys_up) / n
    shift = avg_orig - avg_up
    label_ys = [y + shift for y in ys_up]

    # On clampe dans les limites du graphe (sans déborder).
    y_lo, y_hi = ax.get_ylim()
    if label_ys[0] < y_lo + min_label_gap / 2:
        delta = y_lo + min_label_gap / 2 - label_ys[0]
        label_ys = [y + delta for y in label_ys]
    if label_ys[-1] > y_hi - min_label_gap / 2:
        delta = label_ys[-1] - (y_hi - min_label_gap / 2)
        label_ys = [y - delta for y in label_ys]

    label_y_by_cfg = {d['cfg']: y for d, y in zip(sorted_items, label_ys)}

    for d in items:
        xs, ys_clean = d['xs'], d['ys']
        color, is_ils = d['color'], d['is_ils']

        if band_ratios is not None:
            es_full  = band_ratios.get(d['cfg'], [])
            es_clean = [e for y, e in zip(d['ys_full'], es_full) if y is not None]
            if len(es_clean) == len(ys_clean) and es_clean:
                lo = [y - e for y, e in zip(ys_clean, es_clean)]
                hi = [y + e for y, e in zip(ys_clean, es_clean)]
                ax.fill_between(xs, lo, hi, color=color, alpha=0.15,
                                linewidth=0, zorder=2 if is_ils else 1)

        ax.plot(xs, ys_clean,
                marker="o",
                markersize=3.5 if is_ils else 2.6,
                linewidth=1.6 if is_ils else 0.9,
                color=color, zorder=5 if is_ils else 3,
                solid_capstyle='round')
        y_label = label_y_by_cfg[d['cfg']]
        # Si le label a été décalé, on dessine un petit trait gris pointillé
        # entre la fin de la courbe et le label, pour éviter l'ambigüité.
        if abs(y_label - d['y_final']) > 1e-3:
            ax.plot([xs[-1], xs[-1] + (ax.get_xlim()[1] - xs[-1]) * 0.08],
                    [d['y_final'], y_label],
                    color=color, lw=0.6, ls=':', alpha=0.8, zorder=4,
                    clip_on=False)
        ax.annotate(
            d['short'],
            xy=(xs[-1], y_label),
            xytext=(8, 0), textcoords='offset points',
            fontsize=8 if is_ils else 7.5,
            fontweight='bold' if is_ils else 'normal',
            color=color, va='center', ha='left',
            annotation_clip=False,
        )


def _render_two_panel(args, mean_ratios, families, out_name,
                      y_max, y_min=0.90, suptitle=None, band_ratios=None):
    apply_style()
    x_max = max(args.n_values)
    fig, axes = plt.subplots(1, 2, figsize=fsize("double"), sharey=True)
    for ax, (title, family) in zip(axes, families.items()):
        _setup_axis(ax, x_max, y_min, y_max)
        _plot_family(ax, args.n_values, mean_ratios, family, band_ratios)
        ax.set_title(title, fontsize=9.5, fontweight='bold', pad=4)
    axes[0].set_ylabel("Rapport d'approximation")
    if suptitle:
        fig.suptitle(suptitle, fontsize=10.5, fontweight='bold', y=1.02)
    fig.tight_layout()
    # `.pdf` automatique côté save_pres ; on retire .png si présent dans out_name.
    save_pres(fig, out_name.removesuffix(".png"))


def _render_single_panel(args, mean_ratios, family, out_name, title,
                         y_max, y_min=0.90, band_ratios=None):
    apply_style()
    x_max = max(args.n_values)
    fig, ax = plt.subplots(figsize=fsize("std"))
    _setup_axis(ax, x_max, y_min, y_max)
    _plot_family(ax, args.n_values, mean_ratios, family, band_ratios)
    ax.set_title(title, fontsize=10, fontweight='bold', pad=4)
    ax.set_ylabel("Rapport d'approximation")
    fig.tight_layout()
    save_pres(fig, out_name.removesuffix(".png"))


def _render_only(args, mean_ratios, stdev_ratios, config_names):
    """Produit 7 variantes (révélation progressive pour la présentation).

    Les bandes ±σ (`stdev_ratios`) sont superposées sous chaque courbe.
    """
    print(f"[{datetime.now():%H:%M:%S}] Écriture des variantes dans {args.out_dir}/")

    # Y-range global pour échelle cohérente entre toutes les variantes.
    # On élargit pour inclure les bandes ±σ (sinon les hauts de bande sont coupés).
    band = stdev_ratios or {}
    all_tops = []
    for name, ys in mean_ratios.items():
        es = band.get(name, [])
        for j, y in enumerate(ys):
            if y is None:
                continue
            e = es[j] if j < len(es) else 0.0
            all_tops.append(y + e)
    y_max = max(all_tops) * 1.03 if all_tops else 2.2

    bands = stdev_ratios  # ±σ : variabilité inter-instances

    # 1. méthode 1 seule (1 panneau)
    _render_single_panel(args, mean_ratios,
                         [("method1 seul", "méthode 1")],
                         "ratio_m1_only.png",
                         "Constructeur méthode 1 (glouton) — sans amélioration",
                         y_max, band_ratios=bands)

    # 2. méthode 2 seule (1 panneau)
    _render_single_panel(args, mean_ratios,
                         [("method2 seul", "méthode 2")],
                         "ratio_m2_only.png",
                         "Constructeur méthode 2 (insertion) — sans amélioration",
                         y_max, band_ratios=bands)

    # 3. m1 + m2 superposés (1 panneau)
    _render_single_panel(args, mean_ratios,
                         [("method1 seul", "méthode 1"),
                          ("method2 seul", "méthode 2")],
                         "ratio_m1_m2_basic.png",
                         "Comparaison des constructeurs (sans amélioration)",
                         y_max, band_ratios=bands)

    # 4. 2 panneaux, juste base
    _render_two_panel(args, mean_ratios,
                      {
                          "Constructeur méthode 1 (glouton)":    [("method1 seul", "seul")],
                          "Constructeur méthode 2 (insertion)": [("method2 seul", "seul")],
                      },
                      "ratio_2p_basic.png", y_max,
                      suptitle="Constructeurs seuls (sans amélioration)",
                      band_ratios=bands)

    # 5. 2 panneaux + Or-opt
    _render_two_panel(args, mean_ratios,
                      {
                          "Constructeur méthode 1 (glouton)": [
                              ("method1 seul",     "seul"),
                              ("method1 + OR_OPT", "+ Or-opt"),
                          ],
                          "Constructeur méthode 2 (insertion)": [
                              ("method2 seul",     "seul"),
                              ("method2 + OR_OPT", "+ Or-opt"),
                          ],
                      },
                      "ratio_2p_oropt.png", y_max,
                      suptitle="Ajout de l'opérateur Or-opt",
                      band_ratios=bands)

    # 6. 2 panneaux + 2-opt + Or-opt + combiné (sans ILS)
    _render_two_panel(args, mean_ratios,
                      {
                          "Constructeur méthode 1 (glouton)": [
                              ("method1 seul",             "seul"),
                              ("method1 + OPT_2",          "+ 2-opt"),
                              ("method1 + OR_OPT",         "+ Or-opt"),
                              ("method1 + OPT_2 + OR_OPT", "+ 2-opt + Or-opt"),
                          ],
                          "Constructeur méthode 2 (insertion)": [
                              ("method2 seul",             "seul"),
                              ("method2 + OPT_2",          "+ 2-opt"),
                              ("method2 + OR_OPT",         "+ Or-opt"),
                              ("method2 + OPT_2 + OR_OPT", "+ 2-opt + Or-opt"),
                          ],
                      },
                      "ratio_2p_2opt.png", y_max,
                      suptitle="Ajout des opérateurs 2-opt et Or-opt",
                      band_ratios=bands)

    # 7. version complète avec ILS (= ratio_vs_n.png original)
    _render_two_panel(args, mean_ratios,
                      {
                          "Constructeur méthode 1 (glouton)": [
                              ("method1 seul",             "seul"),
                              ("method1 + OPT_2",          "+ 2-opt"),
                              ("method1 + OR_OPT",         "+ Or-opt"),
                              ("method1 + OPT_2 + OR_OPT", "+ 2-opt + Or-opt"),
                              ("method1 + ILS",            "+ ILS"),
                          ],
                          "Constructeur méthode 2 (insertion)": [
                              ("method2 seul",             "seul"),
                              ("method2 + OPT_2",          "+ 2-opt"),
                              ("method2 + OR_OPT",         "+ Or-opt"),
                              ("method2 + OPT_2 + OR_OPT", "+ 2-opt + Or-opt"),
                              ("method2 + ILS",            "+ ILS"),
                          ],
                      },
                      "ratio_vs_n.png", y_max,
                      suptitle=f"Qualité des algorithmes en fonction de la taille du problème\n"
                               f"({args.instances} instances aléatoires par valeur de n)",
                      band_ratios=bands)

    print(f"[{datetime.now():%H:%M:%S}] OK — 7 variantes écrites dans {args.out_dir}/")


if __name__ == "__main__":
    main()
