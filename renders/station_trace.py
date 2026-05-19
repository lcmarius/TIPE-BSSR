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
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt


SOURCE_DIR = Path("data/source")
CLEAN_DIR  = Path("data/clean")
OUT        = Path("renders/station_trace.png")

# Palette presentation
COL_RAW   = "#C0392B"
COL_CLEAN = "#27AE60"
COL_CAP   = "#6C7A89"
TEXT_DARK = "#23373B"


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
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT timestamp, available_bikes FROM station_history "
        "WHERE station_number = ? AND DATE(timestamp) = ? "
        "ORDER BY timestamp",
        (station, date_str),
    ).fetchall()
    cap, name = conn.execute(
        "SELECT capacity, name FROM stations WHERE station_number = ?",
        (station,),
    ).fetchone()
    conn.close()
    times  = [datetime.fromisoformat(t) for t, _ in rows]
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

    # Index des aberrants (sur la brute, hors [0, capacite])
    aberr_idx = [i for i, v in enumerate(v_raw) if v < 0 or v > cap]

    fig, ax = plt.subplots(figsize=(8.8, 4.2))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    # Bande [0, capacite] = domaine admissible
    ax.axhspan(0, cap, facecolor="#eaf3ec", edgecolor="none",
               alpha=0.6, zorder=0)
    ax.axhline(cap, color=COL_CAP, lw=1.0, ls="--", alpha=0.7, zorder=1)
    ax.text(t_raw[-1], cap, f" capacité = {cap}",
            ha="right", va="bottom", fontsize=9, color=COL_CAP)
    ax.axhline(0, color=COL_CAP, lw=1.0, ls="--", alpha=0.7, zorder=1)

    # Courbe brute (rouge) + courbe corrigee (verte)
    ax.plot(t_raw, v_raw, color=COL_RAW, lw=1.6, alpha=0.85,
            label="brute", zorder=3)
    ax.plot(t_cln, v_cln, color=COL_CLEAN, lw=1.6, alpha=0.95,
            label="corrigée", zorder=4)

    # Marqueurs sur les aberrants
    if aberr_idx:
        ax.scatter([t_raw[i] for i in aberr_idx],
                   [v_raw[i] for i in aberr_idx],
                   s=42, facecolor="none", edgecolor=COL_RAW, lw=1.6,
                   zorder=5, label=f"{len(aberr_idx)} valeurs aberrantes")

    ax.set_xlabel("heure", fontsize=11, color=TEXT_DARK)
    ax.set_ylabel("vélos disponibles", fontsize=11, color=TEXT_DARK)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))

    ax.set_title(f"Station {args.station} — {name}   ({args.date})",
                 fontsize=12, color=TEXT_DARK, loc="left")

    ax.grid(True, alpha=0.3)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    ax.legend(loc="upper left", frameon=False, fontsize=10)

    fig.tight_layout()
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=180, bbox_inches="tight")
    print(f"écrit : {OUT}")


if __name__ == "__main__":
    main()
