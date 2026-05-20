"""Visualisation d'une instance aléatoire du sweep — slide rapport d'approximation.

Génère UNE instance synthétique (carré 5×5 km, dépôt au centre, $n$ stations
uniformes avec $b_i$ équilibrés), la résout via méthode 1 + ILS, et trace :
  - les stations colorées par signe de $b_i$ (vert = déposer, rouge = retirer)
  - la tournée trouvée (lignes orange entre stations consécutives)
  - le ratio $\\rho$ obtenu en titre

Sert d'illustration de ce qu'on mesure pour chaque point du sweep
`ratio_vs_n.pdf` : un ratio par instance, moyenné sur 100 instances par $n$.

Produit : pres/fig/instance_random.pdf
"""

import os

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from renders._presstyle import apply_style, palette as P
from renders.render_sweep import SyntheticMap, generate_instance
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.incrementer.ils import ils
from src.solver.graph import SolvingStationGraph
from src.solver.reviewer import review_solution


N        = 20
CAPACITY = 25
TRUCK    = 30
SEED     = 12_345    # une instance lisible (pas trop serré)


def _solve(targeted, depot, depot_t):
    """Construit le graphe, résout (méthode 1 + ILS), renvoie (graph, metrics)."""
    synth = SyntheticMap()
    g = SolvingStationGraph(synth, depot)
    g.station_map[0] = depot_t
    for t in targeted:
        if t.bike_gap() != 0:
            g.add_station(t)
    g.preload_times()
    method1(g, TRUCK)
    ils(g, TRUCK, max_iterations=200)
    return g, review_solution(g, TRUCK)


def _tour_coords(g, depot, targeted):
    """Reconstitue la tournée 0 → … → 0 en coordonnées (x, y)."""
    by_num = {t.number: t for t in targeted}
    by_num[0] = depot
    coords = [(depot.long, depot.lat)]
    visited = {0}
    cur = 0
    while True:
        succ = g.get_successor(cur)
        if succ is None or succ in visited:
            break
        s = by_num[succ]
        coords.append((s.long, s.lat))
        visited.add(succ)
        cur = succ
    coords.append((depot.long, depot.lat))   # retour au dépôt
    return coords


def main():
    apply_style()
    targeted, depot, depot_t = generate_instance(N, CAPACITY, SEED)
    g, metrics = _solve(targeted, depot, depot_t)

    fig, ax = plt.subplots(figsize=(6.0, 2.2))
    ax.grid(False)

    # Stations colorées par signe de b_i
    for t in targeted:
        b = -t.bike_gap()        # b_i = target - count
        if b > 0:
            color = P.surplus
        elif b < 0:
            color = P.deficit
        else:
            color = P.textmuted
        ax.scatter([t.long], [t.lat], s=12 + 8 * abs(b),
                   facecolor=color, edgecolor=P.tdark, linewidth=0.4,
                   alpha=0.92, zorder=4)

    # Dépôt (carré bleu)
    ax.scatter([depot.long], [depot.lat], s=70, marker="s",
               facecolor=P.depot, edgecolor=P.tdark, linewidth=0.6, zorder=5)
    ax.text(depot.long, depot.lat - 0.10, "dépôt",
            ha="center", va="top", fontsize=6.5,
            color=P.depot, fontweight="bold")

    # Axe carré (les coords sont en km autour de 0,0)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ("top", "right", "bottom", "left"):
        ax.spines[sp].set_visible(False)
    ax.margins(0.05)

    fig.tight_layout()
    # Sortie en PNG (et pas PDF) : dimensions pixel-prévisibles pour aligner
    # parfaitement avec la column de texte dans Beamer.
    out_dir = "pres/fig"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/instance_random.png"
    fig.savefig(out_path, dpi=240, bbox_inches="tight",
                pad_inches=0.04, transparent=True)
    plt.close(fig)
    print(f"  écrit {out_path}")
    print(f"  LaTeX : \\fig[\\linewidth]{{instance_random.png}}")


if __name__ == "__main__":
    main()
