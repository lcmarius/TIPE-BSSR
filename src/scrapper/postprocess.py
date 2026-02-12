import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CleaningReport:
    jour: date
    mouvements_non_user: int
    valeurs_interpolees: int
    mouvements_orphelins: int
    records_originaux: int
    records_conserves: int
    output_path: str


def _day_bounds(jour: date) -> tuple[str, str]:
    start = f"{jour.isoformat()} 00:00:00"
    end = f"{(jour + timedelta(days=1)).isoformat()} 00:00:00"
    return start, end


def _clean_db(db_path, jour, output_path) -> tuple[int, int, int]:
    shutil.copy2(db_path, output_path)
    conn = sqlite3.connect(output_path)
    start, end = _day_bounds(jour)

    conn.execute("DELETE FROM station_history WHERE timestamp < ? OR timestamp >= ?", (start, end))
    conn.execute("DELETE FROM bike_movements WHERE timestamp < ? OR timestamp >= ?", (start, end))

    nb_non_user = conn.execute(
        "SELECT COUNT(*) FROM bike_movements WHERE source != 'USER'"
    ).fetchone()[0]
    conn.execute("DELETE FROM bike_movements WHERE source != 'USER'")

    nb_interpolated = conn.execute("""
        SELECT COUNT(*) FROM station_history sh
        JOIN stations s ON s.station_number = sh.station_number
        WHERE sh.available_bikes > s.capacity OR sh.available_bikes < 0
    """).fetchone()[0]

    conn.execute("""
        WITH numbered AS (
            SELECT sh.id, s.capacity,
                   LAG(sh.available_bikes) OVER w as prev_bikes,
                   LEAD(sh.available_bikes) OVER w as next_bikes
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

    nb_orphans = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT movement_type,
                   LEAD(movement_type) OVER (PARTITION BY bike_id ORDER BY timestamp) as next_type
            FROM bike_movements
        ) WHERE movement_type = next_type
    """).fetchone()[0]

    conn.execute("""
        DELETE FROM bike_movements WHERE id IN (
            SELECT id FROM (
                SELECT id, movement_type,
                       LEAD(movement_type) OVER (PARTITION BY bike_id ORDER BY timestamp) as next_type
                FROM bike_movements
            ) WHERE movement_type = next_type
        )
    """)

    conn.commit()
    conn.close()

    with sqlite3.connect(output_path) as c:
        c.execute("VACUUM")

    return nb_interpolated, nb_orphans, nb_non_user


def run_postprocess(db_path: str, jour: date, output_dir: str | None = None):
    start, end = _day_bounds(jour)

    conn = sqlite3.connect(db_path)
    records_originaux = conn.execute("""
        SELECT
            (SELECT COUNT(*) FROM station_history WHERE timestamp >= ? AND timestamp < ?) +
            (SELECT COUNT(*) FROM bike_movements WHERE timestamp >= ? AND timestamp < ?)
    """, (start, end, start, end)).fetchone()[0]
    conn.close()

    output_dir = output_dir or os.path.dirname(db_path) or "."
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"clean_{jour.isoformat()}.db")

    nb_interpolated, nb_orphans, nb_non_user = _clean_db(db_path, jour, output_path)

    with sqlite3.connect(output_path) as c:
        records_conserves = c.execute("""
            SELECT (SELECT COUNT(*) FROM station_history) + (SELECT COUNT(*) FROM bike_movements)
        """).fetchone()[0]

    report = CleaningReport(
        jour=jour,
        mouvements_non_user=nb_non_user,
        valeurs_interpolees=nb_interpolated,
        mouvements_orphelins=nb_orphans,
        records_originaux=records_originaux,
        records_conserves=records_conserves,
        output_path=output_path,
    )

    print(f"\n{'=' * 60}")
    print(f" Nettoyage — {report.jour}")
    print(f"{'=' * 60}")
    print(f"  Mouvements non-user supprimés : {report.mouvements_non_user}")
    print(f"  Valeurs interpolées           : {report.valeurs_interpolees}")
    print(f"  Mouvements orphelins supprimés: {report.mouvements_orphelins}")
    print(f"  Records originaux             : {report.records_originaux}")
    print(f"  Records conservés             : {report.records_conserves}")
    print(f"  Fichier exporté               : {report.output_path}")
