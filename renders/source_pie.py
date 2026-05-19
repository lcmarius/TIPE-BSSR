"""Camembert des sources de mouvements (slide 15).

Agrège `bike_movements.source` sur l'ensemble des DBs brutes `data/source/*.sql`
puis rend un donut USER / TRUCK / MAINTENANCE avec annotations chiffrées.

Usage :
    python -m renders.source_pie
"""

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt


SOURCE_DIR = Path("data/source")
OUT        = Path("renders/source_pie.png")

# Palette presentation
PALETTE = {
    "USER":        "#27AE60",
    "TRUCK":       "#2980B9",
    "MAINTENANCE": "#C0392B",
}
TEXT_DARK = "#23373B"


def aggregate_sources() -> dict[str, int]:
    counts: dict[str, int] = {}
    for db in sorted(SOURCE_DIR.glob("source_*.sql")):
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM bike_movements GROUP BY source"
        ).fetchall()
        for source, cnt in rows:
            counts[source] = counts.get(source, 0) + cnt
        conn.close()
    return counts


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def main():
    counts = aggregate_sources()
    total  = sum(counts.values())
    keys     = ["USER", "TRUCK", "MAINTENANCE"]
    labels   = ["Usagers", "Camion", "Maintenance"]
    values   = [counts.get(k, 0) for k in keys]
    colors   = [PALETTE[k] for k in keys]

    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    fig.patch.set_facecolor("white")

    explode = [0.0, 0.05, 0.22]  # ecarte les petites tranches
    wedges, _ = ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        explode=explode,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )

    # Etiquettes a positions fixes pour eviter le chevauchement
    # (ancre = point sur la tranche, texte = position absolue, alignement)
    # Apres startangle=90 + counterclock=False :
    #   USER       occupe 91.2 % a partir du nord, sens horaire  -> majorite droite + bas
    #   TRUCK      8.6 %, tranche en haut-a-gauche, centre vers ~106 deg
    #   MAINTENANCE 0.24 %, sliver tout en haut, ~90 deg (decale par explode)
    label_layout = {
        "Usagers":     {"xy": ( 0.55, -0.55), "xytext": ( 1.30, -0.90), "ha": "left"},
        "Camion":      {"xy": (-0.40,  0.80), "xytext": (-1.30,  0.60), "ha": "right"},
        "Maintenance": {"xy": ( 0.10,  1.10), "xytext": ( 1.00,  1.30), "ha": "left"},
    }
    for lbl, v in zip(labels, values):
        cfg = label_layout[lbl]
        pct = 100 * v / total
        pct_str = f"{pct:.2f} %" if pct < 1 else f"{pct:.1f} %"
        ax.annotate(
            f"{lbl}\n{pct_str}  ({fmt(v)})",
            xy=cfg["xy"],
            xytext=cfg["xytext"],
            ha=cfg["ha"],
            va="center",
            fontsize=10.5,
            color=TEXT_DARK,
            arrowprops=dict(arrowstyle="-", color="#888", lw=0.8),
        )

    ax.set_aspect("equal")
    ax.set_xlim(-2.0, 2.2)
    ax.set_ylim(-1.5, 1.6)
    ax.axis("off")

    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    print(f"écrit : {OUT}")


if __name__ == "__main__":
    main()
