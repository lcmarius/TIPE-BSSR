"""Schemas lineaires des operateurs 2-opt et OR-opt (slide 11).

Reprend la representation en succession des commentaires de
`src/solver/algorithm/incrementer/opt2.py` et `or_opt.py` :

  2-opt
    avant : i-1 -> i -> ... -> j -> j+1
    apres : i-1 -> j -> ... -> i -> j+1

  OR-opt
    avant : t1 -> t2 -> ... -> t3 -> t4   ...   p1 -> p2
                └─ segment ─┘
    apres : t1 -> t4                      ...   p1 -> t2 -> ... -> t3 -> p2
            └─trou─┘                                  └─ segment ─┘

Produit deux PNG distincts :
    renders/move_2opt.png
    renders/move_oropt.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT_2OPT  = Path("renders/move_2opt.png")
OUT_OROPT = Path("renders/move_oropt.png")

# Palette
COL_ARC      = "#F39C12"   # arete conservee
COL_REMOVE   = "#C0392B"   # arete supprimee
COL_ADD      = "#27AE60"   # arete ajoutee
COL_NODE_BG  = "#D6EAF8"
COL_NODE_ED  = "#2980B9"
COL_SEG_BG   = "#FCEFE1"   # bandeau segment
COL_SEG_ED   = "#F39C12"
TEXT_DARK    = "#23373B"
GREY         = "#7F8C8D"


def draw_arrow(ax, p, q, color, lw=2.4, style="-", curve=0.0):
    arrow = FancyArrowPatch(
        p, q,
        arrowstyle="-|>",
        mutation_scale=14,
        color=color,
        linewidth=lw,
        linestyle=style,
        shrinkA=14, shrinkB=14,
        connectionstyle=f"arc3,rad={curve}",
        zorder=2,
    )
    ax.add_patch(arrow)


def draw_node(ax, pos, label, faded=False):
    face = "#F4F6F7" if faded else COL_NODE_BG
    edge = GREY      if faded else COL_NODE_ED
    txt  = GREY      if faded else TEXT_DARK
    ax.scatter(
        [pos[0]], [pos[1]],
        s=900, facecolor=face, edgecolor=edge,
        linewidths=2.0, zorder=3,
    )
    ax.text(pos[0], pos[1], label,
            ha="center", va="center",
            fontsize=10, fontweight="bold",
            color=txt, zorder=4)


def draw_row_label(ax, y, text, color=TEXT_DARK):
    ax.text(-0.4, y, text, ha="right", va="center",
            fontsize=12, fontweight="bold", color=color)


def draw_segment_band(ax, x_left, x_right, y, label):
    """Bandeau colore sous une suite de sommets pour materialiser le segment."""
    h = 0.28
    pad = 0.25
    box = FancyBboxPatch(
        (x_left - pad, y - h / 2),
        (x_right - x_left) + 2 * pad, h,
        boxstyle="round,pad=0.02,rounding_size=0.14",
        linewidth=1.4, edgecolor=COL_SEG_ED,
        facecolor=COL_SEG_BG, zorder=1,
    )
    ax.add_patch(box)
    ax.text((x_left + x_right) / 2, y, label,
            ha="center", va="center",
            fontsize=10, fontstyle="italic", color=COL_SEG_ED,
            fontweight="bold", zorder=2)


# ---------------------------------------------------------------------------
# 2-opt
# ---------------------------------------------------------------------------

def render_2opt():
    """Inversion du segment turn[i..j].

    avant : i-1 -> i -> i+1 -> ... -> j-1 -> j -> j+1
    apres : i-1 -> j -> j-1 -> ... -> i+1 -> i -> j+1
    """
    fig, ax = plt.subplots(figsize=(11.5, 4.6))

    labels = [r"$i{-}1$", r"$i$", r"$i{+}1$", r"$\cdots$", r"$j{-}1$", r"$j$", r"$j{+}1$"]
    xs = [0, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0]
    Y_AV = 2.6
    Y_AP = 0.6

    # ---- ligne AVANT ---------------------------------------------------------
    draw_row_label(ax, Y_AV, "avant")
    for x, lab in zip(xs, labels):
        draw_node(ax, (x, Y_AV), lab)
    # arcs : (i-1)->i et j->(j+1) sont supprimes ; tout l'interieur est conserve
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AV); v = (xs[k + 1], Y_AV)
        if k == 0 or k == len(xs) - 2:           # (i-1,i) et (j,j+1)
            draw_arrow(ax, u, v, COL_REMOVE, lw=2.6, style="--")
        else:
            draw_arrow(ax, u, v, COL_ARC)

    # bandeau segment
    draw_segment_band(ax, xs[1], xs[5], Y_AV - 0.85, "segment à inverser")

    # ---- ligne APRES ---------------------------------------------------------
    draw_row_label(ax, Y_AP, "après")
    # ordre apres inversion : i-1, j, j-1, ..., i+1, i, j+1
    labels_ap = [r"$i{-}1$", r"$j$", r"$j{-}1$", r"$\cdots$", r"$i{+}1$", r"$i$", r"$j{+}1$"]
    for x, lab in zip(xs, labels_ap):
        draw_node(ax, (x, Y_AP), lab)
    # arcs : (i-1,j) et (i,j+1) ajoutes ; interieur en sens reverse, conserve
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AP); v = (xs[k + 1], Y_AP)
        if k == 0 or k == len(xs) - 2:           # (i-1,j) et (i,j+1)
            draw_arrow(ax, u, v, COL_ADD, lw=2.6)
        else:
            draw_arrow(ax, u, v, COL_ARC)

    draw_segment_band(ax, xs[1], xs[5], Y_AP - 0.85, "segment inversé")

    # Legende
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=COL_ARC,    lw=2.4, label="arête conservée"),
        Line2D([0], [0], color=COL_REMOVE, lw=2.4, linestyle="--", label="arête supprimée"),
        Line2D([0], [0], color=COL_ADD,    lw=2.4, label="arête ajoutée"),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=3,
              frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.08))

    ax.set_title(r"2-opt : inversion du segment $[i..j]$",
                 fontsize=13, color=TEXT_DARK, pad=10)
    ax.set_xlim(-1.2, 9.8)
    ax.set_ylim(-0.8, 3.3)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(OUT_2OPT, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved -> {OUT_2OPT}")


# ---------------------------------------------------------------------------
# OR-opt
# ---------------------------------------------------------------------------

def render_oropt():
    """Relocation d'un segment [t2..t3] apres p1.

    avant : t1 -> t2 -> ... -> t3 -> t4 -> ... -> p1 -> p2
    apres : t1 -> t4 -> ... -> p1 -> t2 -> ... -> t3 -> p2

    Layout : 8 colonnes pour 7 aretes ; (p1, p2) (avant) et (t3, p2) (apres)
    sont adjacents donc dessines en ligne, sans arc courbe.
    """
    fig, ax = plt.subplots(figsize=(12.5, 4.8))

    Y_AV = 2.6
    Y_AP = 0.6

    xs = [0.0, 1.6, 3.2, 4.8, 6.4, 8.0, 9.6, 11.2]

    # ---- ligne AVANT ---------------------------------------------------------
    draw_row_label(ax, Y_AV, "avant")
    labels_av = [r"$t_1$", r"$t_2$", r"$\cdots$", r"$t_3$",
                 r"$t_4$", r"$\cdots$", r"$p_1$", r"$p_2$"]
    for x, lab in zip(xs, labels_av):
        draw_node(ax, (x, Y_AV), lab)
    # 7 aretes : indices supprimes = (t1,t2)=0, (t3,t4)=3, (p1,p2)=6
    removed_edges = {0, 3, 6}
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AV); v = (xs[k + 1], Y_AV)
        if k in removed_edges:
            draw_arrow(ax, u, v, COL_REMOVE, lw=2.6, style="--")
        else:
            draw_arrow(ax, u, v, COL_ARC)

    # bandeau segment (sous t2..t3)
    draw_segment_band(ax, xs[1], xs[3], Y_AV - 0.85, "segment à relocaliser")

    # ---- ligne APRES ---------------------------------------------------------
    draw_row_label(ax, Y_AP, "après")
    labels_ap = [r"$t_1$", r"$t_4$", r"$\cdots$", r"$p_1$",
                 r"$t_2$", r"$\cdots$", r"$t_3$", r"$p_2$"]
    for x, lab in zip(xs, labels_ap):
        draw_node(ax, (x, Y_AP), lab)
    # 7 aretes : indices ajoutes = (t1,t4)=0, (p1,t2)=3, (t3,p2)=6
    added_edges = {0, 3, 6}
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AP); v = (xs[k + 1], Y_AP)
        if k in added_edges:
            draw_arrow(ax, u, v, COL_ADD, lw=2.6)
        else:
            draw_arrow(ax, u, v, COL_ARC)

    # bandeau segment relocalise (cols 4..6 : t2..t3)
    draw_segment_band(ax, xs[4], xs[6], Y_AP - 0.85, "segment relocalisé")

    # Legende
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=COL_ARC,    lw=2.4, label="arête conservée"),
        Line2D([0], [0], color=COL_REMOVE, lw=2.4, linestyle="--", label="arête supprimée"),
        Line2D([0], [0], color=COL_ADD,    lw=2.4, label="arête ajoutée"),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=3,
              frameon=False, fontsize=10, bbox_to_anchor=(0.5, -0.08))

    ax.set_title(r"OR-opt : relocation du segment $[t_2..t_3]$ après $p_1$",
                 fontsize=13, color=TEXT_DARK, pad=10)
    ax.set_xlim(-1.4, 12.2)
    ax.set_ylim(-0.9, 3.5)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(OUT_OROPT, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"saved -> {OUT_OROPT}")


def main():
    render_2opt()
    render_oropt()


if __name__ == "__main__":
    main()
