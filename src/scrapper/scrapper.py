"""
Scrapper Bicloo - Collecte des mouvements de vélos en temps réel

STRATÉGIE:
    1. Au démarrage:
       - 1 appel /stations → enregistre les infos stations en DB
       - 1 appel /bikes → initialise le cache (quels vélos sur quelle station)

    2. Toutes les 10 secondes:
       - 1 appel /station_status → récupère le nombre de vélos par station (temps réel)
       - Compare avec le cache pour détecter les stations qui ont changé
       - Pour chaque station modifiée: 1 appel /bikes?stationNumber=X
         → Diff des bike_ids pour savoir quels vélos sont arrivés/partis
       - Enregistre les mouvements (ARRIVAL/DEPARTURE) avec le bike_id
       - Enregistre l'historique du nombre de vélos (toutes les 5 min ou si changement)

APPELS API:
    - Init: 2 appels (/stations + /bikes)
    - Sans changement: 1 appel/cycle
    - Avec changements: 1 + nb_stations_modifiées appels/cycle

DONNÉES COLLECTÉES:
    - bike_movements: bike_id, station, type (ARRIVAL/DEPARTURE), timestamp
    - station_history: station, nb_vélos_disponibles, timestamp

USAGE:
    python -m src.scrapper.scrapper
    Ctrl+C pour arrêter proprement
"""

import signal
import logging
import time
from datetime import datetime
from typing import Dict, Set, Tuple, List

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

POLL_INTERVAL = 10
HISTORY_INTERVAL = 300


class Scrapper:

    def __init__(self, db_path: str = "data/scrapper.sql"):
        self.api = API()
        self.db = Database(db_path)

        # Cache counts: station_id -> nb_bikes (pour détecter les changements)
        self.station_counts: Dict[int, int] = {}

        # Cache vélos: station_id -> set of bike_ids
        self.station_bikes: Dict[int, Set[str]] = {}

        # Cache statuts vélos: bike_id -> status
        self.bike_status: Dict[str, str] = {}

        # Dernière mise à jour station_history par station
        self.last_history_update: Dict[int, datetime] = {}

        self.running = False
        self.first_cycle = True

    def run(self):
        """Boucle principale"""
        signal.signal(signal.SIGINT, lambda *_: setattr(self, 'running', False))
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, 'running', False))
        self.running = True

        logger.info(f"Démarrage - poll: {POLL_INTERVAL}s, history: {HISTORY_INTERVAL}s")

        # Init: récupérer les infos stations
        self._init_stations()

        try:
            while self.running:
                cycle_start = time.monotonic()
                try:
                    self._execute_cycle()
                except Exception as e:
                    logger.error(f"Erreur cycle: {e}", exc_info=True)

                sleep_time = max(0, POLL_INTERVAL - (time.monotonic() - cycle_start))
                if self.running and sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            logger.info("Collecteur arrêté")

    def _init_stations(self):
        """Récupère les infos stations et les enregistre en DB"""
        logger.info("Initialisation des stations...")
        try:
            data = get_stations(self.api)
        except Exception as e:
            logger.error(f"Erreur init stations: {e}")
            return

        stations = [
            Station(
                station_number=s['code'],
                name=s.get('label', ''),
                capacity=s.get('nbBikeBases', 0),
                address='',
                geo_long=0.0,
                geo_lat=0.0,
                connected=s.get('connected', False)
            )
            for s in data
        ]
        self.db.upsert_stations(stations)
        logger.info(f"{len(stations)} stations enregistrées")

    def _execute_cycle(self):
        """Exécute un cycle de collecte"""
        now = datetime.now()

        # 1. Appel rapide pour les counts
        try:
            status_data = get_station_status(self.api)
        except Exception as e:
            logger.error(f"Erreur API status: {e}")
            return

        current_counts = {
            int(s['station_id']): s['num_vehicles_available']
            for s in status_data
        }

        if self.first_cycle:
            # Premier cycle: init tous les vélos de toutes les stations
            logger.info(f"Premier cycle: {len(current_counts)} stations, {sum(current_counts.values())} vélos")
            self._init_all_bikes(current_counts.keys())
            self.station_counts = current_counts
            self.first_cycle = False
            return

        # 2. Détecter les stations qui ont changé
        changed_stations = [
            sn for sn, count in current_counts.items()
            if self.station_counts.get(sn) != count
        ]

        movements = []
        new_bikes = []

        if changed_stations:
            logger.info(f"{len(changed_stations)} stations ont changé, analyse détaillée...")

            # 3. Pour chaque station modifiée, récupérer les détails
            for sn in changed_stations:
                try:
                    bikes_data = get_bikes(self.api, sn)
                    station_movements, station_new_bikes = self._analyze_station(sn, bikes_data, now)
                    movements.extend(station_movements)
                    new_bikes.extend(station_new_bikes)
                except Exception as e:
                    logger.warning(f"Erreur détails station {sn}: {e}")

        # 4. Enregistrer les mouvements
        if movements:
            self.db.insert_movements_batch(movements)
            arrivals = sum(1 for m in movements if m[2] == 'ARRIVAL')
            departures = sum(1 for m in movements if m[2] == 'DEPARTURE')
            logger.info(f"Mouvements: +{arrivals} -{departures}")

        if new_bikes:
            self.db.upsert_bikes(new_bikes)

        # 5. Historique
        self._record_history(current_counts, now, changed_stations)

        self.station_counts = current_counts

    def _init_all_bikes(self, station_ids):
        """Initialise le cache de tous les vélos (1 seul appel API)"""
        logger.info("Chargement initial des vélos...")

        try:
            bikes_data = get_bikes(self.api)  # Tous les vélos en 1 appel
        except Exception as e:
            logger.error(f"Erreur chargement vélos: {e}")
            return

        # Init les sets pour toutes les stations
        for sn in station_ids:
            self.station_bikes[sn] = set()

        all_bikes = []
        for b in bikes_data:
            bike_id = b.get('id')
            sn = b.get('stationNumber')

            if bike_id and sn:
                self.station_bikes[sn].add(bike_id)
                self.bike_status[bike_id] = b.get('status', 'UNKNOWN')
                all_bikes.append(Bike(bike_id, b.get('number', 0), b.get('status')))

        if all_bikes:
            self.db.upsert_bikes(all_bikes)
        logger.info(f"Cache initialisé: {len(self.bike_status)} vélos sur {len([s for s in self.station_bikes if self.station_bikes[s]])} stations")

    def _analyze_station(self, sn: int, bikes_data: List[dict], timestamp: datetime) -> Tuple[List, List]:
        """Analyse les changements sur une station"""
        movements = []
        new_bikes = []

        # Vélos actuels sur la station
        current_bikes = {b.get('id'): b for b in bikes_data if b.get('id')}
        current_ids = set(current_bikes.keys())
        prev_ids = self.station_bikes.get(sn, set())

        # Arrivées
        arrived = current_ids - prev_ids
        for bike_id in arrived:
            b = current_bikes[bike_id]
            movements.append((bike_id, sn, 'ARRIVAL', timestamp))

            if bike_id not in self.bike_status:
                # Nouveau vélo jamais vu
                new_bikes.append(Bike(bike_id, b.get('number', 0), b.get('status')))

            self.bike_status[bike_id] = b.get('status', 'UNKNOWN')

        # Départs
        departed = prev_ids - current_ids
        for bike_id in departed:
            movements.append((bike_id, sn, 'DEPARTURE', timestamp))

        # Mettre à jour le cache
        self.station_bikes[sn] = current_ids

        return movements, new_bikes

    def _record_history(self, current: Dict[int, int], timestamp: datetime, changed_stations: List[int]):
        """Enregistre l'historique si changement ou 5min écoulées"""
        changed_set = set(changed_stations)
        records = []

        for sn, count in current.items():
            last = self.last_history_update.get(sn)
            elapsed = (timestamp - last).total_seconds() if last else float('inf')

            if sn in changed_set or elapsed >= HISTORY_INTERVAL:
                records.append((sn, count, timestamp))
                self.last_history_update[sn] = timestamp

        if records:
            self.db.insert_station_history_batch(records)


def run(db_path: str = "data/scrapper.sql"):
    Scrapper(db_path).run()


if __name__ == "__main__":
    run()
