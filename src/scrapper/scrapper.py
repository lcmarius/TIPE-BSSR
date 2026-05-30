# =============================================================================
# Collecte temps réel des mouvements de vélos Bicloo
# =============================================================================
#
# Stratégie deux sources :
#
#   1. Endpoint `/bikes` (polling rapide, ~5 s) : liste vélo-par-vélo. En diffant
#      deux snapshots successifs on reconstruit les mouvements unitaires
#      (ARRIVAL / DEPARTURE) et on peut classer leur source via le `status`
#      individuel (REGULATION → camion de rééquilibrage, MAINTENANCE → service,
#      sinon usager).
#
#   2. Endpoint `/station_status` (polling lent, ~5 min) : counts officiels
#      agrégés par station. Sert d'ancrage : on s'en sert pour détecter les
#      dérives du tracking individuel (vélo invisible côté `/bikes`, vol, …)
#      et pour recalibrer périodiquement.
#
# Sans le recalage, les écarts s'accumulent au fil de la journée. Sans le
# polling rapide, on n'a aucune information de source ni de granularité.
# =============================================================================

import logging
import signal
import time

from src.objects.bike import Bike
from src.objects.station import Station
from src.scrapper.api import API, get_stations, get_station_status, get_bikes
from src.scrapper.database import Database
from src.utils.timezone import now_utc_naive

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# Statuts API Bicloo signalant un vélo hors-service côté maintenance.
MAINTENANCE_STATUSES = frozenset(('MAINTENANCE', 'TO_BE_REPARED', 'MAINTENANCE_HEAVY'))


class Scrapper:

    def __init__(self, db_path: str = "data/current.sql",
                 poll_interval: int = 5, status_interval: int = 300):
        self.api = API()
        self.db = Database(db_path)
        self.poll_interval = poll_interval
        self.status_interval = status_interval

        self.stations: dict[int, Station] = {}
        self.station_counts: dict[int, int] = {}          # count officiel le plus récent
        self.station_bikes: dict[int, set[str]] = {}      # set des bike_id par station (tracking)
        self.bike_statuses: dict[str, str] = {}           # status API du dernier cycle, par bike_id
        self.known_bikes: set[str] = set()
        self.active_stations: set[int] = set()
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

    @staticmethod
    def _classify_source(status: str) -> str:
        # Classification décidée d'après le `status` API au moment de l'événement.
        # REGULATION = vélo manipulé par le camion de rééquilibrage Bicloo, c'est
        # précisément ce qu'on cherche à isoler pour étudier la politique actuelle.
        if status == 'REGULATION':
            return 'TRUCK'
        if status in MAINTENANCE_STATUSES:
            return 'MAINTENANCE'
        return 'USER'

    def _init_stations(self):
        data = get_stations(self.api)
        for s in data:
            name = s.get('name', '')
            if isinstance(name, list):
                name = name[0]['text'] if name else ''
            station = Station(
                number=int(s['station_id']),
                name=name,
                capacity=s.get('capacity', 0),
                address=s.get('address', ''),
                long=s.get('lon', 0.0),
                lat=s.get('lat', 0.0),
            )
            self.stations[station.number] = station
        self.db.upsert_stations(list(self.stations.values()))
        logger.info(f"{len(self.stations)} stations enregistrées")

    def _init_bikes(self) -> bool:
        try:
            self._refresh_official_counts()
            snapshot, details, all_statuses = self._fetch_bike_snapshot()
        except Exception as e:
            logger.error(f"Erreur init: {e}")
            return False

        self.station_bikes = snapshot
        self.bike_statuses = all_statuses
        self.known_bikes = set(details.keys())

        all_bikes = [Bike(bid, b.get('number', 0)) for bid, b in details.items()]
        if all_bikes:
            self.db.upsert_bikes(all_bikes)

        active = sum(1 for bikes in snapshot.values() if bikes)
        logger.info(f"{len(self.active_stations)} stations actives, {len(self.known_bikes)} vélos sur {active} stations")

        self._record_history(list(self.station_counts.keys()))
        return True

    # Mesure (sans corriger) l'écart entre notre tracking individuel et les
    # counts officiels juste avant chaque recalage. Une dérive récurrente sur
    # une station indique qu'on rate des mouvements : snapshot trop espacé,
    # vélo absent de `/bikes`, etc.
    def _audit_before_refresh(self):
        """Logge les stations en dérive avant le recalage."""
        try:
            status_data = get_station_status(self.api)
        except Exception as e:
            logger.warning(f"Erreur audit: {e}")
            return

        official = {int(s['station_id']): s['num_vehicles_available'] for s in status_data}
        drifts = []

        for sn in self.active_stations:
            tracked = len(self.station_bikes.get(sn, set()))
            off = official.get(sn, 0)
            diff = tracked - off
            if diff != 0:
                drifts.append((self._station_label(sn), tracked, off, diff))

        if drifts:
            logger.warning(f"AUDIT: {len(drifts)} station(s) en dérive avant recalage:")
            for label, tracked, off, diff in drifts:
                logger.warning(f"  {label}: bikes_trackés={tracked}, officiel={off} (écart={diff:+d})")
        else:
            logger.info("AUDIT: aucune dérive")

    def _refresh_official_counts(self):
        status_data = get_station_status(self.api)
        self.station_counts = {
            int(s['station_id']): s['num_vehicles_available']
            for s in status_data
        }
        self.active_stations = set(self.station_counts.keys())
        self.last_status_refresh = time.monotonic()

    def _fetch_bike_snapshot(self) -> tuple[dict[int, set[str]], dict[str, dict], dict[str, str]]:
        """Retourne (bikes_par_station, détails_par_bike_id, status_par_bike_id)."""
        bikes_data = get_bikes(self.api)

        snapshot: dict[int, set[str]] = {sn: set() for sn in self.active_stations}
        details: dict[str, dict] = {}
        all_statuses: dict[str, str] = {}

        for b in bikes_data:
            bike_id = b.get('id')
            if not bike_id:
                continue
            all_statuses[bike_id] = b.get('status', 'UNKNOWN')
            sn = b.get('stationNumber')
            if sn and sn in self.active_stations:
                snapshot[sn].add(bike_id)
                details[bike_id] = b

        return snapshot, details, all_statuses

    def _execute_cycle(self):
        # Stockage en UTC naïf — cf. src/utils/timezone.py.
        now = now_utc_naive()

        # Recalage périodique sur les counts officiels (cf. stratégie deux sources).
        if time.monotonic() - self.last_status_refresh >= self.status_interval:
            try:
                self._audit_before_refresh()
                self._refresh_official_counts()
                logger.info(f"Counts officiels recalés ({len(self.active_stations)} stations)")
                self._record_history(list(self.station_counts.keys()))
            except Exception as e:
                logger.warning(f"Erreur refresh status: {e}")

        snapshot, details, current_statuses = self._fetch_bike_snapshot()

        movements = []
        new_bikes = []
        changed_stations = []

        for sn in self.active_stations:
            current_ids = snapshot.get(sn, set())
            prev_ids = self.station_bikes.get(sn, set())

            # Diff ensembliste : un vélo dans current\prev a déposé là, et
            # réciproquement. C'est l'opération centrale de tout le scrapper.
            arrived = current_ids - prev_ids
            departed = prev_ids - current_ids

            if not arrived and not departed:
                continue

            changed_stations.append(sn)
            label = self._station_label(sn)

            for bike_id in arrived:
                # Pour une arrivée, on utilise le statut du cycle précédent : il
                # reflète l'état "en circulation" qui a précédé le dépôt.
                source = self._classify_source(self.bike_statuses.get(bike_id, 'UNKNOWN'))
                movements.append((bike_id, sn, 'ARRIVAL', now, source))
                self.station_counts[sn] = self.station_counts.get(sn, 0) + 1
                logger.info(f"ARRIVAL  vélo {details[bike_id].get('number', '?')} ({bike_id[:8]}) → {label} [{source}]")
                if bike_id not in self.known_bikes:
                    new_bikes.append(Bike(bike_id, details[bike_id].get('number', 0)))
                    self.known_bikes.add(bike_id)

            for bike_id in departed:
                # Pour un départ, c'est le statut courant qui caractérise l'action
                # (le vélo vient juste de passer en REGULATION, MAINTENANCE, …).
                source = self._classify_source(current_statuses.get(bike_id, 'UNKNOWN'))
                movements.append((bike_id, sn, 'DEPARTURE', now, source))
                self.station_counts[sn] = max(0, self.station_counts.get(sn, 0) - 1)
                logger.info(f"DEPARTURE vélo ({bike_id[:8]}) ← {label} [{source}]")

        if movements:
            self.db.insert_movements_batch(movements)
        if new_bikes:
            self.db.upsert_bikes(new_bikes)
        if changed_stations:
            self._record_history(changed_stations)

        self.station_bikes = snapshot
        self.bike_statuses = current_statuses

    def _record_history(self, stations: list[int]):
        records = [(sn, self.station_counts.get(sn, 0), now_utc_naive()) for sn in stations]
        if records:
            self.db.insert_station_history_batch(records)
