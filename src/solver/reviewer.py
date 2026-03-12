from dataclasses import dataclass
from src.solver.graph import SolvingStationGraph

@dataclass
class SolutionMetrics:
    """Métriques d'évaluation d'une solution"""
    solved: bool
    distance: float          # Distance totale en mètres (plus bas = mieux)
    score: float  # Score [0, 1] (plus haut = mieux)


def assert_solution(solution: SolvingStationGraph):
    """
    Vérifie si le graphe donné contient une solution valide (un chemin qui visite toutes les stations)
    :param solution: Le graphe à vérifier
    :return: True si c'est une solution valide
    """

    if not solution.is_connex():
        raise Exception("Le graphe n'est pas connexe.")

    visited = set()
    current_id = 0
    gap=0

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        gap+=solution.get_station(current_id).bike_gap()
        current_id = solution.get_successor(current_id)

    all_stations = {s.number for s in solution.list_stations() if s.number != 0}

    if gap != 0:
        raise Exception("Le graphe n'a pas un bike_gap total de 0.")

    if not all_stations.issubset(visited):
        raise Exception("Le graphe ne visite pas toutes les stations.")

def review_solution(graph: SolvingStationGraph) -> SolutionMetrics:
    """
    Évalue une solution de manière détaillée
    :param graph: Le graphe avec la solution (chemin construit)
    :return: Métriques complètes de la solution
    """
    assert_solution(graph)

    distance = 0.0
    current_id = 0
    visited = set()

    while current_id is not None and current_id not in visited:
        visited.add(current_id)
        station = graph.get_station(current_id)

        successor = graph.get_successor(current_id)
        if successor is not None:
            next_station = graph.get_station(successor)
            distance += graph.get_distance(station, next_station)

        current_id = successor

    lower_bound, upper_bound = compute_bounds(graph)

    if upper_bound <= lower_bound:
        score = 1.0
    else:
        score = 1.0 - (distance - lower_bound) / (upper_bound - lower_bound)

    return SolutionMetrics(
        distance=distance,
        score=score,
        solved=True
    )


def compute_bounds(graph: SolvingStationGraph) -> tuple[float, float]:
    """
    Calcule les bornes inférieure et supérieure pour un TSP asymétrique.

    Lower bound : pour chaque station, l'arête sortante la moins chère est
    nécessaire (chaque nœud est quitté exactement une fois dans un cycle
    hamiltonien). Idem pour les arêtes entrantes. On prend le max des deux
    sommes pour une borne plus serrée.

    Upper bound : 2 × lower bound (heuristique simple).

    :param graph: Le graphe du problème
    :return: (lower_bound, upper_bound)
    """
    stations = graph.list_stations()

    if len(stations) <= 1:
        return 0.0, 0.0

    min_outgoing_sum = 0.0
    min_incoming_sum = 0.0

    for s in stations:
        others = [o for o in stations if o.number != s.number]
        if others:
            min_outgoing_sum += min(graph.get_distance(s, o) for o in others)
            min_incoming_sum += min(graph.get_distance(o, s) for o in others)

    lower_bound = max(min_outgoing_sum, min_incoming_sum)
    return lower_bound, 2 * lower_bound



