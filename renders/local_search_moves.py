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

from renders._presstyle import apply_style, palette as P, save_pres

OUT_2OPT  = "move_2opt"     # → pres/fig/move_2opt.pdf
OUT_OROPT = "move_oropt"    # → pres/fig/move_oropt.pdf

# Palette alignée sur pres/main.tex
COL_ARC      = P.accent       # arête conservée
COL_REMOVE   = P.deficit      # arête supprimée
COL_ADD      = P.surplus      # arête ajoutée
COL_NODE_BG  = "#D6EAF8"      # depot très pâle (pas de variante dans palette)
COL_NODE_ED  = P.depot
COL_SEG_BG   = "#FCEFE1"      # accent très pâle
COL_SEG_ED   = P.accent
TEXT_DARK    = P.tdark
GREY         = P.textmuted


def draw_arrow(ax, p, q, color, lw=1.4, style="-", curve=0.0):
    arrow = FancyArrowPatch(
        p, q,
        arrowstyle="-|>",
        mutation_scale=9,
        color=color,
        linewidth=lw,
        linestyle=style,
        shrinkA=10, shrinkB=10,
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
        s=380, facecolor=face, edgecolor=edge,
        linewidths=1.2, zorder=3,
    )
    ax.text(pos[0], pos[1], label,
            ha="center", va="center",
            fontsize=7, fontweight="bold",
            color=txt, zorder=4)


def draw_row_label(ax, y, text, color=TEXT_DARK):
    # x=-0.5 + ha="right" → fin du texte à x=-0.5 ; les nodes commencent à
    # x=0.5 → gap visible entre le label et la première bulle.
    ax.text(-0.5, y, text, ha="right", va="center",
            fontsize=8, fontweight="bold", color=color)


def draw_segment_band(ax, x_left, x_right, y, label, *, h=0.48, pad=0.35):
    """Bandeau colore sous une suite de sommets pour materialiser le segment.

    Hauteur `h` et padding `pad` ajustables : utile pour les schémas où le
    label est long mais l'envergure du segment est courte (cas OR-opt).
    """
    box = FancyBboxPatch(
        (x_left - pad, y - h / 2),
        (x_right - x_left) + 2 * pad, h,
        boxstyle="round,pad=0.02,rounding_size=0.10",
        linewidth=0.9, edgecolor=COL_SEG_ED,
        facecolor=COL_SEG_BG, zorder=1,
    )
    ax.add_patch(box)
    ax.text((x_left + x_right) / 2, y, label,
            ha="center", va="center",
            fontsize=7, fontstyle="italic", color=COL_SEG_ED,
            fontweight="bold", zorder=2)


# ---------------------------------------------------------------------------
# 2-opt
# ---------------------------------------------------------------------------

def render_2opt():
    """Inversion du segment turn[i..j].

    avant : i-1 -> i -> i+1 -> ... -> j-1 -> j -> j+1
    apres : i-1 -> j -> j-1 -> ... -> i+1 -> i -> j+1
    """
    apply_style()
    fig, ax = plt.subplots(figsize=(4.2, 2.4))
    ax.grid(False)

    labels = [r"$i{-}1$", r"$i$", r"$i{+}1$", r"$\cdots$", r"$j{-}1$", r"$j$", r"$j{+}1$"]
    # Espacement compact (1.0 entre nodes) + offset 0.5 pour gap avec row_label
    xs = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]
    Y_AV = 3.0
    Y_AP = 0.5

    # ---- ligne AVANT ---------------------------------------------------------
    draw_row_label(ax, Y_AV, "avant")
    for x, lab in zip(xs, labels):
        draw_node(ax, (x, Y_AV), lab)
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AV); v = (xs[k + 1], Y_AV)
        if k == 0 or k == len(xs) - 2:
            draw_arrow(ax, u, v, COL_REMOVE, lw=1.6, style="--")
        else:
            draw_arrow(ax, u, v, COL_ARC)

    draw_segment_band(ax, xs[1], xs[5], Y_AV - 0.75, "segment à inverser")

    # ---- ligne APRES ---------------------------------------------------------
    draw_row_label(ax, Y_AP, "après")
    labels_ap = [r"$i{-}1$", r"$j$", r"$j{-}1$", r"$\cdots$", r"$i{+}1$", r"$i$", r"$j{+}1$"]
    for x, lab in zip(xs, labels_ap):
        draw_node(ax, (x, Y_AP), lab)
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AP); v = (xs[k + 1], Y_AP)
        if k == 0 or k == len(xs) - 2:
            draw_arrow(ax, u, v, COL_ADD, lw=1.6)
        else:
            draw_arrow(ax, u, v, COL_ARC)

    draw_segment_band(ax, xs[1], xs[5], Y_AP - 0.75, "segment inversé")

    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=COL_ARC,    lw=1.6, label="arête conservée"),
        Line2D([0], [0], color=COL_REMOVE, lw=1.6, linestyle="--", label="arête supprimée"),
        Line2D([0], [0], color=COL_ADD,    lw=1.6, label="arête ajoutée"),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=3,
              frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, -0.08))

    ax.set_title(r"2-opt : inversion du segment $[i..j]$",
                 fontsize=8.5, color=TEXT_DARK, pad=4, fontweight="bold")
    ax.set_xlim(-1.2, 7.2)
    ax.set_ylim(-0.7, 3.8)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    save_pres(fig, OUT_2OPT, height="0.58\\textheight")


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
    apply_style()
    fig, ax = plt.subplots(figsize=(4.8, 2.4))
    ax.grid(False)

    Y_AV = 3.0
    Y_AP = 0.5

    # Espacement compact (1.0 entre nodes) + offset 0.5 pour gap avec row_label
    xs = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]

    # ---- ligne AVANT ---------------------------------------------------------
    draw_row_label(ax, Y_AV, "avant")
    labels_av = [r"$t_1$", r"$t_2$", r"$\cdots$", r"$t_3$",
                 r"$t_4$", r"$\cdots$", r"$p_1$", r"$p_2$"]
    for x, lab in zip(xs, labels_av):
        draw_node(ax, (x, Y_AV), lab)
    removed_edges = {0, 3, 6}
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AV); v = (xs[k + 1], Y_AV)
        if k in removed_edges:
            draw_arrow(ax, u, v, COL_REMOVE, lw=1.6, style="--")
        else:
            draw_arrow(ax, u, v, COL_ARC)

    # Segment court (t2..t3 = 2 unités), label long → extra padding pour
    # élargir la box et laisser respirer le texte.
    draw_segment_band(ax, xs[1], xs[3], Y_AV - 0.75, "segment à relocaliser",
                      pad=0.7)

    # ---- ligne APRES ---------------------------------------------------------
    draw_row_label(ax, Y_AP, "après")
    labels_ap = [r"$t_1$", r"$t_4$", r"$\cdots$", r"$p_1$",
                 r"$t_2$", r"$\cdots$", r"$t_3$", r"$p_2$"]
    for x, lab in zip(xs, labels_ap):
        draw_node(ax, (x, Y_AP), lab)
    added_edges = {0, 3, 6}
    for k in range(len(xs) - 1):
        u = (xs[k], Y_AP); v = (xs[k + 1], Y_AP)
        if k in added_edges:
            draw_arrow(ax, u, v, COL_ADD, lw=1.6)
        else:
            draw_arrow(ax, u, v, COL_ARC)

    draw_segment_band(ax, xs[4], xs[6], Y_AP - 0.75, "segment relocalisé",
                      pad=0.7)

    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], color=COL_ARC,    lw=1.6, label="arête conservée"),
        Line2D([0], [0], color=COL_REMOVE, lw=1.6, linestyle="--", label="arête supprimée"),
        Line2D([0], [0], color=COL_ADD,    lw=1.6, label="arête ajoutée"),
    ]
    ax.legend(handles=handles, loc="lower center", ncol=3,
              frameon=False, fontsize=6.5, bbox_to_anchor=(0.5, -0.08))

    ax.set_title(r"OR-opt : relocation du segment $[t_2..t_3]$ après $p_1$",
                 fontsize=8.5, color=TEXT_DARK, pad=4, fontweight="bold")
    ax.set_xlim(-1.2, 8.2)
    ax.set_ylim(-0.7, 3.8)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    save_pres(fig, OUT_OROPT, height="0.58\\textheight")


def main():
    render_2opt()
    render_oropt()


if __name__ == "__main__":
    main()
