from dataclasses import dataclass
from src.solver.graph import SolvingStationGraph

@dataclass
class SolutionMetrics:
    """Métriques d'évaluation d'une solution"""
    distance: float          # Distance totale en mètres (plus bas = mieux)
    score: float  # Score [0, 1] (plus haut = mieux)


def review_solution(graph: SolvingStationGraph) -> SolutionMetrics:
    """
    Évalue une solution de manière détaillée
    :param graph: Le graphe avec la solution (chemin construit)
    :return: Métriques complètes de la solution
    """
    distance = 0.0
    current_id = 0
    visited = set()

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        station = graph.get_station(current_id)

        successor = graph.get_successor(current_id)
        if successor is not None:
            next_station = graph.get_station(successor)
            distance += station.distance_to(next_station)

        current_id = successor

    total_bike_gap = 0.0
    nb_stations = 0

    for station in graph.list_stations():
        if station.id != 0:
            total_bike_gap += abs(station.bike_gap())
            nb_stations += 1

    lower_bound, upper_bound = compute_bounds(graph)

    if upper_bound <= lower_bound:
        score = 1.0
    else:
        score = 1.0 - (distance - lower_bound) / (upper_bound - lower_bound)

    return SolutionMetrics(
        distance=distance,
        score=score
    )


def compute_bounds(graph: SolvingStationGraph) -> tuple[float, float]:
    """
    Calcule les bornes inférieure et supérieure en utilisant MST (Minimum Spanning Tree)
    - Lower bound: MST (borne inf classique du TSP)
    - Upper bound: 2 × MST (approximation classique du TSP)

    :param graph: Le graphe du problème
    :return: (lower_bound, upper_bound)
    """
    stations = graph.list_stations()

    if len(stations) <= 1:
        return 0.0, 0.0

    # Algorithme de Prim pour calculer le MST
    mst_distance = 0.0
    visited = {0}  # Commencer par le dépôt
    remaining = {s.id for s in stations if s.id != 0}

    while remaining:
        min_edge = float('inf')
        next_node = None

        # Trouver l'arête de poids minimum entre visited et remaining
        for v_id in visited:
            v_station = graph.get_station(v_id)
            for r_id in remaining:
                r_station = graph.get_station(r_id)
                dist = v_station.distance_to(r_station)
                if dist < min_edge:
                    min_edge = dist
                    next_node = r_id

        if next_node is not None:
            mst_distance += min_edge
            visited.add(next_node)
            remaining.remove(next_node)

    lower_bound = mst_distance
    upper_bound = 2 * mst_distance

    return lower_bound, upper_bound


