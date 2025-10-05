import math

from src.objects.station import TargetedStation
from src.solver.graph import SolvingStationGraph
import random

def create_path(graph: SolvingStationGraph, q: int, alpha: int):
    """
    Permet de créer un chemin initial dans le graphe
    alpha ≤ station_load ≤ q + alpha
    :param graph: Graphe du problème
    :param q: Capacité du camion
    :param alpha: Paramètre d'optimisation choisie par l'utilisateur
    :return: Créer le chemin dans le graphe
    """
    stations = graph.list_stations()
    unloading_stations: list[TargetedStation] = []
    loading_stations: list[TargetedStation] = []
    for station in stations:
        if station.is_loading():
            loading_stations.append(station)
        else:
            unloading_stations.append(station)

    vehicle_load: int = 0

    cursor_station: TargetedStation = loading_stations[random.randint(0, len(loading_stations) - 1)]
    graph.add_edge(0, cursor_station.id)
    vehicle_load += cursor_station.bike_gap()

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


def loop(graph: SolvingStationGraph, vehicle_capacity: int) -> bool:
    """
    Réorganise le chemin dans le graphe pour qu'il soit réalisable
    0 < max_station_load < vehicle_capacity
    :param graph: le graphe dans lequel on réorganise le chemin pour qu'il soit réalisable
    :param vehicle_capacity: Capacité du camion
    :return: True si le graphe est réalisable, False sinon
    """
    vehicle_load: int = graph.get_station(0).bike_gap()
    max_station_load: int = vehicle_load
    max_station_id: int = 0

    cursor_station: TargetedStation = graph.get_station(graph.get_successor(0));
    while cursor_station is not None:
        vehicle_load += cursor_station.bike_gap()
        if abs(vehicle_load) > abs(max_station_load):
            max_station_load = vehicle_load
            max_station_id = cursor_station.id
        cursor_station = graph.get_station(graph.get_successor(cursor_station.id))

    if max_station_load <= vehicle_capacity:
        return True

    max_station_predecessor_id: int = graph.get_predecessor(max_station_id)
    max_station_successor_id: int = graph.get_successor(max_station_id)

    target_station_id: int = choice(graph, max_station_id, max_station_load)
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


def choice(graph: SolvingStationGraph, station_id: int, station_load: int, vehicle_capacity: int) -> int:
    """
    Choisit un successeur valide pour la station donnée
    0 < station_load < vehicle_capacity
    :param graph: le graphe dans lequel on cherche un successeur
    :param station_id: station à partir de laquelle on cherche un successeur
    :param station_load: vélos du camion à la station donnée
    :param vehicle_capacity: Capacité du camion
    :return: ID de la station à échanger
    """

    station: TargetedStation = graph.get_station(station_id)
    cursor_id: int | None = graph.get_successor(station_id)
    while cursor_id is not None:
        cursor: TargetedStation = graph.get_station(cursor_id)
        station_load += cursor.bike_gap()

        if 0 <= station_load <= vehicle_capacity:
            if math.copysign(station.bike_gap(), cursor.bike_gap()) == -1:
                return cursor_id

        cursor_id = graph.get_successor(cursor_id)

    raise Exception("No valid successor found, graph might be unsolvable")



def method1(graph: SolvingStationGraph, vehicle_capacity: int, alpha: int):
    """
    Application de la méthode 1 pour résoudre le problème
    :param graph: Le graphe du problème
    :param vehicle_capacity: Capacité du camion
    :param alpha: Paramètre d'optimisation choisie par l'utilisateur
    :return: Créer un chemin optimale dans le graphe
    """
    create_path(graph, vehicle_capacity, alpha)
    N=0
    while not loop(graph, vehicle_capacity) and N < 1000:
        N+=1



