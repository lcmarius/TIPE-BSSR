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
    Calcule les bornes inférieure et supérieure en utilisant Held-Karp (1-tree)
    - Lower bound: Held-Karp (1-tree)
    - Upper bound: 2 × Held-Karp (garantit upper ≥ lower)

    :param graph: Le graphe du problème
    :return: (lower_bound, upper_bound)
    """
    stations = graph.list_stations()

    if len(stations) <= 1:
        return 0.0, 0.0

    non_depot = [s for s in stations if s.number != 0]
    if len(non_depot) == 0:
        return 0.0, 0.0

    distance = 0.0
    visited = {non_depot[0].number}
    remaining = {s.number for s in non_depot[1:]}

    while remaining:
        min_edge = float('inf')
        min_node = None

        for v_id in visited:
            v_station = graph.get_station(v_id)
            for r_id in remaining:
                r_station = graph.get_station(r_id)
                dist = v_station.distance_to(r_station)
                if dist < min_edge:
                    min_edge = dist
                    min_node = r_id

        if min_node is not None:
            distance += min_edge
            visited.add(min_node)
            remaining.remove(min_node)

    depot = graph.get_station(0)
    edges = sorted([depot.distance_to(s) for s in non_depot])

    # Arrête du dépot au premier nœud, et arrête du dernier nœud au dépot
    two_shortest = sum(edges[:2]) if len(edges) >= 2 else sum(edges)

    held_karp = mst_distance + two_shortest

    return held_karp, 2*held_karp



