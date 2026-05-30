# =============================================================================
# Pipeline de nettoyage d'une journée de scrap
# =============================================================================
#
# On opère sur une copie de la DB pour préserver la source brute. Quatre étapes :
#
#   1. Tronquer aux bornes du jour [00:00, 24:00).
#   2. Filtrer les mouvements par source. Par défaut on garde USER + TRUCK et on
#      jette MAINTENANCE (le vélo n'est pas physiquement déplacé pour l'usager).
#      Avec `keep_truck=False`, on ne garde que USER.
#   3. Interpoler les valeurs aberrantes de `available_bikes` (négatives ou au-
#      dessus de la capacité) à partir des voisins temporels de la même station.
#   4. Supprimer les mouvements orphelins : deux ARRIVAL ou deux DEPARTURE
#      consécutifs pour un même vélo trahissent un événement raté.
#
# Sortie : `clean_<YYYY-MM-DD>.sql` dans `output_dir`.
# =============================================================================

import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date

from src.utils.timezone import local_day_bounds_utc


@dataclass
class CleaningReport:
    jour: date
    mouvements_supprimes: int
    mouvements_truck_conserves: int
    valeurs_interpolees: int
    mouvements_orphelins: int
    records_originaux: int
    records_conserves: int
    output_path: str


def _day_bounds(jour: date) -> tuple[str, str]:
    # `jour` est une date locale Paris. On découpe en UTC pour matcher les
    # timestamps stockés en base (UTC naïf). cf. src/utils/timezone.py.
    start_utc, end_utc = local_day_bounds_utc(jour)
    return start_utc.strftime("%Y-%m-%d %H:%M:%S"), end_utc.strftime("%Y-%m-%d %H:%M:%S")


def _truncate_to_day(conn: sqlite3.Connection, jour: date):
    start, end = _day_bounds(jour)
    conn.execute("DELETE FROM station_history  WHERE timestamp < ? OR timestamp >= ?", (start, end))
    conn.execute("DELETE FROM bike_movements   WHERE timestamp < ? OR timestamp >= ?", (start, end))


def _filter_by_source(conn: sqlite3.Connection, keep_truck: bool) -> int:
    """Supprime les mouvements indésirables, retourne le nombre supprimé."""
    delete_clause = "source = 'MAINTENANCE'" if keep_truck else "source != 'USER'"
    nb = conn.execute(f"SELECT COUNT(*) FROM bike_movements WHERE {delete_clause}").fetchone()[0]
    conn.execute(f"DELETE FROM bike_movements WHERE {delete_clause}")
    return nb


# Remplace les `available_bikes` hors [0, capacity] par la moyenne de leurs
# voisins temporels (LAG/LEAD sur la même station).
def _interpolate_aberrant_counts(conn: sqlite3.Connection) -> int:
    """Interpole les valeurs aberrantes, retourne le nombre corrigé."""
    nb = conn.execute("""
        SELECT COUNT(*) FROM station_history sh
        JOIN stations s ON s.station_number = sh.station_number
        WHERE sh.available_bikes > s.capacity OR sh.available_bikes < 0
    """).fetchone()[0]

    conn.execute("""
        WITH numbered AS (
            SELECT sh.id, s.capacity,
                   LAG(sh.available_bikes)  OVER w AS prev_bikes,
                   LEAD(sh.available_bikes) OVER w AS next_bikes
            FROM station_history sh
            JOIN stations s ON s.station_number = sh.station_number
            WHERE sh.available_bikes > s.capacity OR sh.available_bikes < 0
            WINDOW w AS (PARTITION BY sh.station_number ORDER BY sh.timestamp)
        )
        UPDATE station_history SET available_bikes = (
            SELECT MAX(0, MIN(capacity,
                COALESCE(ROUND((prev_bikes + next_bikes) / 2.0), prev_bikes, next_bikes, 0)
            )) FROM numbered WHERE numbered.id = station_history.id
        )
        WHERE id IN (SELECT id FROM numbered)
    """)
    return nb


# Deux ARRIVAL ou deux DEPARTURE consécutifs pour le même vélo trahissent un
# événement intermédiaire raté : on supprime le premier des deux.
def _remove_orphan_movements(conn: sqlite3.Connection) -> int:
    """Supprime les mouvements orphelins, retourne le nombre supprimé."""
    nb = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT movement_type,
                   LEAD(movement_type) OVER (PARTITION BY bike_id ORDER BY timestamp) AS next_type
            FROM bike_movements
        ) WHERE movement_type = next_type
    """).fetchone()[0]

    conn.execute("""
        DELETE FROM bike_movements WHERE id IN (
            SELECT id FROM (
                SELECT id, movement_type,
                       LEAD(movement_type) OVER (PARTITION BY bike_id ORDER BY timestamp) AS next_type
                FROM bike_movements
            ) WHERE movement_type = next_type
        )
    """)
    return nb


def _count_truck_movements(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM bike_movements WHERE source = 'TRUCK'").fetchone()[0]


def _count_day_records(db_path: str, jour: date) -> int:
    start, end = _day_bounds(jour)
    with sqlite3.connect(db_path) as conn:
        return conn.execute("""
            SELECT
                (SELECT COUNT(*) FROM station_history WHERE timestamp >= ? AND timestamp < ?) +
                (SELECT COUNT(*) FROM bike_movements  WHERE timestamp >= ? AND timestamp < ?)
        """, (start, end, start, end)).fetchone()[0]


def _count_all_records(db_path: str) -> int:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT (SELECT COUNT(*) FROM station_history) + (SELECT COUNT(*) FROM bike_movements)"
        ).fetchone()[0]


def run_postprocess(db_path: str, jour: date, output_dir: str | None = None, keep_truck: bool = True) -> CleaningReport:
    records_originaux = _count_day_records(db_path, jour)

    output_dir = output_dir or os.path.dirname(db_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"clean_{jour.isoformat()}.sql")

    # On travaille sur une copie pour ne pas toucher à la DB source.
    shutil.copy2(db_path, output_path)
    conn = sqlite3.connect(output_path)
    try:
        _truncate_to_day(conn, jour)
        nb_supprimes  = _filter_by_source(conn, keep_truck)
        nb_truck      = _count_truck_movements(conn)
        nb_interpoles = _interpolate_aberrant_counts(conn)
        nb_orphelins  = _remove_orphan_movements(conn)
        conn.commit()
    finally:
        conn.close()

    # VACUUM doit s'exécuter hors transaction.
    with sqlite3.connect(output_path) as c:
        c.execute("VACUUM")

    report = CleaningReport(
        jour=jour,
        mouvements_supprimes=nb_supprimes,
        mouvements_truck_conserves=nb_truck,
        valeurs_interpolees=nb_interpoles,
        mouvements_orphelins=nb_orphelins,
        records_originaux=records_originaux,
        records_conserves=_count_all_records(output_path),
        output_path=output_path,
    )
    _print_report(report, keep_truck)
    return report


def _print_report(report: CleaningReport, keep_truck: bool):
    supprime_label = "MAINTENANCE supprimés" if keep_truck else "non-USER supprimés"
    print(f"\n{'=' * 60}")
    print(f" Nettoyage — {report.jour}  (keep_truck={keep_truck})")
    print(f"{'=' * 60}")
    print(f"  Mouvements {supprime_label:<22}: {report.mouvements_supprimes}")
    print(f"  Mouvements TRUCK conservés          : {report.mouvements_truck_conserves}")
    print(f"  Valeurs interpolées                 : {report.valeurs_interpolees}")
    print(f"  Mouvements orphelins supprimés      : {report.mouvements_orphelins}")
    print(f"  Records originaux                   : {report.records_originaux}")
    print(f"  Records conservés                   : {report.records_conserves}")
    print(f"  Fichier exporté                     : {report.output_path}")
