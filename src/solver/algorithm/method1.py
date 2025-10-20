import random

from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph


def method1(graph: SolvingStationGraph, vehicle_capacity: int):
    """
    Méthode 1 simplifiée : Construction greedy faisable
    :param graph: Le graphe du problème
    :param vehicle_capacity: Capacité du camion
    :return: Créer un chemin faisable dans le graphe
    """
    graph.take_snapshot("État initial", [], None)

    stations = graph.list_stations()
    loading_stations: list[TargetedStation] = []
    for station in stations:
        if station.is_loading():
            loading_stations.append(station)

    vehicle_load: int = 0

    cursor_station: TargetedStation = loading_stations[random.randint(0, len(loading_stations) - 1)]
    graph.add_edge(0, cursor_station.id)
    vehicle_load += cursor_station.bike_gap()
    graph.take_snapshot(f"Première station: {cursor_station.name} (charge: {vehicle_load})",
                       [cursor_station.id], (0, cursor_station.id))

    for i in range(1, graph.size() - 1):
        nearest_station: TargetedStation | None = graph.get_nearest_neighbor(
            cursor_station.id,
            lambda s:
                s.id != 0 and
                s.id != cursor_station.id and
                graph.get_predecessor(s.id) is None and
                0 <= vehicle_load + s.bike_gap() <= vehicle_capacity
        )

        if nearest_station is None:
            raise Exception("No valid successor found, graph might be unsolvable")

        graph.add_edge(cursor_station.id, nearest_station.id)
        vehicle_load += nearest_station.bike_gap()
        graph.take_snapshot(f"Ajout station {nearest_station.name} (charge: {vehicle_load})",
                           [nearest_station.id], (cursor_station.id, nearest_station.id))
        cursor_station = nearest_station

    graph.add_edge(cursor_station.id, 0)
    graph.take_snapshot(f"Retour au dépôt (charge finale: {vehicle_load})", [0], (cursor_station.id, 0))