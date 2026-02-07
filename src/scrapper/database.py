import os
import shutil
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from src.objects.bike import Bike
from src.objects.station import Station


def archive_db(db_path: str):
    """Archive la DB actuelle dans un sous-dossier archives/ avec la date/heure."""
    if not os.path.exists(db_path):
        return
    db_dir = os.path.dirname(db_path) or "."
    archive_dir = os.path.join(db_dir, "archives")
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_path = os.path.join(archive_dir, f"{timestamp}.sql")
    shutil.move(db_path, archive_path)
    print(f"Session précédente archivée → {archive_path}")


class Database:
    """Gestion de la base de données SQLite pour le scraping Bicloo"""

    def __init__(self, db_path: str, clear: bool = False):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                address TEXT NOT NULL DEFAULT '',
                geo_lat REAL NOT NULL,
                geo_long REAL NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bikes (
                bike_id TEXT PRIMARY KEY,
                number INTEGER NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bike_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bike_id TEXT NOT NULL,
                station_number INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (bike_id) REFERENCES bikes(bike_id),
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS station_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_number INTEGER NOT NULL,
                available_bikes INTEGER NOT NULL,
                timestamp DATETIME NOT NULL,
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_station_history_station
            ON station_history(station_number, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_movements_bike_id
            ON bike_movements(bike_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_movements_station
            ON bike_movements(station_number, timestamp)
        """)

        self.conn.commit()

    """
    ---------------------------
    Requêtes d'écriture
    ---------------------------
    """

    def upsert_stations(self, stations: List[Station]):
        self.conn.executemany("""
            INSERT INTO stations (station_number, name, capacity, address, geo_lat, geo_long)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(station_number) DO UPDATE SET
                name = excluded.name,
                capacity = excluded.capacity,
                address = excluded.address,
                geo_lat = excluded.geo_lat,
                geo_long = excluded.geo_long
        """, [(s.number, s.name, s.capacity, s.address, s.lat, s.long) for s in stations])
        self.conn.commit()

    def upsert_bikes(self, bikes: List[Bike]):
        self.conn.executemany("""
            INSERT INTO bikes (bike_id, number)
            VALUES (?, ?)
            ON CONFLICT(bike_id) DO UPDATE SET
                number = excluded.number
        """, [(b.id, b.number) for b in bikes])
        self.conn.commit()

    def insert_movements_batch(self, movements: List[Tuple[str, int, str, datetime]]):
        self.conn.executemany("""
            INSERT INTO bike_movements (bike_id, station_number, movement_type, timestamp)
            VALUES (?, ?, ?, ?)
        """, movements)
        self.conn.commit()

    def insert_station_history_batch(self, records: List[Tuple[int, int, datetime]]):
        if not records:
            return
        self.conn.executemany("""
            INSERT INTO station_history (station_number, available_bikes, timestamp)
            VALUES (?, ?, ?)
        """, records)
        self.conn.commit()


    """
    ---------------------------
    Requêtes de lecture
    ---------------------------
    """

    def get_movements(self, station_number: int, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None, limit: Optional[int] = None) -> List[Dict]:
        query = "SELECT * FROM bike_movements WHERE station_number = ?"
        params: list = [station_number]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_station_history(self, station_number: int, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> List[Dict]:
        query = "SELECT * FROM station_history WHERE station_number = ?"
        params: list = [station_number]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC"

        cursor = self.conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_all_stations(self) -> List[Dict]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM stations").fetchall()]

    def get_all_bikes(self) -> List[Dict]:
        return [dict(row) for row in self.conn.execute("SELECT * FROM bikes").fetchall()]
