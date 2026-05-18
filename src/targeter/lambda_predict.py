# =============================================================================
# Estimation des taux Poisson (lambda_in, lambda_out) pour le targeter Skellam
# =============================================================================
#
# On regroupe les jours en strates (type de jour) × (saison). Pour chaque
# (station, heure, strate), lambda est la moyenne empirique des comptes USER
# journaliers — MLE Poisson sous l'hypothèse iid. Les mouvements TRUCK et
# MAINTENANCE sont écartés : on n'estime que la demande des usagers.
# =============================================================================

import glob
import os
import sqlite3
from datetime import date, datetime
from enum import Enum


# Coupure froid / tempéré : équinoxe de printemps 2026.
SPLIT_DATE: date = date(2026, 3, 20)


class DayType(Enum):
    """Type de jour : ouvré (lundi--vendredi) ou week-end (samedi--dimanche)."""
    WD = 0   # Weekday
    WE = 1   # Weekend


class Season(Enum):
    """Saison : froide (avant l'équinoxe) ou tempérée (à partir de l'équinoxe)."""
    COLD = 0
    WARM = 1


def _day_type(day: date) -> DayType:
    """Type de jour auquel appartient `day`. Convention Python : lundi=0, ..., dimanche=6."""
    return DayType.WE if day.weekday() >= 5 else DayType.WD


def _season(day: date) -> Season:
    """Saison à laquelle appartient `day`, relativement à `SPLIT_DATE`."""
    return Season.WARM if day >= SPLIT_DATE else Season.COLD


def predict_lambdas(station_number: int, when: datetime,
                    clean_dir: str = "data/clean") -> tuple[float, float]:
    """Retourne (lambda_in, lambda_out) pour la station sur le créneau
    `[when.hour, when.hour + 1[` du jour `when.date()`.

    On scanne tous les `clean_*.sql` du répertoire, on retient ceux qui
    tombent dans la même strate (type de jour, saison) que `when.date()`,
    on agrège les ARRIVAL et DEPARTURE USER pour la station et l'heure
    cibles, puis on divise par le nombre de jours retenus.

    Renvoie `(0.0, 0.0)` si aucun jour de la strate n'a été observé.
    """
    target_day_type = _day_type(when.date())
    target_season   = _season(when.date())
    target_hour     = when.hour

    files = sorted(glob.glob(os.path.join(clean_dir, "clean_*.sql")))
    if not files:
        raise FileNotFoundError(f"Aucun clean_*.sql dans {clean_dir}")

    arrivals_total   = 0
    departures_total = 0
    days_in_strate   = 0

    for sql_file in files:
        day = date.fromisoformat(
            os.path.basename(sql_file)[len("clean_"):-len(".sql")])
        if _day_type(day) != target_day_type:
            continue
        if _season(day) != target_season:
            continue
        days_in_strate += 1

        connection = sqlite3.connect(sql_file)
        try:
            rows = connection.execute("""
                SELECT movement_type, COUNT(*) AS count
                FROM bike_movements
                WHERE source = 'USER'
                  AND station_number = ?
                  AND CAST(strftime('%H', timestamp) AS INTEGER) = ?
                GROUP BY movement_type
            """, (station_number, target_hour))
            for movement_type, count in rows:
                if movement_type == "ARRIVAL":
                    arrivals_total   += count
                else:  # DEPARTURE
                    departures_total += count
        finally:
            connection.close()

    if days_in_strate == 0:
        return 0.0, 0.0
    return arrivals_total / days_in_strate, departures_total / days_in_strate
