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
                status TEXT NOT NULL,
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
            bikes_data.append((bike.id, bike.number, bike.status, created_at))

        cursor.executemany("""
            INSERT INTO bikes (bike_id, number, status, created_at, last_updated)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(bike_id) DO UPDATE SET
                number = excluded.number,
                status = excluded.status,
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


    def dump_daily_data(self, target_date: Optional[datetime] = None, output_dir: str = "dumps") -> str:
        """
        Dump les données de la base pour une journée spécifique dans un fichier SQL.
        :param target_date: La date cible pour le dump (par défaut aujourd'hui)
        :param output_dir: Le répertoire de sortie pour le fichier dump
        :return: Le chemin du fichier dump généré
        """
        import os

        if target_date is None:
            target_date = datetime.now()

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        os.makedirs(output_dir, exist_ok=True)

        filename = f"dump_{target_date.strftime('%Y-%m-%d')}.sql"
        filepath = os.path.join(output_dir, filename)

        conn = self.connect()
        cursor = conn.cursor()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"-- Dump Bicloo du {target_date.strftime('%Y-%m-%d')}\n")
            f.write(f"-- Généré le {datetime.now().isoformat()}\n\n")

            cursor.execute("""
                           SELECT *
                           FROM stations
                           WHERE date(last_updated) <= date(?)
                           """, (day_end,))
            stations = cursor.fetchall()

            if stations:
                f.write("-- Stations\n")
                for row in stations:
                    f.write(
                        f"INSERT OR REPLACE INTO stations (station_number, name, capacity, address, geo_long, geo_lat, connected, last_updated) VALUES ({row['station_number']}, '{row['name'].replace(chr(39), chr(39) + chr(39))}', {row['capacity']}, '{(row['address'] or '').replace(chr(39), chr(39) + chr(39))}', {row['geo_long']}, {row['geo_lat']}, {row['connected']}, '{row['last_updated']}');\n")
                f.write("\n")

            cursor.execute("""
                           SELECT *
                           FROM bikes
                           WHERE date(created_at) <= date(?)
                           """, (day_end,))
            bikes = cursor.fetchall()

            if bikes:
                f.write("-- Vélos\n")
                for row in bikes:
                    f.write(
                        f"INSERT OR REPLACE INTO bikes (bike_id, number, status, created_at, last_updated) VALUES ('{row['bike_id']}', {row['number']}, '{row['status']}', '{row['created_at']}', '{row['last_updated']}');\n")
                f.write("\n")

            cursor.execute("""
                           SELECT *
                           FROM station_history
                           WHERE timestamp >= ?
                             AND timestamp <= ?
                           """, (day_start, day_end))
            history = cursor.fetchall()

            if history:
                f.write("-- Historique des stations\n")
                for row in history:
                    f.write(
                        f"INSERT INTO station_history (station_number, available_bikes, timestamp) VALUES ({row['station_number']}, {row['available_bikes']}, '{row['timestamp']}');\n")
                f.write("\n")

            cursor.execute("""
                           SELECT *
                           FROM bike_trips
                           WHERE (start_time >= ? AND start_time <= ?)
                              OR (end_time >= ? AND end_time <= ?)
                           """, (day_start, day_end, day_start, day_end))
            trips = cursor.fetchall()

            if trips:
                f.write("-- Trajets\n")
                for row in trips:
                    from_station = row['from_station_number'] if row['from_station_number'] else 'NULL'
                    to_station = row['to_station_number'] if row['to_station_number'] else 'NULL'
                    f.write(
                        f"INSERT INTO bike_trips (bike_id, from_station_number, to_station_number, start_time, end_time) VALUES ('{row['bike_id']}', {from_station}, {to_station}, '{row['start_time']}', '{row['end_time']}');\n")

        self.close()
        return filepath