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
        nearest_station: TargetedStation | None = graph.get_nearest_neighbor(
            cursor_station.id,
            lambda s: alpha <= vehicle_load + s.bike_gape() <= q + alpha
        )

        if nearest_station is None:
            raise Exception("No valid neighbor found, graph might be unsolvable")

        graph.add_edge(cursor_station.id, nearest_station.id)
        vehicle_load += nearest_station.bike_gap()
        cursor_station = nearest_station
        path.append(cursor_station.id)

    return path


def round(graph: SolvingStationGraph, q: int) -> bool:
    vehicle_load = graph.get_station(0).bike_gap()
    max_station_load = abs(vehicle_load)
    max_station_index = 0
    for i in range(1, len(path)):
        station = graph.get_station(path[i])
        vehicle_load += station.bike_gap()
        if abs(vehicle_load) > max_station_load:
            max_station_load = vehicle_load
            max_station_index = i

    if max_station_load <= q:
        return True

    max_station_id = path[max_station_index]
    target_index: int = max_station_index+1 + choice(graph, path[(max_station_index+1):], max_station_id)

    graph.remove_edge(path[max_station_index-1], path[max_station_index])
    graph.remove_edge(path[max_station_index], path[max_station_index+1])
    graph.remove_edge(path[target_index-1], path[target_index])
    graph.remove_edge(path[target_index], path[target_index+1])

    graph.add_edge(path[max_station_index-1], path[target_index])
    graph.add_edge(path[target_index], path[max_station_index+1])
    graph.add_edge(path[target_index-1], max_station_id)
    graph.add_edge(max_station_id, target_index+1)

    # Retirer implémentation path avec liste


    path[max_station_index] = path[target_index]
    path[target_index] = max_station_id

    return False


def choice(graph: SolvingStationGraph, sub_path: list[int], station_id: int) -> int:

    return 0



def method1(graph: SolvingStationGraph, q: int, alpha: int):
    path = create_path(graph, q, alpha)
    N=0
    while not round(graph, path, q) and N < 1000:
        N+=1



