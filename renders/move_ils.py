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

from renders._presstyle import apply_style, palette as P, save_pres

OUT = "move_ils"   # → pres/fig/move_ils.pdf

# Palette alignée sur pres/main.tex
COL_BOX_BG     = "#D6EAF8"      # depot pâle
COL_BOX_ED     = P.depot
COL_BEST_BG    = "#FCEFE1"      # accent pâle
COL_BEST_ED    = P.accent
COL_DEC_BG     = "#FDEDE7"      # deficit pâle
COL_DEC_ED     = P.deficit
COL_ARROW      = P.tdark
COL_LOOP       = P.surplus     # branche oui : amélioration
COL_NOLOOP     = P.textmuted   # branche non : pas d'amélioration
TEXT_DARK      = P.tdark


def box(ax, xy, w, h, label, *, face=COL_BOX_BG, edge=COL_BOX_ED, lw=1.2, fontsize=7, bold=True):
    """Cadre arrondi avec un libelle multi-ligne."""
    x, y = xy
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.03,rounding_size=0.12",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=2,
    )
    ax.add_patch(patch)
    weight = "bold" if bold else "normal"
    ax.text(x, y, label, ha="center", va="center",
            fontsize=fontsize, color=TEXT_DARK, fontweight=weight, zorder=3)


def best_box(ax, xy, w, h, label):
    """Boite double-bordure pour mettre en valeur l'incumbent s*."""
    x, y = xy
    outer = FancyBboxPatch(
        (x - w / 2 - 0.08, y - h / 2 - 0.08), w + 0.16, h + 0.16,
        boxstyle="round,pad=0.03,rounding_size=0.14",
        facecolor="none", edgecolor=COL_BEST_ED, linewidth=1.0, zorder=2,
    )
    ax.add_patch(outer)
    box(ax, xy, w, h, label, face=COL_BEST_BG, edge=COL_BEST_ED, lw=1.2, fontsize=8)


def diamond(ax, xy, w, h, label):
    x, y = xy
    pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
    poly = Polygon(pts, closed=True,
                   facecolor=COL_DEC_BG, edgecolor=COL_DEC_ED, linewidth=1.2, zorder=2)
    ax.add_patch(poly)
    ax.text(x, y, label, ha="center", va="center",
            fontsize=7.5, color=TEXT_DARK, fontweight="bold", zorder=3)


def down_triangle(ax, xy, *, size=0.16, color=COL_ARROW, label=None,
                  label_offset=(0.18, 0.0), label_fontsize=6.5, label_color=None):
    """Petit triangle plein orienté ↓, à utiliser entre 2 boîtes adjacentes
    quand l'espace est trop court pour une flèche complète."""
    x, y = xy
    pts = [(x - size, y + size * 0.85),
           (x + size, y + size * 0.85),
           (x,        y - size * 0.85)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=color,
                          edgecolor=color, linewidth=0, zorder=4))
    if label is not None:
        ax.text(x + label_offset[0], y + label_offset[1], label,
                ha="left", va="center",
                fontsize=label_fontsize,
                color=(label_color or color),
                fontweight="bold", zorder=5)


def arrow(ax, p, q, *, color=COL_ARROW, lw=1.2, style="-", curve=0.0, label=None,
          label_offset=(0.15, 0.0), label_fontsize=6.5, label_color=None):
    a = FancyArrowPatch(
        p, q,
        arrowstyle="-|>",
        mutation_scale=10,
        color=color, linewidth=lw, linestyle=style,
        shrinkA=3, shrinkB=3,
        connectionstyle=f"arc3,rad={curve}",
        zorder=4,
    )
    ax.add_patch(a)
    if label is not None:
        mx = (p[0] + q[0]) / 2 + label_offset[0]
        my = (p[1] + q[1]) / 2 + label_offset[1]
        ax.text(mx, my, label,
                ha="left", va="center",
                fontsize=label_fontsize,
                color=(label_color or color),
                fontweight="bold", zorder=5)


def main():
    apply_style()
    fig, ax = plt.subplots(figsize=(5.5, 3.5))
    ax.grid(False)

    # ---- Positions ----------------------------------------------------------
    # Colonne centrale à x = 0. Boucle de rétroaction par x = ±3.6.
    BW, BH = 3.6, 0.72               # boîtes compactes
    DW, DH = 4.2, 1.05               # losange élargi pour que le label tienne

    p_s0      = (0.0,  5.10)
    p_vnd0    = (0.0,  4.05)
    p_best    = (0.0,  2.90)
    p_pert    = (0.0,  1.60)
    p_vnd     = (0.0,  0.45)
    p_dec     = (0.0, -1.00)

    # ---- Boites -------------------------------------------------------------
    box(ax, p_s0,   BW, BH, "Tournée initiale  $s_0$",                fontsize=7.5)
    box(ax, p_vnd0, BW, BH, "VND initial",                            fontsize=7.5)
    best_box(ax, p_best, BW, BH, r"$s^\star$  meilleure connue")
    box(ax, p_pert, BW, BH, "Perturbation",                           fontsize=7.5)
    box(ax, p_vnd,  BW, BH, "VND",                                    fontsize=7.5)
    diamond(ax, p_dec, DW, DH,
            r"$\mathrm{cost}(s'') < \mathrm{cost}(s^\star)\ ?$")

    # ---- Annotations à droite : précisent VND et Perturbation -------------
    x_anno = 4.0
    ax.text(x_anno, p_vnd0[1],
            "VND (Variable\nNeighborhood\nDescent) :\n"
            "2-opt $\\rightleftarrows$ OR-opt\n"
            "jusqu'à un\noptimum local",
            ha="left", va="center", fontsize=6.5,
            color=COL_BOX_ED, fontstyle="italic", zorder=5)
    ax.text(x_anno, p_pert[1],
            "saut aléatoire :\npermet de sortir\nd'un optimum local",
            ha="left", va="center", fontsize=6.5,
            color=COL_BEST_ED, fontstyle="italic", zorder=5)
    # Petits traits pointillés vers les boîtes correspondantes
    ax.plot([p_vnd0[0] + BW/2 + 0.05, x_anno - 0.10],
            [p_vnd0[1], p_vnd0[1]],
            color=COL_BOX_ED, ls=":", lw=0.8, zorder=1)
    ax.plot([p_pert[0] + BW/2 + 0.05, x_anno - 0.10],
            [p_pert[1], p_pert[1]],
            color=COL_BEST_ED, ls=":", lw=0.8, zorder=1)

    # ---- Triangles verticaux (pipeline principal) ---------------------------
    # Entre boîtes collées, une flèche complète serait amputée par les têtes
    # et le shrink — on utilise des triangles pleins centrés entre paires.
    down_triangle(ax, (0.0, (p_s0[1]   - BH/2 + p_vnd0[1] + BH/2) / 2))
    down_triangle(ax, (0.0, (p_vnd0[1] - BH/2 + p_best[1] + BH/2) / 2))
    down_triangle(ax, (0.0, (p_best[1] - BH/2 + p_pert[1] + BH/2) / 2),
                  label=r"perturbe $s^\star$")
    down_triangle(ax, (0.0, (p_pert[1] - BH/2 + p_vnd[1]  + BH/2) / 2),
                  label=r"$s'$")
    down_triangle(ax, (0.0, (p_vnd[1]  - BH/2 + p_dec[1]  + DH/2) / 2),
                  label=r"$s''$  (optimum local)")

    # ---- Branche OUI : amelioration -> mise a jour s* (boucle gauche) -------
    x_left = -3.20
    y_dec  = p_dec[1]
    y_best = p_best[1]
    # arc gauche : du losange vers le haut, puis a droite vers s*
    arrow(ax, (p_dec[0] - DW/2, y_dec),
              (x_left, y_dec),
              color=COL_LOOP, lw=1.5)
    ax.text(p_dec[0] - DW/2 - 0.20, y_dec - 0.32,
            "oui  :  $s^\\star \\leftarrow s''$",
            ha="right", va="center", fontsize=7,
            color=COL_LOOP, fontweight="bold", zorder=5)
    arrow(ax, (x_left, y_dec),
              (x_left, y_best),
              color=COL_LOOP, lw=1.5)
    arrow(ax, (x_left, y_best),
              (p_best[0] - BW/2 - 0.12, y_best),
              color=COL_LOOP, lw=1.5)

    # ---- Branche NON : pas d'amelioration -> boucle a droite vers s* --------
    x_right = 2.80
    arrow(ax, (p_dec[0] + DW/2, y_dec),
              (x_right, y_dec),
              color=COL_NOLOOP, lw=1.5)
    ax.text(p_dec[0] + DW/2 + 0.20, y_dec - 0.32,
            "non  :  $s^\\star$ inchangée",
            ha="left", va="center", fontsize=7,
            color=COL_NOLOOP, fontweight="bold", zorder=5)
    arrow(ax, (x_right, y_dec),
              (x_right, y_best),
              color=COL_NOLOOP, lw=1.5)
    arrow(ax, (x_right, y_best),
              (p_best[0] + BW/2 + 0.12, y_best),
              color=COL_NOLOOP, lw=1.5)

    ax.set_title("ILS : perturber, ré-optimiser, comparer — on relance autour de $s^\\star$",
                 fontsize=8.5, color=TEXT_DARK, pad=5, fontweight="bold")

    ax.set_xlim(-5.0, 7.0)
    ax.set_ylim(-2.0, 5.8)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    save_pres(fig, OUT, height="0.86\\textheight")


if __name__ == "__main__":
    main()
