"""
Scrapper Bicloo - Collecte des mouvements de vélos en temps réel

STRATÉGIE:
    1. Au démarrage: /stations + /station_status + /bikes → init DB + caches
    2. Toutes les 5s: /bikes → diff → mouvements + historique
    3. Toutes les 5min: /station_status → recale counts officiels

USAGE:
    python -m src.main scrapper [--interval N] [--status-interval N] [--data-dir DIR] [--no-archive]
    Ctrl+C pour arrêter proprement
"""

import signal
import logging
import time
from datetime import datetime
from typing import Dict, List, Set, Tuple

from src.objects.bike import Bike
from src.objects.station import Station
from src.scrapper.api import API, get_stations, get_station_status, get_bikes
from src.scrapper.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class Scrapper:

    def __init__(self, db_path: str = "data/current.sql",
                 poll_interval: int = 5, status_interval: int = 300):
        self.api = API()
        self.db = Database(db_path)
        self.poll_interval = poll_interval
        self.status_interval = status_interval

        self.stations: Dict[int, Station] = {}
        self.station_counts: Dict[int, int] = {}
        self.station_bikes: Dict[int, Set[str]] = {}
        self.known_bikes: Set[str] = set()
        self.active_stations: Set[int] = set()
        self.last_status_refresh: float = 0.0
        self.running = False

    def run(self):
        signal.signal(signal.SIGINT, lambda *_: setattr(self, 'running', False))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, 'running', False))
        self.running = True

        logger.info(f"Démarrage - poll: {self.poll_interval}s, status refresh: {self.status_interval}s")

        self._init_stations()
        if not self._init_bikes():
            logger.error("Init échouée, arrêt")
            return

        try:
            while self.running:
                cycle_start = time.monotonic()
                try:
                    self._execute_cycle()
                except Exception as e:
                    logger.error(f"Erreur cycle: {e}", exc_info=True)

                sleep_time = max(0, self.poll_interval - (time.monotonic() - cycle_start))
                if self.running and sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            logger.info("Collecteur arrêté")

    def _station_label(self, sn: int) -> str:
        s = self.stations.get(sn)
        return s.name if s else f"#{sn}"

    def _init_stations(self):
        data = get_stations(self.api)
        for s in data:
            name = s.get('name', '')
            if isinstance(name, list):
                name = name[0]['text'] if name else ''
            station = Station(
                station_number=int(s['station_id']),
                name=name,
                capacity=s.get('capacity', 0),
                address=s.get('address', ''),
                geo_lat=s.get('lat', 0.0),
                geo_long=s.get('lon', 0.0),
            )
            self.stations[station.number] = station
        self.db.upsert_stations(list(self.stations.values()))
        logger.info(f"{len(self.stations)} stations enregistrées")

    def _init_bikes(self) -> bool:
        try:
            self._refresh_official_counts()
            snapshot, details = self._fetch_bike_snapshot()
        except Exception as e:
            logger.error(f"Erreur init: {e}")
            return False

        self.station_bikes = snapshot
        self.known_bikes = set(details.keys())

        all_bikes = [Bike(bid, b.get('number', 0)) for bid, b in details.items()]
        if all_bikes:
            self.db.upsert_bikes(all_bikes)

        active = sum(1 for bikes in snapshot.values() if bikes)
        logger.info(f"{len(self.active_stations)} stations actives, {len(self.known_bikes)} vélos sur {active} stations")

        self._record_history(list(self.station_counts.keys()))
        return True

    def _refresh_official_counts(self):
        status_data = get_station_status(self.api)
        self.station_counts = {
            int(s['station_id']): s['num_vehicles_available']
            for s in status_data
        }
        self.active_stations = set(self.station_counts.keys())
        self.last_status_refresh = time.monotonic()

    def _fetch_bike_snapshot(self) -> Tuple[Dict[int, Set[str]], Dict[str, dict]]:
        bikes_data = get_bikes(self.api)

        snapshot: Dict[int, Set[str]] = {sn: set() for sn in self.active_stations}
        details: Dict[str, dict] = {}

        for b in bikes_data:
            bike_id = b.get('id')
            sn = b.get('stationNumber')
            if bike_id and sn and sn in self.active_stations:
                snapshot[sn].add(bike_id)
                details[bike_id] = b

        return snapshot, details

    def _execute_cycle(self):
        now = datetime.now()

        if time.monotonic() - self.last_status_refresh >= self.status_interval:
            try:
                self._refresh_official_counts()
                logger.info(f"Counts officiels recalés ({len(self.active_stations)} stations)")
                self._record_history(list(self.station_counts.keys()))
            except Exception as e:
                logger.warning(f"Erreur refresh status: {e}")

        snapshot, details = self._fetch_bike_snapshot()

        movements = []
        new_bikes = []
        changed_stations = []

        for sn in self.active_stations:
            current_ids = snapshot.get(sn, set())
            prev_ids = self.station_bikes.get(sn, set())

            arrived = current_ids - prev_ids
            departed = prev_ids - current_ids

            if not arrived and not departed:
                continue

            changed_stations.append(sn)
            label = self._station_label(sn)

            for bike_id in arrived:
                movements.append((bike_id, sn, 'ARRIVAL', now))
                self.station_counts[sn] = self.station_counts.get(sn, 0) + 1
                num = details[bike_id].get('number', '?')
                logger.info(f"ARRIVAL  vélo {num} ({bike_id[:8]}) → {label}")
                if bike_id not in self.known_bikes:
                    new_bikes.append(Bike(bike_id, details[bike_id].get('number', 0)))
                    self.known_bikes.add(bike_id)

            for bike_id in departed:
                movements.append((bike_id, sn, 'DEPARTURE', now))
                self.station_counts[sn] = max(0, self.station_counts.get(sn, 0) - 1)
                logger.info(f"DEPARTURE vélo ({bike_id[:8]}) ← {label}")

        if movements:
            self.db.insert_movements_batch(movements)
        if new_bikes:
            self.db.upsert_bikes(new_bikes)
        if changed_stations:
            self._record_history(changed_stations)

        self.station_bikes = snapshot

    def _record_history(self, stations: List[int]):
        records = [(sn, self.station_counts.get(sn, 0), datetime.now()) for sn in stations]
        if records:
            self.db.insert_station_history_batch(records)

