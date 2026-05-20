"""Temps total de rupture par jour — Bicloo Nantes.

Pour chaque journée scrapée, intègre dans le temps le nombre de stations
en rupture (vide ou pleine) et trace une barre empilée :

  * partie rouge  = minutes-station passées en rupture VIDE
  * partie bleue  = minutes-station passées en rupture PLEINE

Une station immobilisée 1 h compte 1 « heure-station » au cumul. Le
total quotidien indique le poids global du déséquilibre sur le réseau,
indépendamment du nombre de stations en rupture à un instant donné.

Échantillonnage station_history toutes les ~5 min, agrégé par tranches
de `grid_min` minutes (intégration trapèze).

Usage :
    python -m renders.rupture_daily
    python -m renders.rupture_daily --grid-min 5
"""

import argparse
import bisect
import glob
import os
import sqlite3
from datetime import date, datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.utils.timezone import utc_naive_to_local
from renders._presstyle import apply_style, palette as P, figsize, save_pres


DEFAULT_CLEAN_DIR = "data/clean"
DEFAULT_OUT_PATH  = "rupture_daily"     # sauvegardé en pres/fig/<>.pdf
DEFAULT_GRID_MIN  = 10

EMPTY_COLOR = P.deficit   # rouge : station vide
FULL_COLOR  = P.depot     # bleu : station pleine
MEAN_COLOR  = P.tdark


def _seconds_of_day(ts: datetime) -> int:
    # `ts` est attendu en heure locale Paris (conversion en amont).
    return ts.hour * 3600 + ts.minute * 60 + ts.second


def _date_from_clean(path: str) -> date:
    base = os.path.basename(path)
    return date.fromisoformat(base[len("clean_"):-len(".sql")])


def _scan_day(path: str, grid_secs: list[int]
              ) -> tuple[int, int] | None:
    """Retourne (minutes-station vides, minutes-station pleines) sur la journée.

    Pour chaque pas de grille on regarde l'état présumé de chaque station
    (dernier sample ≤ pas), on compte combien sont en rupture, on multiplie
    par la durée de la tranche.
    """
    con = sqlite3.connect(path)
    caps = {n: c for n, c in con.execute("SELECT station_number, capacity FROM stations")}
    if not caps:
        con.close()
        return None

    by_station: dict[int, list[tuple[int, int]]] = {}
    for sn, ab, ts in con.execute(
        "SELECT station_number, available_bikes, timestamp "
        "FROM station_history ORDER BY station_number, timestamp"
    ):
        # Stocké en UTC naïf, on bascule en local Paris pour avoir un offset
        # within-day cohérent avec la sémantique "journée locale".
        t = utc_naive_to_local(datetime.fromisoformat(ts))
        by_station.setdefault(sn, []).append((_seconds_of_day(t), ab))
    con.close()

    grid_min = (grid_secs[1] - grid_secs[0]) // 60
    total_empty = 0
    total_full  = 0

    for sn, series in by_station.items():
        cap = caps.get(sn)
        if cap is None or cap <= 0 or not series:
            continue
        ts_list = [t for t, _ in series]
        ab_list = [a for _, a in series]

        for g in grid_secs:
            i = bisect.bisect_right(ts_list, g) - 1
            if i < 0:
                continue
            ab = ab_list[i]
            if ab <= 0:
                total_empty += grid_min
            elif ab >= cap:
                total_full  += grid_min

    return total_empty, total_full


def render(days: list[date], minutes_empty: list[int], minutes_full: list[int],
           out_name: str) -> str:
    apply_style()
    fig, ax = plt.subplots(figsize=figsize("wide"))

    h_empty = [m / 60 for m in minutes_empty]
    h_full  = [m / 60 for m in minutes_full]
    h_total = [e + f for e, f in zip(h_empty, h_full)]

    ax.bar(days, h_empty, color=EMPTY_COLOR, edgecolor="white", linewidth=0.3,
           label="Stations vides", zorder=3)
    ax.bar(days, h_full, bottom=h_empty, color=FULL_COLOR,
           edgecolor="white", linewidth=0.3,
           label="Stations pleines", zorder=3)

    n = len(days)
    mean_total = sum(h_total) / n
    ax.axhline(mean_total, color=MEAN_COLOR, lw=1.2, ls="--",
               label=f"Moyenne : {mean_total:.0f} h-station / jour",
               zorder=4)

    ax.set_xlabel("Date")
    ax.set_ylabel("Heures-station de rupture / jour")
    ax.grid(True, alpha=0.6, axis="y")
    ax.legend(loc="upper left", ncol=3, fontsize=8.5)

    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    plt.setp(ax.get_xticklabels(), rotation=0, ha="center", fontsize=7.5)
    ax.set_ylim(bottom=0)
    ax.margins(x=0.005)

    fig.tight_layout()
    return str(save_pres(fig, out_name))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--clean-dir", default=DEFAULT_CLEAN_DIR)
    p.add_argument("--grid-min", type=int, default=DEFAULT_GRID_MIN,
                   help=f"Pas d'intégration en minutes (défaut: {DEFAULT_GRID_MIN})")
    p.add_argument("--out", default=DEFAULT_OUT_PATH)
    args = p.parse_args()

    files = sorted(glob.glob(os.path.join(args.clean_dir, "clean_*.sql")))
    if not files:
        raise SystemExit(f"Aucun clean_*.sql dans {args.clean_dir}")
    print(f"[{datetime.now():%H:%M:%S}] {len(files)} jours trouvés")

    step = args.grid_min * 60
    grid_secs = list(range(0, 24 * 3600 + 1, step))

    days:    list[date] = []
    minutes_empty: list[int] = []
    minutes_full:  list[int] = []
    for i, f in enumerate(files, 1):
        res = _scan_day(f, grid_secs)
        if res is None:
            continue
        e, fu = res
        days.append(_date_from_clean(f))
        minutes_empty.append(e)
        minutes_full.append(fu)
        if i % 10 == 0 or i == len(files):
            print(f"[{datetime.now():%H:%M:%S}]   {i}/{len(files)} jours traités")

    if not days:
        raise SystemExit("Aucun jour exploitable")

    total_h = sum(minutes_empty + minutes_full) / 60
    n_days = len(days)
    print(f"[{datetime.now():%H:%M:%S}] Total réseau : {total_h:.0f} h-station de rupture "
          f"sur {n_days} jours")
    print(f"[{datetime.now():%H:%M:%S}] Moyenne quotidienne : {total_h/n_days:.0f} h-station / jour")

    print(f"[{datetime.now():%H:%M:%S}] Rendu...")
    path = render(days, minutes_empty, minutes_full, args.out)
    print(f"[{datetime.now():%H:%M:%S}] OK — {path}")


if __name__ == "__main__":
    main()
