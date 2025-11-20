"""
Amélioration de solution OPT-2
"""

from src.solver.graph import SolvingStationGraph

def opt2(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000):
    """
    Optimisation 2-opt : améliore un tour existant en inversant des segments
    Suppose que le graphe contient déjà un tour valide

    :param graph: Le graphe avec un tour initial (doit être connexe)
    :param vehicle_capacity: Capacité du camion (pour vérifier la faisabilité)
    :param max_iterations: Nombre maximum d'itérations sans amélioration.
    """


    turn = get_turn(graph)
    n = len(turn)
    distance_cache = {}

    def get_distance(id1: int, id2: int) -> float:
        """Calcule la distance entre deux stations avec memoization"""
        if (id1, id2) not in distance_cache:
            distance_cache[(id1, id2)] = graph.get_station(id1).distance_to(graph.get_station(id2))
        return distance_cache[(id1, id2)]

    def calculate_total_distance(tour: list[int]) -> float:
        """Calcule la distance totale d'un tour"""
        total = 0.0
        for i in range(len(tour) - 1):
            total += get_distance(tour[i], tour[i+1])
        return total

    def try_improve() -> list[int] | None:
        """Cherche une amélioration, retourne le nouveau tour ou None"""
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                current_dist = get_distance(turn[i - 1], turn[i]) + get_distance(turn[j], turn[j + 1])
                new_dist = get_distance(turn[i - 1], turn[j]) + get_distance(turn[i], turn[j + 1])

                if new_dist < current_dist:
                    new_turn = turn[:i] + turn[i:j + 1][::-1] + turn[j + 1:]
                    if is_turn_feasible(graph, new_turn, vehicle_capacity):
                        return new_turn
        return None

    for iteration in range(max_iterations):
        turn = try_improve()
        if turn is None:
            break
        apply_turn(graph, turn)

def is_turn_feasible(graph: SolvingStationGraph, turn: list[int], vehicle_capacity: int) -> bool:
    """
    Vérifie si un tour respecte les contraintes de capacité
    :param graph: Le graphe
    :param turn: Liste des IDs dans l'ordre du tour
    :param vehicle_capacity: Capacité du véhicule
    :return: True si le tour est faisable
    """
    vehicle_load = 0

    for i in range(1, len(turn)):  # Commencer après le dépôt
        station = graph.get_station(turn[i])
        vehicle_load += station.bike_gap()

        if vehicle_load < 0 or vehicle_load > vehicle_capacity:
            return False

    return True


def apply_turn(graph: SolvingStationGraph, turn: list[int]):
    """
    Applique un nouveau tour au graphe en reconstruisant les ar�tes
    :param graph: Le graphe à modifier
    :param turn: Liste des IDs dans le nouvel ordre
    """
    for (a,b) in graph.list_edges():
        graph.remove_edge(a, b)

    for i in range(len(turn) - 1):
        graph.add_edge(turn[i], turn[i+1])

    graph.add_edge(turn[-1], turn[0])

def get_turn(graph: SolvingStationGraph) -> list[int]:
    """
    Récupère le tour actuel du graphe sous forme de liste de numéros de stations.
    :return: Liste des numéros de station dans l'ordre du tour
    """
    turn = []
    current_number = 0
    visited = set()

    while current_number is not None and current_number not in visited:
        turn.append(current_number)
        visited.add(current_number)
        current_number = graph.get_successor(current_number)

    return turn