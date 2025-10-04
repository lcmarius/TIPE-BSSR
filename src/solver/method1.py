from src.objects.station import TargetedStation
from src.solver.graph import SolvingStationGraph
import random

def create_path(graph: SolvingStationGraph, q: int, alpha: int) -> list[int]:
    stations = graph.list_stations()
    unloading_stations: list[TargetedStation] = []
    loading_stations: list[TargetedStation] = []
    for station in stations:
        if station.is_loading():
            loading_stations.append(station)
        else:
            unloading_stations.append(station)

    vehicle_load: int = 0
    path: list[int] = [0]

    cursor_station: TargetedStation = loading_stations[random.randint(0, len(loading_stations) - 1)]
    graph.add_edge(0, cursor_station.id)
    vehicle_load += cursor_station.bike_gap()
    path.append(cursor_station.id)

    for i in range(1, graph.size() - 1):
        nearest_station: TargetedStation | None = graph.get_nearest_successor(
            cursor_station.id,
            lambda s: alpha <= vehicle_load + s.bike_gape() <= q + alpha
        )

        if nearest_station is None:
            raise Exception("No valid successor found, graph might be unsolvable")

        graph.add_edge(cursor_station.id, nearest_station.id)
        vehicle_load += nearest_station.bike_gap()
        cursor_station = nearest_station
        path.append(cursor_station.id)

    return path


def round(graph: SolvingStationGraph, q: int) -> bool:
    vehicle_load: int = graph.get_station(0).bike_gap()
    max_station_load: int = abs(vehicle_load)
    max_station_id: int = 0

    cursor_station: TargetedStation = graph.get_station(graph.get_successor(0));
    while cursor_station is not None:
        vehicle_load += cursor_station.bike_gap()
        if abs(vehicle_load) > max_station_load:
            max_station_load = vehicle_load
            max_station_id = cursor_station.id
        cursor_station = graph.get_station(graph.get_successor(cursor_station.id))

    if max_station_load <= q:
        return True

    max_station_predecessor_id: int = graph.get_predecessor(max_station_id)
    max_station_successor_id: int = graph.get_successor(max_station_id)
    
    target_station_id: int = choice(graph, max_station_id)
    target_station_predecessor_id: int = graph.get_predecessor(target_station_id)
    target_station_successor_id: int = graph.get_successor(target_station_id)

    graph.remove_edge(max_station_predecessor_id, max_station_id)
    graph.remove_edge(max_station_id, max_station_successor_id)
    graph.remove_edge(target_station_predecessor_id, target_station_id)
    graph.remove_edge(target_station_id, target_station_successor_id)

    graph.add_edge(max_station_predecessor_id, target_station_id)
    graph.add_edge(target_station_id, max_station_successor_id)
    graph.add_edge(target_station_predecessor_id, max_station_id)
    graph.add_edge(max_station_id, target_station_successor_id)

    return False


def choice(graph: SolvingStationGraph, station_id: int) -> int:
    """
    On la permute avec une station dans L[t’+1:] ou t' correspond à la station station_id
Si la t ème station est une station surstocké -> on récupère la première stations sous stockés t’’ (t’’ minimum dans L[t‘+1:]) tel que 0 <= z(t’’) <= q
A l’inverse, on récupère une station sous stocké t’’ tel que t’’ soit le minimum dans L[t’+1:] tel que 0 <= z(t’’) <= q
Dès qu’on obtient tout dans le bon intervalle, tout est ok.
    """
    return 0



def method1(graph: SolvingStationGraph, q: int, alpha: int):
    path = create_path(graph, q, alpha)
    N=0
    while not round(graph, path, q) and N < 1000:
        N+=1



