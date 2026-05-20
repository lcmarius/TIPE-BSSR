"""Trace `available_bikes(t)` brute vs corrigée pour une station/un jour (slide 15).

Illustre l'étape d'interpolation des valeurs aberrantes du post-process :
les snapshots où `available_bikes` sort de [0, capacité] sont corrigés par
moyenne des voisins temporels. La courbe rouge (brute) montre les pics ;
la courbe verte (corrigée) les écrête.

Usage :
    python -m renders.station_trace
    python -m renders.station_trace --station 73 --date 2026-05-07
"""

import argparse
import sqlite3
from datetime import date as date_cls, datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.utils.timezone import local_day_bounds_utc, utc_naive_to_local
from renders._presstyle import apply_style, palette as P, figsize, save_pres


SOURCE_DIR = Path("data/source")
CLEAN_DIR  = Path("data/clean")
OUT_NAME   = "station_trace"     # → pres/fig/station_trace.pdf

COL_RAW   = P.deficit
COL_CLEAN = P.surplus
COL_CAP   = P.textmuted
TEXT_DARK = P.tdark


def find_source_db(date_str: str) -> Path:
    """Trouve la DB source qui contient `date_str` (format YYYY-MM-DD)."""
    target = datetime.strptime(date_str, "%Y-%m-%d").date()
    for db in sorted(SOURCE_DIR.glob("source_*.sql")):
        stem = db.stem.replace("source_", "")
        if "_to_" in stem:
            start_s, end_s = stem.split("_to_")
            start = datetime.strptime(start_s, "%Y-%m-%d").date()
            end   = datetime.strptime(end_s,   "%Y-%m-%d").date()
        else:
            start = end = datetime.strptime(stem, "%Y-%m-%d").date()
        if start <= target <= end:
            return db
    raise FileNotFoundError(f"Aucune source ne couvre {date_str}")


def load_trace(db: Path, station: int, date_str: str):
    # `date_str` est une date locale Paris. On filtre les timestamps (UTC en
    # base) sur la fenêtre UTC correspondante, puis on convertit en local
    # pour l'affichage. cf. src/utils/timezone.py.
    jour = date_cls.fromisoformat(date_str)
    start_utc, end_utc = local_day_bounds_utc(jour)
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT timestamp, available_bikes FROM station_history "
        "WHERE station_number = ? AND timestamp >= ? AND timestamp < ? "
        "ORDER BY timestamp",
        (station,
         start_utc.strftime("%Y-%m-%d %H:%M:%S"),
         end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()
    cap, name = conn.execute(
        "SELECT capacity, name FROM stations WHERE station_number = ?",
        (station,),
    ).fetchone()
    conn.close()
    times  = [utc_naive_to_local(datetime.fromisoformat(t)) for t, _ in rows]
    values = [v for _, v in rows]
    return times, values, cap, name


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--station", type=int, default=73,
                   help="station_number (defaut: 73, exemple a 5 aberrants)")
    p.add_argument("--date", default="2026-05-07",
                   help="YYYY-MM-DD (defaut: 2026-05-07)")
    args = p.parse_args()

    src_db   = find_source_db(args.date)
    clean_db = CLEAN_DIR / f"clean_{args.date}.sql"
    if not clean_db.exists():
        raise FileNotFoundError(f"Pas de clean DB pour {args.date}")

    t_raw, v_raw, cap, name = load_trace(src_db, args.station, args.date)
    t_cln, v_cln, _,   _    = load_trace(clean_db, args.station, args.date)

    aberr_idx = [i for i, v in enumerate(v_raw) if v < 0 or v > cap]

    apply_style()
    # Plus large et plus haut pour la slide 17 ; la légende sera posée
    # à droite, hors du panneau de tracé.
    fig, ax = plt.subplots(figsize=(7.6, 3.6))

    # Bande [0, capacité] = domaine admissible (vert très pâle)
    ax.axhspan(0, cap, facecolor=COL_CLEAN, edgecolor="none",
               alpha=0.10, zorder=0)
    # Trait de capacité — la valeur est rappelée dans la légende externe.
    ax.axhline(cap, color=COL_CAP, lw=0.9, ls="--", alpha=0.7, zorder=1,
               label=f"capacité = {cap}")
    ax.axhline(0, color=COL_CAP, lw=0.9, ls="--", alpha=0.7, zorder=1)

    ax.plot(t_raw, v_raw, color=COL_RAW, lw=1.4, alpha=0.85,
            label="brute", zorder=3)
    ax.plot(t_cln, v_cln, color=COL_CLEAN, lw=1.4, alpha=0.95,
            label="corrigée", zorder=4)

    if aberr_idx:
        ax.scatter([t_raw[i] for i in aberr_idx],
                   [v_raw[i] for i in aberr_idx],
                   s=36, facecolor="none", edgecolor=COL_RAW, lw=1.4,
                   zorder=5, label=f"{len(aberr_idx)} valeurs aberrantes")

    ax.set_xlabel("heure")
    ax.set_ylabel("vélos disponibles")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))

    ax.set_title(f"Station {name}   ({args.date})", loc="left")

    # Légende à droite, hors de la zone de tracé : évite d'écraser
    # les courbes et les valeurs aberrantes près du haut du graphe.
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5),
              frameon=False, handlelength=2.2, handletextpad=0.6,
              borderaxespad=0)
    fig.tight_layout(rect=[0, 0, 0.80, 1])
    save_pres(fig, OUT_NAME)


if __name__ == "__main__":
    main()
