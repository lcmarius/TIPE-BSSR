"""
Méthode 1 de l'étude : Construction gloutonne faisable
"""


import random

from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph
from src.solver.graph_viewer import GraphSnapshot


def greedy(graph: SolvingStationGraph, vehicle_capacity: int):
    """
    Méthode de création de chemin faisable par approche gloutonne
    :param graph: Le graphe du problème
    :param vehicle_capacity: Capacité du camion
    :return: Créer un chemin faisable dans le graphe
    """
    snapshots = [GraphSnapshot(graph, "État initial", [], None)]

    vehicle_load: int = 0

    cursor_station: TargetedStation = graph.get_nearest_neighbor(0, lambda s: s.id != 0 and s.is_loading())
    graph.add_edge(0, cursor_station.id)
    vehicle_load += cursor_station.bike_gap()
    snapshots.append(GraphSnapshot(graph, f"Première station: {cursor_station.name} (charge: {vehicle_load})",[cursor_station.id], (0, cursor_station.id)))

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
        snapshots.append(GraphSnapshot(graph, f"Ajout station {nearest_station.name} (charge: {vehicle_load})",[nearest_station.id], (cursor_station.id, nearest_station.id)))
        cursor_station = nearest_station

    graph.add_edge(cursor_station.id, 0)
    snapshots.append(GraphSnapshot(graph, f"Retour au dépôt (charge finale: {vehicle_load})", [0], (cursor_station.id, 0)))
    return snapshots