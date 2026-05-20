"""Carte des cibles $b_i$ à un instant donné — slide protocole.

Charge un snapshot (jour + heure locale), appelle le targeter pour
produire les cibles $t_i$, calcule $b_i = t_i - c_i$ et trace les
stations sur leurs positions GPS, taille $\\propto |b_i|$ et couleur
selon le signe :
  - rouge  ($b_i > 0$) → station qui va RECEVOIR des vélos
  - bleu   ($b_i < 0$) → station qui va DONNER  des vélos
Cohérent avec `asymmetry_morning` (cmap RdBu_r).

Produit : pres/fig/targets_map.png (haute résolution, large format pour
la slide Evan où le texte est aligné à gauche de l'image).
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import numpy as np

from src.objects.station import Station
from src.targeter.targeter import compute_adjusted_targets
from src.utils.timezone import local_to_utc_naive
from renders._presstyle import apply_style, palette as P, PRES_FIG_DIR


SNAPSHOT      = datetime(2026, 4, 15, 12, 0, 0)   # mercredi midi, printemps
TRUCK_Q       = 30
CLEAN_DIR     = "data/clean"
GRAPHML_PATH  = "data/nantes_graph.graphml"


def _load_snapshot(when_local: datetime):
    when_utc = local_to_utc_naive(when_local)
    db = f"{CLEAN_DIR}/clean_{when_local.date().isoformat()}.sql"
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT station_number, name, capacity, address, geo_lat, geo_long "
        "FROM stations ORDER BY station_number"
    ).fetchall()
    stations = [Station(n, name, cap, addr, lon, lat)
                for n, name, cap, addr, lat, lon in rows]
    count_rows = con.execute(
        """
        SELECT station_number, available_bikes
        FROM station_history h1
        WHERE timestamp = (
            SELECT MAX(timestamp) FROM station_history h2
            WHERE h2.station_number = h1.station_number AND h2.timestamp <= ?
        )
        """,
        (when_utc.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchall()
    con.close()
    return stations, {n: c for n, c in count_rows}


def main():
    stations, counts = _load_snapshot(SNAPSHOT)
    targeted = compute_adjusted_targets(stations, counts, SNAPSHOT, TRUCK_Q,
                                         clean_dir=CLEAN_DIR)
    # b_i = c_i − t_i (current − target) : positif ⇒ surplus (vert),
    # négatif ⇒ déficit (rouge). Cohérent avec bike_gap dans CLAUDE.md.
    b_by_sn = {t.number: (t.bike_count - t.bike_target) for t in targeted}

    apply_style()
    # Format plus carré et largement plus grand : le PNG sera intégré
    # à ~0,60·linewidth sur la slide Evan et doit rester net.
    # Pas de titre ni de légende : titre/légende gérés en LaTeX côté slide.
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    ax.grid(False)

    # Fond OSM en noir : la silhouette de Nantes devient lisible derrière
    # les points (alpha modéré pour ne pas écraser le code couleur).
    if os.path.exists(GRAPHML_PATH):
        import osmnx as ox
        g = ox.load_graphml(GRAPHML_PATH)
        segs = [[(g.nodes[u]['x'], g.nodes[u]['y']),
                 (g.nodes[v]['x'], g.nodes[v]['y'])]
                for u, v in g.edges(keys=False)]
        ax.add_collection(LineCollection(segs, colors="black",
                                          linewidths=0.4, alpha=0.55, zorder=1))

    # 3 catégories discrètes : ignorée (b=0, gris), b>0 (surplus, vert),
    # b<0 (deficit, rouge). Taille ∝ |b_i| pour les actifs ; les points
    # gris (équilibrés) ont la même taille de référence que les autres.
    BASE_S = 55
    xs_ign, ys_ign = [], []
    xs_pos, ys_pos, s_pos = [], [], []
    xs_neg, ys_neg, s_neg = [], [], []
    for s in stations:
        if s.number == 0:
            continue
        b = b_by_sn.get(s.number, 0)
        if b == 0:
            xs_ign.append(s.long); ys_ign.append(s.lat)
        elif b > 0:
            xs_pos.append(s.long); ys_pos.append(s.lat)
            s_pos.append(min(140, 22 + 18 * b))
        else:
            xs_neg.append(s.long); ys_neg.append(s.lat)
            s_neg.append(min(140, 22 + 18 * (-b)))

    ax.scatter(xs_ign, ys_ign, s=BASE_S, facecolor=P.textmuted,
               edgecolor=P.tdark, linewidth=0.45, alpha=0.75, zorder=3)
    ax.scatter(xs_pos, ys_pos, s=s_pos, facecolor=P.surplus, edgecolor=P.tdark,
               linewidth=0.45, alpha=0.92, zorder=4)
    ax.scatter(xs_neg, ys_neg, s=s_neg, facecolor=P.deficit, edgecolor=P.tdark,
               linewidth=0.45, alpha=0.92, zorder=4)

    # Fenêtre centrée sur l'enveloppe des stations
    all_lon = [s.long for s in stations if s.number != 0]
    all_lat = [s.lat  for s in stations if s.number != 0]
    pad = 0.004
    ax.set_xlim(min(all_lon) - pad, max(all_lon) + pad)
    ax.set_ylim(min(all_lat) - pad, max(all_lat) + pad)
    ax.set_aspect(1.0 / np.cos(np.radians(np.mean(all_lat))))
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ("top", "right", "bottom", "left"):
        ax.spines[sp].set_visible(False)

    fig.tight_layout(pad=0.2)

    # Sortie PNG haute résolution (DPI=320 → environ 2050×1800 px) :
    # parfaitement net même en zoom et alignement pixel-exact sur la
    # slide où le texte est calé à gauche.
    PRES_FIG_DIR.mkdir(parents=True, exist_ok=True)
    png_path = PRES_FIG_DIR / "targets_map.png"
    pdf_path = PRES_FIG_DIR / "targets_map.pdf"
    fig.savefig(png_path, dpi=320)
    fig.savefig(pdf_path)
    plt.close(fig)
    print(f"  écrit {png_path}")
    print(f"  écrit {pdf_path}")
    print(f"  LaTeX : \\fig[\\linewidth]{{targets_map.png}}")


if __name__ == "__main__":
    main()
