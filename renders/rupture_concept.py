"""Schéma conceptuel du temps de rupture (slide Motivation).

Trace `available_bikes(t)` pour UNE vraie station-jour Bicloo Nantes
qui présente un beau pattern : vide le matin, pleine l'après-midi.
Visualise concrètement les périodes pendant lesquelles la station est
saturée (vide / pleine).

Choix : Sainte Élisabeth (sn=17, capacité 14) le lundi 16 mars 2026.
Pattern centre-ville classique. Cf. exploration des donnés clean.

Produit : pres/fig/rupture_concept.pdf
"""

import sqlite3
from datetime import datetime

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.utils.timezone import local_day_bounds_utc, utc_naive_to_local
from renders._presstyle import apply_style, palette as P, save_pres


# Station-jour sélectionné pour son pattern lisible et son équilibre vide/plein.
STATION_NUMBER = 17       # SAINTE ÉLISABETH
DATE_ISO       = "2026-03-16"   # lundi
CLEAN_DIR      = "data/clean"


def _load_trace(date_iso: str, sn: int):
    jour = datetime.fromisoformat(date_iso).date()
    start_utc, end_utc = local_day_bounds_utc(jour)
    conn = sqlite3.connect(f"{CLEAN_DIR}/clean_{date_iso}.sql")
    rows = conn.execute(
        "SELECT timestamp, available_bikes FROM station_history "
        "WHERE station_number = ? AND timestamp >= ? AND timestamp < ? "
        "ORDER BY timestamp",
        (sn,
         start_utc.strftime("%Y-%m-%d %H:%M:%S"),
         end_utc.strftime("%Y-%m-%d %H:%M:%S")),
    ).fetchall()
    cap = conn.execute(
        "SELECT capacity FROM stations WHERE station_number = ?", (sn,)
    ).fetchone()[0]
    conn.close()
    times  = [utc_naive_to_local(datetime.fromisoformat(t)) for t, _ in rows]
    values = [v for _, v in rows]
    return times, values, cap


def main():
    times, values, cap = _load_trace(DATE_ISO, STATION_NUMBER)

    apply_style()
    # Aspect 1.45 : à col 0.58×\linewidth, hauteur d'inclusion == celle de
    # asymmetry_morning (aspect 1.0) en col 0.40×\linewidth.
    fig, ax = plt.subplots(figsize=(5.0, 3.45))

    # Convention couleur cohérente avec asymmetry_morning (RdBu_r) :
    #   ROUGE = station pleine (gagnées de vélos)  →  P.deficit
    #   BLEU  = station vide   (perdues de vélos)  →  P.depot
    COL_FULL  = P.deficit
    COL_EMPTY = P.depot

    # Bande "[0, capacité]" claire en fond, lignes-repère discrètes
    ax.axhspan(0, cap, color=P.tlight, alpha=0.55, zorder=0)
    ax.axhline(0,   color=COL_EMPTY, lw=0.8, ls="--", alpha=0.7)
    ax.axhline(cap, color=COL_FULL,  lw=0.8, ls="--", alpha=0.7)

    # Bandes colorées : bleu sous la courbe = vide, rouge au-dessus = plein.
    band_h = max(1.0, cap * 0.08)
    is_empty = [v <= 0   for v in values]
    is_full  = [v >= cap for v in values]
    ax.fill_between(times, 0, band_h, where=is_empty, step="post",
                    color=COL_EMPTY, alpha=0.45, linewidth=0, zorder=2)
    ax.fill_between(times, cap - band_h, cap, where=is_full, step="post",
                    color=COL_FULL,  alpha=0.45, linewidth=0, zorder=2)

    # Courbe
    ax.plot(times, values, color=P.tdark, lw=1.4, zorder=4)

    # Annotations directionnelles
    ax.text(0.02, 0.10, "station vide",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=8,
            color=COL_EMPTY, fontweight="bold", zorder=5)
    # « station pleine » : juste AU-DESSUS de la ligne y=capacité,
    # côté droit pour éviter la collision avec le label « capacité = ».
    ax.text(times[-1], cap + band_h * 0.35, "station pleine",
            ha="right", va="bottom", fontsize=8,
            color=COL_FULL, fontweight="bold", zorder=5)
    ax.text(times[0], cap + band_h * 0.35, f"capacité = {cap}",
            ha="left", va="bottom", fontsize=7, color=COL_FULL)

    ax.set_title("Station Sainte Élisabeth (centre-ville)\nlundi 16 mars 2026",
                 fontsize=9, fontweight="bold", pad=5, loc="center")
    ax.set_xlabel("Heure de la journée")
    ax.set_ylabel("Vélos disponibles")
    # Marge haute resserrée : labels juste au-dessus de la courbe, pas
    # d'espace mort en haut du cadre.
    ax.set_ylim(-band_h * 0.6, cap + band_h * 0.95)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%-Hh"))

    fig.tight_layout()
    save_pres(fig, "rupture_concept")


if __name__ == "__main__":
    main()
