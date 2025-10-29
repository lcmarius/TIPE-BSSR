import sqlite3
from datetime import datetime
from typing import Optional, List, Dict
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

        # Table des stations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_number INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                address TEXT,
                geo_long REAL NOT NULL,
                geo_lat REAL NOT NULL,
                connected BOOLEAN NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table des vélos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bikes (
                bike_id TEXT PRIMARY KEY,
                number INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table pour l'historique des stations (nombre de vélos disponibles)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS station_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_number INTEGER NOT NULL,
                available_bikes INTEGER NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        # Table pour le statut des vélos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bike_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bike_id TEXT NOT NULL,
                status TEXT NOT NULL,
                location_type TEXT NOT NULL,
                station_number INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bike_id) REFERENCES bikes(bike_id),
                FOREIGN KEY (station_number) REFERENCES stations(station_number)
            )
        """)

        # Table pour les trajets réels des vélos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bike_trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bike_id TEXT NOT NULL,
                from_station_number INTEGER,
                to_station_number INTEGER,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP NOT NULL,
                FOREIGN KEY (bike_id) REFERENCES bikes(bike_id),
                FOREIGN KEY (from_station_number) REFERENCES stations(station_number),
                FOREIGN KEY (to_station_number) REFERENCES stations(station_number)
            )
        """)

        # Index pour améliorer les performances
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_station_history_timestamp
            ON station_history(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_station_history_station
            ON station_history(station_number, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_status_bike_id
            ON bike_status(bike_id, timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_trips_bike_id
            ON bike_trips(bike_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bike_trips_time
            ON bike_trips(start_time, end_time)
        """)

        conn.commit()
        self.close()

    def upsert_stations(self, stations: List[Station]):
        """Insert ou update plusieurs stations en batch"""
        conn = self.connect()
        cursor = conn.cursor()

        stations_data = [
            (station.number, station.name, station.capacity, station.address,
             station.long, station.lat, station.connected)
            for station in stations
        ]

        cursor.executemany("""
            INSERT INTO stations (station_number, name, capacity, address, geo_long, geo_lat, connected, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(station_number) DO UPDATE SET
                name = excluded.name,
                capacity = excluded.capacity,
                address = excluded.address,
                geo_long = excluded.geo_long,
                geo_lat = excluded.geo_lat,
                connected = excluded.connected,
                last_updated = CURRENT_TIMESTAMP
        """, stations_data)

        conn.commit()
        self.close()

    def upsert_bikes(self, bikes: List[Bike]):
        """Insert ou update plusieurs vélos en batch"""
        conn = self.connect()
        cursor = conn.cursor()

        bikes_data = []
        for bike in bikes:
            # Convertir created_at en datetime si c'est un timestamp
            if isinstance(bike.created_at, int):
                created_at = datetime.fromtimestamp(bike.created_at)
            else:
                created_at = bike.created_at
            bikes_data.append((bike.id, bike.number, created_at))

        cursor.executemany("""
            INSERT INTO bikes (bike_id, number, created_at, last_updated)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(bike_id) DO UPDATE SET
                number = excluded.number,
                created_at = excluded.created_at,
                last_updated = CURRENT_TIMESTAMP
        """, bikes_data)

        conn.commit()
        self.close()

    def clear(self):
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("PRAGMA foreign_keys = OFF")
        cursor.execute("DROP TABLE IF EXISTS bike_trips")
        cursor.execute("DROP TABLE IF EXISTS bike_status")
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

        if timestamp:
            cursor.execute("""
                INSERT INTO station_history (station_number, available_bikes, timestamp)
                VALUES (?, ?, ?)
            """, (station_number, available_bikes, timestamp))
        else:
            cursor.execute("""
                INSERT INTO station_history (station_number, available_bikes)
                VALUES (?, ?)
            """, (station_number, available_bikes))

        conn.commit()
        self.close()

    def insert_bike_status(self, bike_id: str, status: str, location_type: str,
                          station_number: Optional[int] = None, timestamp: Optional[datetime] = None):
        """Enregistre le statut d'un vélo

        Args:
            bike_id: ID du vélo
            status: AVAILABLE, AVAILABLE_IN_STOCK, TO_BE_REPARED, NOT_RECOGNIZED,
                   MAINTENANCE, STOLEN, DESTROYED, RENTED, REGULATION, SCRAPPED
            location_type: STATION, STORAGE, LOST, RENTED
            station_number: Numéro de station si location_type=STATION
            timestamp: Timestamp personnalisé (optionnel)
        """
        conn = self.connect()
        cursor = conn.cursor()

        if timestamp:
            cursor.execute("""
                INSERT INTO bike_status (bike_id, status, location_type, station_number, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (bike_id, status, location_type, station_number, timestamp))
        else:
            cursor.execute("""
                INSERT INTO bike_status (bike_id, status, location_type, station_number)
                VALUES (?, ?, ?, ?)
            """, (bike_id, status, location_type, station_number))

        conn.commit()
        self.close()

    def insert_bike_trip(self, bike_id: str, from_station_number: Optional[int],
                        to_station_number: Optional[int], start_time: datetime, end_time: datetime):
        """Enregistre un trajet réel d'un vélo entre deux stations"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO bike_trips (bike_id, from_station_number, to_station_number, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        """, (bike_id, from_station_number, to_station_number, start_time, end_time))

        conn.commit()
        self.close()

    def get_last_bike_status(self, bike_id: str) -> Optional[Dict]:
        """Récupère le dernier statut connu d'un vélo"""
        conn = self.connect()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM bike_status
            WHERE bike_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (bike_id,))

        result = cursor.fetchone()
        self.close()
        return dict(result) if result else None

    def get_bike_trips(self, bike_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Récupère l'historique des trajets d'un vélo"""
        conn = self.connect()
        cursor = conn.cursor()

        query = """
            SELECT * FROM bike_trips
            WHERE bike_id = ?
            ORDER BY start_time DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor.execute(query, (bike_id,))
        trips = [dict(row) for row in cursor.fetchall()]
        self.close()
        return trips

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