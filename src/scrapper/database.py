import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from src.objects.bike import Bike
from src.objects.station import Station


class Database:
    """Gestion de la base de données SQLite pour le scraping Bicloo"""

    def __init__(self, db_path: str, clear: bool = False):
        self.db_path = db_path
        self.conn = None
        self.init_database(clear)

    def connect(self):
        """Établit la connexion à la base de données"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self.conn

    def close(self):
        """Ferme la connexion à la base de données"""
        if self.conn:
            self.conn.close()

    def init_database(self, clear: bool = False):
        """Initialise les tables de la base de données"""
        conn = self.connect()
        cursor = conn.cursor()

        if clear:
            self.clear()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
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
            CREATE INDEX IF NOT EXISTS idx_station_history_timestamp
            ON station_history(timestamp)
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
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_movements_type
            ON bike_movements(movement_type, timestamp)
        """)

        conn.commit()
        self.close()

    def upsert_stations(self, stations: List[Station]):
        """Insert ou update plusieurs stations en batch"""
        conn = self.connect()
        cursor = conn.cursor()

        stations_data = [
            (station.number, station.name, station.capacity, station.lat, station.long)
            for station in stations
        ]

        cursor.executemany("""
            INSERT INTO stations (station_number, name, capacity, geo_lat, geo_long)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(station_number) DO UPDATE SET
                name = excluded.name,
                capacity = excluded.capacity,
                geo_lat = excluded.geo_lat,
                geo_long = excluded.geo_long
        """, stations_data)

        conn.commit()
        self.close()

    def upsert_bikes(self, bikes: List[Bike]):
        """Insert ou update plusieurs vélos en batch"""
        conn = self.connect()
        cursor = conn.cursor()

        bikes_data = [(bike.id, bike.number) for bike in bikes]

        cursor.executemany("""
            INSERT INTO bikes (bike_id, number)
            VALUES (?, ?)
            ON CONFLICT(bike_id) DO UPDATE SET
                number = excluded.number
        """, bikes_data)

        conn.commit()
        self.close()

    def clear(self):
        """Supprime toutes les tables"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DROP TABLE IF EXISTS bike_movements")
        cursor.execute("DROP TABLE IF EXISTS station_history")
        cursor.execute("DROP TABLE IF EXISTS bikes")
        cursor.execute("DROP TABLE IF EXISTS stations")
        cursor.execute("PRAGMA foreign_keys = ON")

        conn.commit()
        self.close()

    def insert_station_history(self, station_number: int, available_bikes: int, timestamp: Optional[datetime] = None):
        """Enregistre le nombre de vélos disponibles dans une station à un instant T"""
        conn = self.connect()
        cursor = conn.cursor()

        if timestamp is None:
            timestamp = datetime.now()

        cursor.execute("""
            INSERT INTO station_history (station_number, available_bikes, timestamp)
            VALUES (?, ?, ?)
        """, (station_number, available_bikes, timestamp))

        conn.commit()
        self.close()

    def insert_station_history_batch(self, history_records: List[Tuple[int, int, datetime]]):
        """Insère plusieurs enregistrements d'historique de station en batch

        Args:
            history_records: Liste de tuples (station_number, available_bikes, timestamp)
        """
        if not history_records:
            return

        conn = self.connect()
        cursor = conn.cursor()

        cursor.executemany("""
            INSERT INTO station_history (station_number, available_bikes, timestamp)
            VALUES (?, ?, ?)
        """, history_records)

        conn.commit()
        self.close()

    def insert_movement(self, bike_id: str, station_number: int, movement_type: str, timestamp: datetime):
        """Enregistre un mouvement de vélo (ARRIVAL ou DEPARTURE)"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO bike_movements (bike_id, station_number, movement_type, timestamp)
            VALUES (?, ?, ?, ?)
        """, (bike_id, station_number, movement_type, timestamp))

        conn.commit()
        self.close()

    def insert_movements_batch(self, movements: List[Tuple[str, int, str, datetime]]):
        """Insère plusieurs mouvements en batch

        Args:
            movements: Liste de tuples (bike_id, station_number, movement_type, timestamp)
        """
        conn = self.connect()
        cursor = conn.cursor()

        cursor.executemany("""
            INSERT INTO bike_movements (bike_id, station_number, movement_type, timestamp)
            VALUES (?, ?, ?, ?)
        """, movements)

        conn.commit()
        self.close()

    def get_movements_count(self, station_number: int, movement_type: str,
                           start_time: datetime, end_time: datetime) -> int:
        """Compte le nombre de mouvements d'un type pour une station sur une période"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) as count FROM bike_movements
            WHERE station_number = ?
              AND movement_type = ?
              AND timestamp >= ?
              AND timestamp <= ?
        """, (station_number, movement_type, start_time, end_time))

        result = cursor.fetchone()
        self.close()
        return result['count'] if result else 0

    def get_bike_location(self, bike_id: str) -> Optional[int]:
        """Récupère la dernière station connue d'un vélo"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT station_number FROM bike_movements
            WHERE bike_id = ?
              AND movement_type = 'ARRIVAL'
            ORDER BY timestamp DESC
            LIMIT 1
        """, (bike_id,))

        result = cursor.fetchone()
        self.close()
        return result['station_number'] if result else None

    def get_movements(self, station_number: int, start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None, limit: Optional[int] = None) -> List[Dict]:
        """Récupère les mouvements d'une station"""
        conn = self.connect()
        cursor = conn.cursor()

        query = "SELECT * FROM bike_movements WHERE station_number = ?"
        params = [station_number]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, params)
        movements = [dict(row) for row in cursor.fetchall()]
        self.close()
        return movements

    def get_station_history(self, station_number: int, start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> List[Dict]:
        """Récupère l'historique d'une station"""
        conn = self.connect()
        cursor = conn.cursor()

        query = "SELECT * FROM station_history WHERE station_number = ?"
        params = [station_number]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)

        query += " ORDER BY timestamp DESC"

        cursor.execute(query, params)
        history = [dict(row) for row in cursor.fetchall()]
        self.close()
        return history

    def get_all_stations(self) -> List[Dict]:
        """Récupère toutes les stations"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stations")
        stations = [dict(row) for row in cursor.fetchall()]
        self.close()
        return stations

    def get_all_bikes(self) -> List[Dict]:
        """Récupère tous les vélos"""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bikes")
        bikes = [dict(row) for row in cursor.fetchall()]
        self.close()
        return bikes
