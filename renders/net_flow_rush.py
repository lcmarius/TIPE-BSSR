"""Carte du flux net usager pendant le rush — Bicloo Nantes.

Pour chaque station, compte sur une fenêtre horaire fixe le **solde
des mouvements USER** (arrivées − départs) moyenné sur les jours ouvrés.

  * solde > 0  → la station GAGNE des vélos pendant la fenêtre (destination)
  * solde < 0  → la station PERD des vélos pendant la fenêtre (origine)

Le résultat est centré sur 0 avec une colormap divergente RdYlGn ; les
extrémités sont saturées à un percentile (par défaut 95 %) pour éviter
qu'une station extrême écrase visuellement les autres.

Usage :
    python -m renders.net_flow_rush                          # 7h-9h matin
    python -m renders.net_flow_rush --window 17 19           # 17h-19h soir
    python -m renders.net_flow_rush --window 7 9 --out renders/net_flow_morning.png
"""

import argparse
import glob
import os
import sqlite3
from datetime import date, datetime

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection

from src.utils.timezone import local_to_utc_naive
from renders._presstyle import apply_style, palette as P, figsize, save_pres


DEFAULT_CLEAN_DIR = "data/clean"
DEFAULT_GRAPHML   = "data/nantes_graph.graphml"
DEFAULT_OUT_NAME  = "asymmetry_morning"        # → pres/fig/<>.pdf
DEFAULT_WINDOW    = (7, 9)


def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def _date_from_clean(path: str) -> date:
    base = os.path.basename(path)
    return date.fromisoformat(base[len("clean_"):-len(".sql")])


def _load_stations(path: str) -> dict[int, tuple[float, float, int, str]]:
    con = sqlite3.connect(path)
    rows = con.execute(
        "SELECT station_number, geo_lat, geo_long, capacity, name FROM stations"
    ).fetchall()
    con.close()
    return {n: (lat, lon, cap, name) for n, lat, lon, cap, name in rows}


def _scan_day(path: str, h_start: int, h_end: int) -> dict[int, int]:
    """station_number → (n_arrivals − n_departures) USER sur [h_start, h_end[
    en heure LOCALE Paris (les bornes sont converties en UTC pour le filtre SQL).
    """
    d = _date_from_clean(path)
    start_local = datetime(d.year, d.month, d.day, h_start, 0, 0)
    end_local   = datetime(d.year, d.month, d.day, h_end,   0, 0)
    t_start = local_to_utc_naive(start_local).strftime("%Y-%m-%d %H:%M:%S")
    t_end   = local_to_utc_naive(end_local).strftime("%Y-%m-%d %H:%M:%S")

    con = sqlite3.connect(path)
    rows = con.execute("""
        SELECT station_number, movement_type, COUNT(*)
        FROM bike_movements
        WHERE source = 'USER'
          AND timestamp >= ? AND timestamp < ?
        GROUP BY station_number, movement_type
    """, (t_start, t_end)).fetchall()
    con.close()

    net: dict[int, int] = {}
    for sn, mtype, n in rows:
        delta = n if mtype == "ARRIVAL" else -n
        net[sn] = net.get(sn, 0) + delta
    return net


def render(stations: dict[int, tuple[float, float, int, str]],
           avg_net: dict[int, float], n_days: int,
           window: tuple[int, int], graphml_path: str | None,
           saturate_pct: float, out_name: str) -> str:
    apply_style()
    fig, ax = plt.subplots(figsize=figsize("map"))
    ax.grid(False)
    # `graphml_path` est ignoré : on ne dessine pas la carte routière en
    # arrière-plan, seules les stations comptent ; le placement géographique
    # (lat/long) suffit à reconnaître Nantes.

    xs, ys, cs, sizes = [], [], [], []
    for sn, (lat, lon, cap, _) in stations.items():
        v = avg_net.get(sn)
        if v is None:
            continue
        xs.append(lon)
        ys.append(lat)
        cs.append(v)
        sizes.append(22 + 3 * cap)
    if not xs:
        raise SystemExit("Aucune donnée à tracer.")

    abs_vals = np.abs(cs)
    vmax = float(np.percentile(abs_vals, saturate_pct))
    if vmax <= 0:
        vmax = float(max(abs_vals) or 1.0)
    cmap = plt.get_cmap("RdBu_r")
    sc = ax.scatter(xs, ys, c=cs, cmap=cmap, vmin=-vmax, vmax=+vmax,
                    s=sizes, edgecolor=P.tdark, linewidth=0.4,
                    alpha=0.95, zorder=3)

    pad = 0.005
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.set_aspect(1.0 / np.cos(np.radians(np.mean(ys))))
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ("top", "right", "bottom", "left"):
        ax.spines[sp].set_visible(False)

    h_start, h_end = window
    ax.set_title(f"Gain de vélos par station entre {h_start}h et {h_end}h\n"
                 f"en moyenne sur {n_days} jours",
                 fontsize=9, fontweight="bold", pad=5)

    cax = ax.inset_axes([0.02, 0.025, 0.36, 0.022])
    cb = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=8, length=2.5, pad=2)
    cb.set_ticks([-vmax, 0, +vmax])
    cb.set_ticklabels([f"−{vmax:.0f}\nperdus", "0", f"+{vmax:.0f}\ngagnés"])

    fig.subplots_adjust(left=0, right=1, top=0.94, bottom=0)
    return str(save_pres(fig, out_name))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--clean-dir", default=DEFAULT_CLEAN_DIR)
    p.add_argument("--graphml", default=DEFAULT_GRAPHML)
    p.add_argument("--window", nargs=2, type=int, default=list(DEFAULT_WINDOW),
                   metavar=("H_START", "H_END"),
                   help=f"Fenêtre horaire en heures (défaut: {DEFAULT_WINDOW[0]} {DEFAULT_WINDOW[1]})")
    p.add_argument("--saturate", type=float, default=95.0,
                   help="Percentile de saturation de l'échelle (défaut: 95)")
    p.add_argument("--weekends-only", action="store_true")
    p.add_argument("--out", default=DEFAULT_OUT_NAME,
                   help="Nom de la figure dans pres/fig/ (sans extension)")
    args = p.parse_args()

    files = sorted(glob.glob(os.path.join(args.clean_dir, "clean_*.sql")))
    if not files:
        raise SystemExit(f"Aucun clean_*.sql dans {args.clean_dir}")
    print(f"[{datetime.now():%H:%M:%S}] {len(files)} jours trouvés")

    stations: dict[int, tuple[float, float, int, str]] = {}
    for f in files:
        for sn, info in _load_stations(f).items():
            stations.setdefault(sn, info)
    print(f"[{datetime.now():%H:%M:%S}] {len(stations)} stations (union)")

    sums:   dict[int, float] = {sn: 0.0 for sn in stations}
    counts: dict[int, int]   = {sn: 0   for sn in stations}
    n_days_kept = 0
    h_start, h_end = args.window
    for i, f in enumerate(files, 1):
        d = _date_from_clean(f)
        keep = (not _is_weekday(d)) if args.weekends_only else _is_weekday(d)
        if not keep:
            continue
        per_station = _scan_day(f, h_start, h_end)
        for sn, net in per_station.items():
            if sn in sums:
                sums[sn]   += net
                counts[sn] += 1
        n_days_kept += 1
        if i % 20 == 0 or i == len(files):
            print(f"[{datetime.now():%H:%M:%S}]   {i}/{len(files)} fichiers parcourus "
                  f"({n_days_kept} retenus)")

    avg = {sn: sums[sn] / counts[sn] for sn in stations if counts[sn] > 0}
    extremes = sorted(avg.values())
    print(f"[{datetime.now():%H:%M:%S}] flux net /jour ouvré — extrêmes : "
          f"{extremes[0]:+.1f}  …  {extremes[-1]:+.1f}")
    n_dest = sum(1 for v in avg.values() if v > 2.0)
    n_orig = sum(1 for v in avg.values() if v < -2.0)
    print(f"[{datetime.now():%H:%M:%S}]   {n_orig} stations « origine » (< −2 vélos), "
          f"{n_dest} « destination » (> +2 vélos)")

    print(f"[{datetime.now():%H:%M:%S}] Rendu...")
    path = render(stations, avg, n_days_kept, (h_start, h_end),
                  args.graphml, args.saturate, args.out)
    print(f"[{datetime.now():%H:%M:%S}] OK — {path}")


if __name__ == "__main__":
    main()
