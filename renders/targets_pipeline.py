"""Schema de la chaine de calcul des cibles b_i (slide cibles).

Pipeline en Y :

  [ Acquisition ]──► [ Current  c_i ]──┐
                                       ├──► [ b_i = t_i - c_i ]
                  └► [ Skelam + proba  ]
                     [ → Target  t_i  ]┘

Produit : renders/targets_pipeline.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path("renders/targets_pipeline.png")

# Palette presentation
COL_DATA_BG    = "#D6EAF8"
COL_DATA_ED    = "#2980B9"
COL_CURR_BG    = "#E8F0FA"
COL_CURR_ED    = "#5DADE2"
COL_TARG_BG    = "#FCEFE1"
COL_TARG_ED    = "#F39C12"
COL_OUT_BG     = "#E8F8EF"
COL_OUT_ED     = "#27AE60"
COL_ARROW      = "#23373B"
TEXT_DARK      = "#23373B"


def box(ax, xy, w, h, lines, *, face, edge, lw=2.0, header=None):
    """Cadre arrondi avec libelle multi-ligne.

    `lines` : liste de tuples (text, fontsize, bold).
    """
    x, y = xy
    patch = FancyBboxPatch(
        (x - w / 2, y - h / 2), w, h,
        boxstyle="round,pad=0.04,rounding_size=0.20",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=2,
    )
    ax.add_patch(patch)

    if header is not None:
        ax.text(x - w / 2 + 0.18, y + h / 2 - 0.22, header,
                ha="left", va="center", fontsize=9,
                color=edge, fontweight="bold", zorder=3)

    n = len(lines)
    line_h = 0.36
    y0 = y + (n - 1) * line_h / 2
    for k, (text, fs, bold) in enumerate(lines):
        ax.text(x, y0 - k * line_h, text,
                ha="center", va="center",
                fontsize=fs, color=TEXT_DARK,
                fontweight=("bold" if bold else "normal"), zorder=3)


def arrow(ax, p, q, *, label=None, label_pos="mid", label_dy=0.30,
          color=COL_ARROW, lw=2.4):
    a = FancyArrowPatch(
        p, q,
        arrowstyle="-|>",
        mutation_scale=18,
        color=color, linewidth=lw,
        shrinkA=4, shrinkB=4,
        zorder=4,
    )
    ax.add_patch(a)
    if label is not None:
        mx = (p[0] + q[0]) / 2
        my = (p[1] + q[1]) / 2 + label_dy
        ax.text(mx, my, label,
                ha="center", va="center",
                fontsize=10, color=TEXT_DARK,
                fontstyle="italic", zorder=5)


def main():
    fig, ax = plt.subplots(figsize=(13.5, 5.6))

    BW, BH = 3.4, 1.85
    BW_MID, BH_MID = 4.2, 1.95

    p_data = (-5.4,  0.0)
    p_curr = ( 0.0,  1.55)      # branche haute
    p_targ = ( 0.0, -1.55)      # branche basse
    p_out  = ( 5.4,  0.0)

    # --- Boites -------------------------------------------------------------
    box(ax, p_data, BW, BH,
        lines=[
            ("Acquisition", 13, True),
            ("des données", 13, True),
            ("",             4, False),
            ("API Bicloo",            10, False),
            ("→ SQL (historique)",   10, False),
        ],
        face=COL_DATA_BG, edge=COL_DATA_ED)

    box(ax, p_curr, BW_MID, BH_MID,
        lines=[
            (r"Current  $c_i$", 13, True),
            ("",                 4, False),
            ("nombre de vélos",  10, False),
            ("actuellement à $i$", 10, False),
        ],
        face=COL_CURR_BG, edge=COL_CURR_ED)

    box(ax, p_targ, BW_MID, BH_MID,
        lines=[
            (r"Target  $t_i$",                    13, True),
            ("Skelam  +  méthode probabiliste",   11, True),
            ("",                                    4, False),
            ("nombre de vélos idéal",             10, False),
            ("prédit à partir de l'historique",   10, False),
        ],
        face=COL_TARG_BG, edge=COL_TARG_ED)

    box(ax, p_out, BW, BH,
        lines=[
            (r"$b_i = t_i - c_i$", 15, True),
            ("",                    4, False),
            ("écart à combler",    10, False),
            ("pour chaque station", 10, False),
        ],
        face=COL_OUT_BG, edge=COL_OUT_ED)

    # --- Fleches ------------------------------------------------------------
    # acquisition -> current (haut)
    arrow(ax, (p_data[0] + BW / 2, p_data[1] + 0.55),
              (p_curr[0] - BW_MID / 2, p_curr[1]),
              label="lecture\ndirecte", label_dy=0.55)
    # acquisition -> target (bas)
    arrow(ax, (p_data[0] + BW / 2, p_data[1] - 0.55),
              (p_targ[0] - BW_MID / 2, p_targ[1]),
              label="prédiction\npar historique", label_dy=-0.65)

    # current -> b_i
    arrow(ax, (p_curr[0] + BW_MID / 2, p_curr[1]),
              (p_out[0]  - BW / 2,     p_out[1] + 0.55),
              label="$c_i$", label_dy=0.45)
    # target -> b_i
    arrow(ax, (p_targ[0] + BW_MID / 2, p_targ[1]),
              (p_out[0]  - BW / 2,     p_out[1] - 0.55),
              label="$t_i$", label_dy=-0.55)

    # --- Titre & limites ----------------------------------------------------
    ax.set_title("Des données aux écarts à combler  $b_i = t_i - c_i$",
                 fontsize=13, color=TEXT_DARK, pad=12)

    ax.set_xlim(-7.8, 7.8)
    ax.set_ylim(-3.0, 3.0)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    main()
