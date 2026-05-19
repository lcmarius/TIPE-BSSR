"""Simulation contrefactuelle : valeur marginale d'un camion supplémentaire
ajouté à la flotte Bicloo Nantes existante, sur une journée réelle.

Cadrage : Bicloo opère déjà 3-4 camions de rééquilibrage par jour (visible
dans la donnée comme `source = 'TRUCK'`). On **ne les remplace pas** ; on
en ajoute UN, piloté par notre solveur. Le gain mesuré est donc la
**valeur marginale** d'un camion supplémentaire dans la flotte.

Principe :

  1. État initial à 00:00 = `available_bikes` premier snapshot de chaque
     station dans `station_history`.
  2. On rejoue chronologiquement TOUS les `bike_movements` (USER + TRUCK
     opérateur). Saturation aux bornes : un DEPARTURE sur station vide ou
     un ARRIVAL sur station pleine ne change pas le stock, et incrémente
     le compteur `demande perdue` *seulement* si l'événement est USER (un
     échec opérationnel du TRUCK n'est pas une perte usager).
  3. Politique « camion supplémentaire en boucle » : au départ (`--start`),
     le camion lance une tournée. Targeter Skellam → solver (method1 + ILS) ;
     on connaît le temps d'arrivée à chaque station et on applique
     `count_i += -bike_gap_i` (clampé à `[0, capacity_i]`) au passage.
     Une fois rentré, repos `--rest` minutes puis nouvelle tournée, tant
     que le départ suivant tombe avant `--end`.
  4. On intègre par station le temps passé en rupture (count==0 ou
     count==capacity). Sortie : une figure à 2 courbes (réalité observée
     vs réalité + notre camion) + chiffre titre `−X %`.

Usage :
    python -m renders.simulate --date 2026-04-15
    python -m renders.simulate --date 2026-04-15 --start 06:30 --end 18:00 --rest 30
    python -m renders.simulate --date 2026-04-15 --from-cache   # re-rend depuis pickle
"""

import argparse
import hashlib
import heapq
import os
import pickle
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from src.objects.station import Station
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.incrementer.ils import ils
from src.solver.graph import SolvingStationGraph
from src.solver.map import GeoPoint, Map
from src.solver.solver import create_graph, is_graph_solvable
from src.targeter.targeter import InfeasibleInstance, compute_adjusted_targets


TRUCK_CAPACITY     = 30
SAMPLE_INTERVAL_S  = 60
DEFAULT_OUT_DIR    = "renders/simulate"
GRAPHML_PATH       = "data/nantes_graph.graphml"
OSM_CITY           = "Nantes Métropole, France"
CLEAN_DIR          = "data/clean"
TIME_MATRIX_DIR    = "data"

# Politique de dispatch en boucle : le camion part à `start`, enchaîne
# tournée → repos → tournée → ... tant que la prochaine tentative tombe
# avant `end`. Une seule stratégie, comparée à la baseline « sans camion ».
DEFAULT_START_HHMM = "06:30"
DEFAULT_END_HHMM   = "18:00"
DEFAULT_REST_MIN   = 30

BASELINE_COLOR  = "#6c7a89"
OPTIMIZED_COLOR = "#2d5a9e"


@dataclass
class DispatchPolicy:
    start: datetime
    end:   datetime
    rest_s: float

    def label(self) -> str:
        return (f"Camion en boucle  {self.start.strftime('%H:%M')} → "
                f"{self.end.strftime('%H:%M')}  (repos {int(self.rest_s/60)} min)")


# ============================================================================
# Préparation carte routière + matrice de temps (mutualisée entre scénarios)
# ============================================================================

def _restrict_to_largest_scc(road_map: Map) -> None:
    import networkx as nx
    sccs = list(nx.strongly_connected_components(road_map.graph))
    largest = max(sccs, key=len)
    if len(largest) < len(road_map.graph.nodes):
        road_map.graph = road_map.graph.subgraph(largest).copy()


def _warm_node_cache(road_map: Map, stations: list[Station]) -> None:
    """Pré-remplit Map._node_cache via scipy (évite la dépendance sklearn d'osmnx)."""
    import numpy as np
    from scipy.spatial import cKDTree
    node_ids = list(road_map.graph.nodes)
    coords = np.array([(road_map.graph.nodes[n]['x'], road_map.graph.nodes[n]['y'])
                       for n in node_ids])
    tree = cKDTree(coords)
    queries = np.array([(s.long, s.lat) for s in stations])
    _, idx = tree.query(queries, k=1)
    for s, i in zip(stations, idx):
        road_map._node_cache[(s.lat, s.long)] = node_ids[int(i)]


def _matrix_cache_path(stations: list[Station], depot: Station) -> str:
    """Clé d'identité (positions + capa) pour invalider le cache si le réseau change."""
    blob = "|".join(f"{s.number}:{s.lat:.6f},{s.long:.6f}"
                    for s in sorted(stations, key=lambda x: x.number))
    blob += f"||depot:{depot.lat:.6f},{depot.long:.6f}"
    h = hashlib.sha1(blob.encode()).hexdigest()[:10]
    return os.path.join(TIME_MATRIX_DIR, f"time_matrix_{h}.pkl")


def _build_time_matrix(road_map: Map, all_stations: list[Station]
                       ) -> dict[int, dict[int, float]]:
    """Toutes les paires (s_i, s_j) → temps Dijkstra en secondes (cf. H3-H5)."""
    matrix: dict[int, dict[int, float]] = {s.number: {} for s in all_stations}
    n = len(all_stations)
    print(f"[{_ts()}] Matrice de temps : {n}×{n} = {n*(n-1)} Dijkstras...")
    for i, s in enumerate(all_stations, 1):
        for t in all_stations:
            if s.number == t.number:
                continue
            if t.number not in matrix[s.number]:
                matrix[s.number][t.number] = road_map.get_time(
                    GeoPoint(s.lat, s.long), GeoPoint(t.lat, t.long))
        if i % 20 == 0 or i == n:
            print(f"[{_ts()}]   {i}/{n} stations traitées")
    return matrix


def _load_or_build_time_matrix(road_map: Map, stations: list[Station],
                                depot: Station, rebuild: bool
                                ) -> dict[int, dict[int, float]]:
    path = _matrix_cache_path(stations, depot)
    if (not rebuild) and os.path.exists(path):
        print(f"[{_ts()}] Cache matrice trouvé : {path}")
        with open(path, "rb") as f:
            return pickle.load(f)
    matrix = _build_time_matrix(road_map, [depot, *stations])
    os.makedirs(TIME_MATRIX_DIR, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(matrix, f)
    print(f"[{_ts()}] Matrice écrite : {path}")
    return matrix


# ============================================================================
# Chargement d'une journée nettoyée
# ============================================================================

def _load_day(db_path: str) -> tuple[list[Station], dict[int, int],
                                      list[tuple[datetime, int, str, str]]]:
    """Stations + comptes initiaux + flux USER **et** TRUCK ordonné.

    Le TRUCK ici est celui de l'opérateur (visible dans la donnée scrapée).
    Il fait déjà partie de la « réalité observée » sur laquelle s'appuie
    la baseline. Notre camion à nous s'ajoute par-dessus dans `run_scenario`.
    """
    con = sqlite3.connect(db_path)
    # Station(number, name, capacity, address, long, lat) — long avant lat.
    rows = con.execute(
        "SELECT station_number, name, capacity, address, geo_lat, geo_long "
        "FROM stations ORDER BY station_number"
    ).fetchall()
    stations = [Station(n, name, cap, addr, lon, lat)
                for n, name, cap, addr, lat, lon in rows]

    # Compte initial = premier snapshot disponible de chaque station.
    init_rows = con.execute("""
        SELECT h.station_number, h.available_bikes
        FROM station_history h
        WHERE h.timestamp = (
            SELECT MIN(timestamp) FROM station_history h2
            WHERE h2.station_number = h.station_number
        )
    """).fetchall()
    initial = {n: c for n, c in init_rows}

    ev_rows = con.execute("""
        SELECT timestamp, station_number, movement_type, source
        FROM bike_movements
        ORDER BY timestamp
    """).fetchall()
    events = [(datetime.fromisoformat(ts), sn, mt, src)
              for ts, sn, mt, src in ev_rows]
    con.close()
    return stations, initial, events


def _synthetic_depot(stations: list[Station]) -> Station:
    """Dépôt fictif au barycentre (number = 0)."""
    if not stations:
        raise SystemExit("Aucune station chargée.")
    mean_lat  = sum(s.lat  for s in stations) / len(stations)
    mean_long = sum(s.long for s in stations) / len(stations)
    return Station(0, "DÉPÔT (barycentre)", 0, "", mean_long, mean_lat)


# ============================================================================
# Simulateur — état du réseau en temps continu
# ============================================================================

class Simulator:
    """Maintient les comptes par station et intègre le temps de rupture.

    Modèle d'intégration : chaque station mémorise son dernier instant de
    changement de stock. Quand le stock change (ou qu'on `settle` pour
    échantillonner), on ajoute `(now − last_t)` à la rupture cumulée *si*
    le stock précédent était saturé (== 0 ou == capacity).
    """

    def __init__(self, stations: list[Station], initial_counts: dict[int, int],
                 day_start: datetime):
        self.cap:      dict[int, int] = {s.number: s.capacity for s in stations}
        # Stations absentes du premier snapshot : compte = capacity//2 par défaut.
        self.count:    dict[int, int] = {
            s.number: initial_counts.get(s.number, s.capacity // 2) for s in stations
        }
        self.last_t:   dict[int, datetime]  = {s.number: day_start for s in stations}
        self.rupture_s: dict[int, float]    = {s.number: 0.0 for s in stations}
        self.lost: int = 0

    def _is_rupture(self, s: int) -> bool:
        c = self.count[s]
        return c <= 0 or c >= self.cap[s]

    def _settle(self, s: int, t: datetime) -> None:
        if self._is_rupture(s):
            self.rupture_s[s] += (t - self.last_t[s]).total_seconds()
        self.last_t[s] = t

    def apply_movement(self, t: datetime, s: int, kind: str, source: str) -> None:
        """Mouvement unitaire (USER ou TRUCK opérateur, +1 / −1 sur le stock).

        Saturation : on clampe aux bornes physiques [0, capacity]. Côté
        compteur `lost`, on n'incrémente QUE pour les USER : un échec
        opérationnel du TRUCK opérateur n'est pas une perte usager.
        """
        if s not in self.count:
            return
        self._settle(s, t)
        if kind == "DEPARTURE":
            if self.count[s] > 0:
                self.count[s] -= 1
            elif source == "USER":
                self.lost += 1
        else:  # ARRIVAL
            if self.count[s] < self.cap[s]:
                self.count[s] += 1
            elif source == "USER":
                self.lost += 1

    def apply_truck(self, t: datetime, s: int, delta: int) -> None:
        """Camion arrive et exécute son plan de transfert (delta = target − count_snapshot)."""
        if s not in self.count:
            return
        self._settle(s, t)
        self.count[s] = max(0, min(self.cap[s], self.count[s] + delta))

    def settle_all(self, t: datetime) -> None:
        for s in list(self.count):
            self._settle(s, t)

    def total_rupture_minutes(self) -> float:
        return sum(self.rupture_s.values()) / 60.0


# ============================================================================
# Planification de la tournée — targeter + solver + temps d'arrivée
# ============================================================================

@dataclass
class TourPlan:
    arrival_offsets: list[tuple[float, int, int]]  # (offset_s, station_num, delta)
    total_time_s: float
    n_active: int


def _plan_tour(stations_master: list[Station], snapshot_counts: dict[int, int],
               when: datetime, truck_capacity: int, depot: Station,
               road_map: Map, time_cache: dict[int, dict[int, float]],
               clean_dir: str) -> TourPlan | None:
    """Renvoie le plan de la tournée à partir de l'état courant, ou None si infaisable."""
    try:
        targeted = compute_adjusted_targets(stations_master, snapshot_counts, when,
                                             truck_capacity, clean_dir=clean_dir)
    except InfeasibleInstance as exc:
        print(f"[{_ts()}]   targeter infaisable : {exc}")
        return None
    if not targeted:
        return TourPlan(arrival_offsets=[], total_time_s=0.0, n_active=0)

    graph = create_graph(targeted, depot, road_map)
    graph.time_cache = time_cache
    if not is_graph_solvable(graph, truck_capacity):
        print(f"[{_ts()}]   graphe non solvable (contraintes C1/C2 violées)")
        return None

    method1(graph, truck_capacity)
    ils(graph, truck_capacity)

    # On parcourt le cycle 0 → ... → 0 en accumulant le temps de trajet ;
    # à chaque station visitée on enregistre (offset, station, delta).
    arrivals: list[tuple[float, int, int]] = []
    current = 0
    elapsed = 0.0
    visited: set[int] = set()
    while True:
        succ = graph.get_successor(current)
        if succ is None:
            break
        elapsed += graph.get_time(graph.get_station(current),
                                  graph.get_station(succ))
        if succ == 0:
            break
        if succ in visited:
            break
        visited.add(succ)
        st = graph.get_station(succ)
        # Plan camion = delta numérique fixé au snapshot. À l'arrivée,
        # le stock observé peut être différent ; on applique le delta tel
        # quel (clampé par `apply_truck` aux bornes physiques).
        delta = -st.bike_gap()
        arrivals.append((elapsed, succ, delta))
        current = succ

    return TourPlan(arrival_offsets=arrivals, total_time_s=elapsed,
                    n_active=len(targeted))


# ============================================================================
# Exécution d'un scénario — boucle d'événements à priorité
# ============================================================================

@dataclass
class SimulationResult:
    label:           str
    times:           list[datetime] = field(default_factory=list)
    rupture_min_cum: list[float]    = field(default_factory=list)
    lost_cum:        list[int]      = field(default_factory=list)
    dispatch_times:  list[datetime] = field(default_factory=list)
    total_tour_time_s:  float       = 0.0
    per_station_rupture_min: dict[int, float] = field(default_factory=dict)

    @property
    def total_rupture_min(self) -> float:
        return self.rupture_min_cum[-1] if self.rupture_min_cum else 0.0

    @property
    def total_lost(self) -> int:
        return self.lost_cum[-1] if self.lost_cum else 0


def run_scenario(label: str, policy: DispatchPolicy | None, day: date,
                 stations_master: list[Station], initial_counts: dict[int, int],
                 events_real: list[tuple[datetime, int, str, str]],
                 depot: Station, road_map: Map,
                 time_cache: dict[int, dict[int, float]],
                 truck_capacity: int, clean_dir: str
                 ) -> SimulationResult:
    """Joue la politique sur la journée et renvoie la trace temporelle.

    `events_real` contient TOUS les mouvements (USER + TRUCK opérateur).
    `policy=None` ⇒ baseline : on rejoue uniquement la réalité observée,
    sans camion supplémentaire.
    Sinon : à `policy.start`, notre camion **s'ajoute** au flux réel pour
    une tournée. Quand elle se termine, on déclenche la suivante après
    `policy.rest_s` de repos, tant qu'on est avant `policy.end`.
    """
    day_start = datetime.combine(day, datetime.min.time())
    day_end   = day_start + timedelta(days=1)

    sim = Simulator(stations_master, initial_counts, day_start)

    # Tiebreaker numérique (0/1/2) à timestamp égal pour éviter la
    # comparaison du payload de types hétérogènes.
    heap: list[tuple[datetime, int, str, object]] = []
    for ev in events_real:
        if day_start <= ev[0] < day_end:
            heapq.heappush(heap, (ev[0], 0, "movement", ev))
    if policy is not None:
        heapq.heappush(heap, (policy.start, 1, "dispatch", None))

    sample_times = [day_start + timedelta(seconds=SAMPLE_INTERVAL_S * i)
                    for i in range(24 * 3600 // SAMPLE_INTERVAL_S + 1)]
    sample_idx = 0

    result = SimulationResult(label=label)
    total_tour_time = 0.0

    def _record_sample(t_sample: datetime) -> None:
        sim.settle_all(t_sample)
        result.times.append(t_sample)
        result.rupture_min_cum.append(sim.total_rupture_minutes())
        result.lost_cum.append(sim.lost)

    while heap or sample_idx < len(sample_times):
        next_event_t = heap[0][0] if heap else day_end + timedelta(seconds=1)
        while (sample_idx < len(sample_times)
               and sample_times[sample_idx] <= next_event_t):
            _record_sample(sample_times[sample_idx])
            sample_idx += 1
        if not heap:
            break

        t, _, kind, payload = heapq.heappop(heap)
        if t > day_end:
            break

        if kind == "movement":
            _, s, mtype, source = payload  # type: ignore[misc]
            sim.apply_movement(t, s, mtype, source)

        elif kind == "truck":
            s, delta = payload      # type: ignore[misc]
            sim.apply_truck(t, s, delta)

        elif kind == "dispatch":
            assert policy is not None
            if t > policy.end:
                continue
            print(f"[{_ts()}]   dispatch {t.strftime('%H:%M')} — snapshot, "
                  f"targeter, solver+ILS...")
            plan = _plan_tour(stations_master, dict(sim.count), t, truck_capacity,
                              depot, road_map, time_cache, clean_dir)
            if plan is None or not plan.arrival_offsets:
                continue
            result.dispatch_times.append(t)
            total_tour_time += plan.total_time_s
            for offset_s, s_num, delta in plan.arrival_offsets:
                arrival_t = t + timedelta(seconds=offset_s)
                if arrival_t <= day_end:
                    heapq.heappush(heap, (arrival_t, 2, "truck", (s_num, delta)))
            tour_end = t + timedelta(seconds=plan.total_time_s)
            next_dispatch = tour_end + timedelta(seconds=policy.rest_s)
            print(f"[{_ts()}]   → {plan.n_active} stations actives, "
                  f"tournée {plan.total_time_s/60:.1f} min  "
                  f"(fin {tour_end.strftime('%H:%M')}, "
                  f"prochain départ {next_dispatch.strftime('%H:%M')})")
            if next_dispatch <= policy.end:
                heapq.heappush(heap, (next_dispatch, 1, "dispatch", None))

    while sample_idx < len(sample_times):
        _record_sample(sample_times[sample_idx])
        sample_idx += 1

    result.total_tour_time_s = total_tour_time
    sim.settle_all(day_end)
    result.per_station_rupture_min = {s: r / 60.0 for s, r in sim.rupture_s.items()}
    return result


# ============================================================================
# Rendu
# ============================================================================

def render(baseline: SimulationResult, optimized: SimulationResult,
           day: date, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"simulate_{day.isoformat()}.png")

    fig, ax = plt.subplots(figsize=(13, 6.5))
    fig.patch.set_facecolor("white")

    base_rupt = baseline.total_rupture_min or 1e-9
    gain = (base_rupt - optimized.total_rupture_min) / base_rupt * 100

    ax.plot(baseline.times, baseline.rupture_min_cum, color=BASELINE_COLOR,
            ls="--", lw=2.2,
            label=(f"Réalité observée (flotte Bicloo actuelle) — "
                   f"{baseline.total_rupture_min:.0f} min"),
            zorder=3)
    ax.plot(optimized.times, optimized.rupture_min_cum, color=OPTIMIZED_COLOR,
            ls="-", lw=2.8,
            label=(f"Réalité + 1 camion supplémentaire — "
                   f"{optimized.total_rupture_min:.0f} min  (−{gain:.1f} %)"),
            zorder=3)
    for dt_disp in optimized.dispatch_times:
        ax.axvline(dt_disp, color=OPTIMIZED_COLOR, ls=":", alpha=0.45,
                   lw=1.0, zorder=1)

    title = (f"Valeur marginale d'un camion supplémentaire dans la flotte Bicloo — "
             f"Nantes, {day.strftime('%d/%m/%Y')}\n"
             f"−{gain:.1f} % de minutes-station en rupture vs flotte actuelle")
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)

    ax.set_ylabel("Minutes-station en rupture (cumul sur la journée)", fontsize=11)
    ax.set_xlabel("Heure", fontsize=11)
    ax.set_facecolor("#fafafa")
    ax.grid(True, alpha=0.3)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(loc="upper left", fontsize=10, framealpha=0.9)

    day_start = datetime.combine(day, datetime.min.time())
    day_end   = day_start + timedelta(days=1)
    ax.set_xlim(day_start, day_end)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))

    note = ("Hypothèse statique (H4) : demande USER indépendante de l'état des "
            "stations — la baseline surestime donc la rupture réellement observable.")
    fig.text(0.5, -0.01, note, ha="center", va="top", fontsize=8.5,
             style="italic", color="#6c7a89")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


# ============================================================================
# API programmatique — appelée par renders/simulate_modal.py
# ============================================================================

def simulate_for_date(date_str: str, *,
                      clean_dir: str = CLEAN_DIR,
                      capacity: int = TRUCK_CAPACITY,
                      start_hhmm: str = DEFAULT_START_HHMM,
                      end_hhmm: str = DEFAULT_END_HHMM,
                      rest_min: int = DEFAULT_REST_MIN,
                      graphml: str = GRAPHML_PATH,
                      city: str = OSM_CITY,
                      rebuild_matrix: bool = False,
                      verbose: bool = True
                      ) -> tuple[SimulationResult, SimulationResult]:
    """Pipeline complet pour une journée : (baseline, optimisé).

    Wrapper réutilisable du CLI. La sortie console est gouvernée par
    `verbose` ; mettre False pour exécution silencieuse (e.g. workers
    parallèles côté Modal).
    """
    day = date.fromisoformat(date_str)
    db_path = os.path.join(clean_dir, f"clean_{day.isoformat()}.sql")
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"Fichier introuvable : {db_path}")

    def log(msg: str) -> None:
        if verbose:
            print(f"[{_ts()}] {msg}")

    log(f"[1/4] Chargement journée  · {db_path}")
    stations, initial, events = _load_day(db_path)
    depot = _synthetic_depot(stations)

    log(f"[2/4] Carte routière      · {city}")
    road_map = Map(graphml, city=city)
    _restrict_to_largest_scc(road_map)
    _warm_node_cache(road_map, [depot, *stations])

    log(f"[3/4] Matrice de temps")
    time_cache = _load_or_build_time_matrix(road_map, stations, depot,
                                             rebuild=rebuild_matrix)

    day_start = datetime.combine(day, datetime.min.time())
    sh, sm = map(int, start_hhmm.split(":"))
    eh, em = map(int, end_hhmm.split(":"))
    policy = DispatchPolicy(
        start  = day_start + timedelta(hours=sh, minutes=sm),
        end    = day_start + timedelta(hours=eh, minutes=em),
        rest_s = rest_min * 60,
    )

    log(f"[4/4] Baseline + {policy.label()}")
    baseline = run_scenario("Réalité observée (USER + TRUCK opérateur)", None,
                            day, stations, initial, events, depot, road_map,
                            time_cache, capacity, clean_dir)
    optimized = run_scenario("Réalité + 1 camion supplémentaire", policy, day,
                             stations, initial, events, depot, road_map,
                             time_cache, capacity, clean_dir)
    return baseline, optimized


# ============================================================================
# Main / CLI
# ============================================================================

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--date", required=True,
                        help="Jour à simuler (YYYY-MM-DD) — un clean_<date>.sql doit exister")
    parser.add_argument("--clean-dir", default=CLEAN_DIR,
                        help=f"Répertoire des clean_*.sql (défaut: {CLEAN_DIR})")
    parser.add_argument("--capacity", type=int, default=TRUCK_CAPACITY,
                        help=f"Capacité du camion (défaut: {TRUCK_CAPACITY})")
    parser.add_argument("--start", default=DEFAULT_START_HHMM,
                        help=f"Heure du premier départ HH:MM (défaut: {DEFAULT_START_HHMM})")
    parser.add_argument("--end",   default=DEFAULT_END_HHMM,
                        help=f"Heure butoir HH:MM, plus aucune nouvelle tournée après "
                             f"(défaut: {DEFAULT_END_HHMM})")
    parser.add_argument("--rest",  type=int, default=DEFAULT_REST_MIN,
                        help=f"Repos en minutes entre fin d'une tournée et départ suivant "
                             f"(défaut: {DEFAULT_REST_MIN})")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                        help=f"Dossier de sortie (défaut: {DEFAULT_OUT_DIR})")
    parser.add_argument("--rebuild-matrix", action="store_true",
                        help="Force le recalcul de la matrice de temps")
    parser.add_argument("--from-cache", action="store_true",
                        help="Réutilise les résultats sim_results_<date>.pkl pour ne refaire que le rendu")
    parser.add_argument("--graphml", default=GRAPHML_PATH,
                        help=f"Cache OSMnx du graphe routier (défaut: {GRAPHML_PATH})")
    parser.add_argument("--city", default=OSM_CITY,
                        help=f"Ville OSMnx (défaut: {OSM_CITY!r})")
    args = parser.parse_args()

    day     = date.fromisoformat(args.date)
    db_path = os.path.join(args.clean_dir, f"clean_{day.isoformat()}.sql")
    if not os.path.isfile(db_path):
        raise SystemExit(f"Fichier introuvable : {db_path}")

    os.makedirs(args.out_dir, exist_ok=True)
    results_cache = os.path.join(args.out_dir, f"sim_results_{day.isoformat()}.pkl")

    if args.from_cache:
        if not os.path.exists(results_cache):
            raise SystemExit(f"Cache résultats absent : {results_cache}")
        print(f"[{_ts()}] Cache résultats trouvé : {results_cache} — rendu seul")
        with open(results_cache, "rb") as f:
            baseline, optimized = pickle.load(f)
        path = render(baseline, optimized, day, args.out_dir)
        print(f"[{_ts()}] OK — {path}")
        return

    baseline, optimized = simulate_for_date(
        args.date,
        clean_dir=args.clean_dir,
        capacity=args.capacity,
        start_hhmm=args.start,
        end_hhmm=args.end,
        rest_min=args.rest,
        graphml=args.graphml,
        city=args.city,
        rebuild_matrix=args.rebuild_matrix,
        verbose=True,
    )
    print(f"[{_ts()}]   baseline  : {baseline.total_rupture_min:.0f} min rupture  ·  "
          f"{baseline.total_lost} USER perdus")
    print(f"[{_ts()}]   optimisé  : {optimized.total_rupture_min:.0f} min rupture  ·  "
          f"{optimized.total_lost} USER perdus  ·  "
          f"{len(optimized.dispatch_times)} tournées effectives")

    with open(results_cache, "wb") as f:
        pickle.dump((baseline, optimized), f)
    print(f"[{_ts()}] Résultats écrits : {results_cache}")

    print(f"[{_ts()}] Rendu...")
    path = render(baseline, optimized, day, args.out_dir)
    print(f"[{_ts()}] OK — {path}")

    if baseline.total_rupture_min > 0:
        dr = (baseline.total_rupture_min - optimized.total_rupture_min) / baseline.total_rupture_min * 100
        dl = ((baseline.total_lost - optimized.total_lost) / baseline.total_lost * 100
              if baseline.total_lost else 0)
        print()
        print(f"  {'Scénario':<48}  {'Rupture (min)':>14}  {'Δ':>7}  {'Perdus':>8}  {'Δ':>7}")
        print(f"  {'─' * 48}  {'─' * 14}  {'─' * 7}  {'─' * 8}  {'─' * 7}")
        print(f"  {baseline.label:<48}  {baseline.total_rupture_min:>14.0f}  "
              f"{0.0:>+6.1f}%  {baseline.total_lost:>8}  {0.0:>+6.1f}%")
        print(f"  {optimized.label:<48}  {optimized.total_rupture_min:>14.0f}  "
              f"{dr:>+6.1f}%  {optimized.total_lost:>8}  {dl:>+6.1f}%")


if __name__ == "__main__":
    main()
