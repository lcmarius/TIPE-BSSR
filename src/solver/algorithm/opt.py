"""
Amélioration de solution OPT-2
"""

from src.solver.graph import SolvingStationGraph


def get_distance(graph: SolvingStationGraph, distance_cache, id1: int, id2: int) -> float:
    """Calcule la distance entre deux stations avec memoization"""
    if (id1, id2) not in distance_cache:
        distance_cache[(id1, id2)] = graph.get_station(id1).distance_to(graph.get_station(id2))
    return distance_cache[(id1, id2)]


def calculate_total_distance(graph: SolvingStationGraph, distance_cache, tour: list[int]) -> float:
    """Calcule la distance totale d'un tour"""
    total = 0.0
    for i in range(len(tour) - 1):
        total += get_distance(graph, distance_cache, tour[i], tour[i + 1])
    return total

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


    def try_improve() -> list[int] | None:
        """Cherche une amélioration, retourne le nouveau tour ou None"""
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                current_dist = get_distance(graph, distance_cache, turn[i - 1], turn[i]) + get_distance(graph, distance_cache, turn[j], turn[j + 1])
                new_dist = get_distance(graph, distance_cache, turn[i - 1], turn[j]) + get_distance(graph, distance_cache, turn[i], turn[j + 1])

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

def opt3(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000):
    """
    Optimisation 3-opt : améliore un tour existant en reconnectant 3 segments
    Suppose que le graphe contient déjà un tour valide

    :param graph: Le graphe avec un tour initial (doit être connexe)
    :param vehicle_capacity: Capacité du camion (pour vérifier la faisabilité)
    :param max_iterations: Nombre maximum d'itérations sans amélioration.
    """

    turn = get_turn(graph)
    n = len(turn)
    distance_cache = {}

    def try_improve() -> list[int] | None:
        current_total_dist = calculate_total_distance(graph, distance_cache, turn)

        for i in range(1, n - 3):
            for j in range(i + 2, n - 2):
                for k in range(j + 2, n - 1):
                    reconnections = generate_3opt_reconnections(turn, i, j, k)

                    # Chercher la meilleure permutation parmi les 7.
                    best_turn = None
                    best_dist = current_total_dist

                    for new_turn in reconnections:
                        new_dist = calculate_total_distance(graph, distance_cache, new_turn)

                        if new_dist < best_dist and is_turn_feasible(graph, new_turn, vehicle_capacity):
                            best_dist = new_dist
                            best_turn = new_turn

                    if best_turn is not None:
                        return best_turn
        return None

    for iteration in range(max_iterations):
        turn = try_improve()
        if turn is None:
            return

        apply_turn(graph, turn)


def generate_3opt_reconnections(tour: list[int], i: int, j: int, k: int) -> list[list[int]]:
    """
    Génère les 7 reconnexions possibles pour 3-opt

    On a 4 segments:
    - A = tour[0:i+1]   (jusqu'à i inclus)
    - B = tour[i+1:j+1] (de i+1 à j inclus)
    - C = tour[j+1:k+1] (de j+1 à k inclus)
    - D = tour[k+1:]    (de k+1 à la fin)

    Tour original: A-B-C-D

    Les 7 reconnexions possibles (hors tour original):
    1. A-B-reversed(C)-D  (2-opt sur segment C)
    2. A-reversed(B)-C-D  (2-opt sur segment B)
    3. A-C-B-D            (swap B et C)
    4. A-reversed(C)-B-D  (inverse C puis swap)
    5. A-C-reversed(B)-D  (inverse B puis swap)
    6. A-reversed(B)-reversed(C)-D  (inverse B et C)
    7. A-reversed(C)-reversed(B)-D  (inverse C et B puis swap)

    :param tour: Le tour complet
    :param i: Index de fin du segment A
    :param j: Index de fin du segment B
    :param k: Index de fin du segment C
    :return: Liste des sept reconnexions possibles.
    """
    # Extraire les 4 segments
    a = tour[0:i+1]
    b = tour[i+1:j+1]
    c = tour[j+1:k+1]
    d = tour[k+1:]

    # Les 7 reconnexions possibles
    reconnections = [
        a + b + c[::-1] + d,           # 1. Inverse C (2-opt)
        a + b[::-1] + c + d,           # 2. Inverse B (2-opt)
        a + c + b + d,                 # 3. Swap B et C
        a + c[::-1] + b + d,           # 4. Inverse C puis swap
        a + c + b[::-1] + d,           # 5. Swap puis inverse B
        a + b[::-1] + c[::-1] + d,     # 6. Inverse B et C
        a + c[::-1] + b[::-1] + d,     # 7. Inverse tout puis swap
    ]

    return reconnections


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