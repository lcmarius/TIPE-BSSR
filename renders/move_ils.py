"""Schema explicatif de la boucle ILS (slide 12).

Iterated Local Search : boucle de retroaction autour d'une recherche locale.

  s0 ─► VND init ─► s* (meilleure-connue)
                         │
                         ▼ perturbe(s*)
                   Perturbation (double-bridge / shuffle)
                         │
                         ▼ s'
                   VND : alterne 2-opt / OR-opt
                         │
                         ▼ s''  (optimum local)
                   dist(s'') < dist(s*) ?
                       │             │
                  oui ◄┘ non         │  retour boucle :
                       │             │  perturbation(s*) au tour suivant
                  s* ← s''           │
                       └─────────────┘

Produit : renders/move_ils.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon

OUT = Path("renders/move_ils.png")

# Palette presentation
COL_BOX_BG     = "#D6EAF8"
COL_BOX_ED     = "#2980B9"
COL_BEST_BG    = "#FCEFE1"
COL_BEST_ED    = "#F39C12"
COL_DEC_BG     = "#FDEDE7"
COL_DEC_ED     = "#C0392B"
COL_ARROW      = "#23373B"
COL_LOOP       = "#27AE60"     # feedback amelioration
COL_NOLOOP     = "#7F8C8D"     # feedback sans amelioration
TEXT_DARK      = "#23373B"


def box(ax, xy, w, h, label, *, face=COL_BOX_BG, edge=COL_BOX_ED, lw=2.0, fontsize=10, bold=True):
    """Cadre arrondi avec un libelle multi-ligne."""
    x, y = xy
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.04,rounding_size=0.18",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=2,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, color=TEXT_DARK, fontweight=weight, zorder=3)


def best_box(ax, xy, w, h, label):
    """Boite double-bordure pour mettre en valeur l'incumbent s*."""
    x, y = xy
    # bordure exterieure
    outer = FancyBboxPatch(
        (x - w / 2 - 0.10, y - h / 2 - 0.10), w + 0.20, h + 0.20,
        boxstyle="round,pad=0.04,rounding_size=0.20",
        facecolor="none", edgecolor=COL_BEST_ED, linewidth=1.6, zorder=2,
    )
    ax.add_patch(outer)
    box(ax, xy, w, h, label, face=COL_BEST_BG, edge=COL_BEST_ED, lw=2.0, fontsize=11)


def diamond(ax, xy, w, h, label):
    x, y = xy
    pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
    poly = Polygon(pts, closed=True,
                   facecolor=COL_DEC_BG, edgecolor=COL_DEC_ED, linewidth=2.0, zorder=2)
    ax.add_patch(poly)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=10, color=TEXT_DARK, fontweight="bold", zorder=3)


def arrow(ax, p, q, *, color=COL_ARROW, lw=2.0, style="-", curve=0.0, label=None,
          label_offset=(0.18, 0.0), label_fontsize=9, label_color=None):
    a = FancyArrowPatch(
        p, q,
        arrowstyle="-|>",
        mutation_scale=16,
        color=color, linewidth=lw, linestyle=style,
        shrinkA=4, shrinkB=4,
        connectionstyle=f"arc3,rad={curve}",
        zorder=4,
    )
    ax.add_patch(a)
    if label is not None:
        # point milieu de l'arc — pour les arcs droits, mid = (p+q)/2
        mx = (p[0] + q[0]) / 2 + label_offset[0]
        my = (p[1] + q[1]) / 2 + label_offset[1]
        ax.text(mx, my, label,
                ha="left", va="center",
                fontsize=label_fontsize,
                color=(label_color or color),
                fontweight="bold", zorder=5)


def main():
    fig, ax = plt.subplots(figsize=(11.0, 7.4))

    # ---- Positions ----------------------------------------------------------
    # Colonne centrale a x = 0. Boucle de retroaction passe par x = 4.6.
    BW, BH = 4.6, 0.95               # taille standard des boites
    DW, DH = 4.6, 1.20               # taille du losange

    p_s0      = (0.0,  6.10)
    p_vnd0    = (0.0,  4.85)
    p_best    = (0.0,  3.50)
    p_pert    = (0.0,  1.95)
    p_vnd     = (0.0,  0.55)
    p_dec     = (0.0, -1.10)

    # ---- Boites -------------------------------------------------------------
    box(ax, p_s0,   BW, BH, "Tournée initiale  $s_0$\n(méthode 1 / méthode 2)",
        fontsize=10)
    box(ax, p_vnd0, BW, BH,
        "VND initial  (Variable Neighborhood Descent)\n"
        "optimum local proche : 2-opt $\\rightleftarrows$ OR-opt",
        fontsize=9)
    best_box(ax, p_best, BW, BH, r"$s^\star$  meilleure solution connue")
    box(ax, p_pert, BW, BH,
        "Perturbation\n(double-bridge  /  segment shuffle)",
        fontsize=10)
    box(ax, p_vnd, BW, BH,
        "VND  (Variable Neighborhood Descent)\n"
        "optimum local proche : 2-opt $\\rightleftarrows$ OR-opt",
        fontsize=9)
    diamond(ax, p_dec, DW, DH, r"$\mathrm{dist}(s'') < \mathrm{dist}(s^\star)\ ?$")

    # ---- Fleches verticales (pipeline principal) ----------------------------
    arrow(ax, (p_s0[0],   p_s0[1]   - BH/2),
              (p_vnd0[0], p_vnd0[1] + BH/2))
    arrow(ax, (p_vnd0[0], p_vnd0[1] - BH/2),
              (p_best[0], p_best[1] + BH/2 + 0.10))
    arrow(ax, (p_best[0], p_best[1] - BH/2 - 0.10),
              (p_pert[0], p_pert[1] + BH/2),
              label=r"perturbe $s^\star$", label_offset=(0.25, 0.0))
    arrow(ax, (p_pert[0], p_pert[1] - BH/2),
              (p_vnd[0],  p_vnd[1]  + BH/2),
              label=r"$s'$", label_offset=(0.18, 0.0))
    arrow(ax, (p_vnd[0],  p_vnd[1] - BH/2),
              (p_dec[0],  p_dec[1] + DH/2),
              label=r"$s''$  (optimum local)", label_offset=(0.25, 0.0))

    # ---- Branche OUI : amelioration -> mise a jour s* (boucle gauche) -------
    # diamond left -> down then up sur la gauche -> rejoint s* par la gauche
    x_left = -4.20
    y_dec  = p_dec[1]
    y_best = p_best[1]
    # arc gauche : du losange vers le haut, puis a droite vers s*
    arrow(ax, (p_dec[0] - DW/2, y_dec),
              (x_left, y_dec),
              color=COL_LOOP, lw=2.4)
    ax.text(p_dec[0] - DW/2 - 0.25, y_dec + 0.35,
            "oui  :  $s^\\star \\leftarrow s''$",
            ha="right", va="center", fontsize=10,
            color=COL_LOOP, fontweight="bold", zorder=5)
    arrow(ax, (x_left, y_dec),
              (x_left, y_best),
              color=COL_LOOP, lw=2.4)
    arrow(ax, (x_left, y_best),
              (p_best[0] - BW/2 - 0.12, y_best),
              color=COL_LOOP, lw=2.4)

    # ---- Branche NON : pas d'amelioration -> boucle a droite vers s* --------
    x_right = 4.20
    arrow(ax, (p_dec[0] + DW/2, y_dec),
              (x_right, y_dec),
              color=COL_NOLOOP, lw=2.4)
    ax.text(p_dec[0] + DW/2 + 0.25, y_dec + 0.35,
            "non  :  $s^\\star$ inchangée",
            ha="left", va="center", fontsize=10,
            color=COL_NOLOOP, fontweight="bold", zorder=5)
    arrow(ax, (x_right, y_dec),
              (x_right, y_best),
              color=COL_NOLOOP, lw=2.4)
    arrow(ax, (x_right, y_best),
              (p_best[0] + BW/2 + 0.12, y_best),
              color=COL_NOLOOP, lw=2.4)

    # ---- Titre & limites ----------------------------------------------------
    ax.set_title("ILS : perturber, ré-optimiser, comparer  —  on relance autour de $s^\\star$",
                 fontsize=13, color=TEXT_DARK, pad=14)

    ax.set_xlim(-6.0, 6.0)
    ax.set_ylim(-2.2, 6.9)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
