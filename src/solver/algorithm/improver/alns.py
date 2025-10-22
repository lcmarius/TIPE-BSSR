"""
Amélioration de solution ALNS (Adaptive Large Neighborhood Search)
"""
import random
import math
from typing import List, Callable
from src.solver.graph import SolvingStationGraph
from src.objects.station import TargetedStation

def alns(graph: SolvingStationGraph, vehicle_capacity: int, max_iterations: int = 1000,
         removal_size: int = 5, seed: int = None):
    """
    Adaptive Large Neighborhood Search

    Alterne entre destruction (removal) et réparation (insertion) avec:
    - Adaptive weights: favorise les operators qui trouvent de bonnes solutions
    - Simulated Annealing: accepte temporairement des solutions pires

    :param graph: Graphe avec un tour initial valide
    :param vehicle_capacity: Capacité du camion
    :param max_iterations: Nombre d'itérations
    :param removal_size: Nombre de stations à retirer à chaque itération
    :param seed: Graine aléatoire pour reproductibilité
    """
    if seed is not None:
        random.seed(seed)

    initial_turn = graph.get_turn()
    if len(initial_turn) < 2:
        return

    # Distance cache
    distance_cache = {}

    def get_distance(id1: int, id2: int) -> float:
        if (id1, id2) not in distance_cache:
            distance_cache[(id1, id2)] = graph.get_station(id1).distance_to(graph.get_station(id2))
        return distance_cache[(id1, id2)]

    def calculate_tour_distance(tour: List[int]) -> float:
        total = 0.0
        for i in range(len(tour) - 1):
            total += get_distance(tour[i], tour[i + 1])
        return total

    current_tour = initial_turn[:]
    current_distance = calculate_tour_distance(current_tour)
    best_tour = current_tour[:]
    best_distance = current_distance

    destroy_operators = [
        random_removal,
        worst_removal,
        shaw_removal
    ]

    # Adaptive weights (initialement égaux)
    destroy_weights = [1.0, 1.0, 1.0]

    # Paramètres Simulated Annealing
    temperature = current_distance * 0.1
    cooling_rate = 0.995
    min_temperature = 0.01

    for iteration in range(max_iterations):
        # 1. Sélection de l'operator (roulette wheel)
        destroy_op_index = roulette_wheel_selection(destroy_weights)
        destroy_op = destroy_operators[destroy_op_index]

        # 2. Destruction: retirer k stations
        removed_stations = destroy_op(graph, current_tour, removal_size, get_distance)

        # 3. Réparation: réinsérer les stations
        new_tour = greedy_repair(graph, current_tour, removed_stations, vehicle_capacity)

        if new_tour is None:
            continue  # Échec de réparation

        # 4. Évaluation
        new_distance = calculate_tour_distance(new_tour)

        # 5. Critère d'acceptation (Simulated Annealing)
        accept = False
        score = 0

        if new_distance < best_distance:
            # Nouvelle meilleure solution globale
            best_tour = new_tour[:]
            best_distance = new_distance
            current_tour = new_tour[:]
            current_distance = new_distance
            accept = True
            score = 15
        elif new_distance < current_distance:
            current_tour = new_tour[:]
            current_distance = new_distance
            accept = True
            score = 10
        else:
            delta = new_distance - current_distance
            probability = math.exp(-delta / temperature) if temperature > 0 else 0
            if random.random() < probability:
                current_tour = new_tour[:]
                current_distance = new_distance
                accept = True
                score = 5

        if accept:
            destroy_weights[destroy_op_index] += score

        temperature = max(min_temperature, temperature * cooling_rate)

    apply_turn(graph, best_tour)


# ============================================================================
# DESTROY OPERATORS
# ============================================================================

def random_removal(graph: SolvingStationGraph, tour: List[int], k: int,
                   get_distance: Callable) -> List[TargetedStation]:
    """
    Retire k stations aléatoirement (sauf le dépôt)
    """
    # Stations disponibles (hors dépôt)
    candidates = [sid for sid in tour if sid != 0]

    k = min(k, len(candidates))
    removed_ids = random.sample(candidates, k)

    return [graph.get_station(sid) for sid in removed_ids]


def worst_removal(graph: SolvingStationGraph, tour: List[int], k: int,
                  get_distance: Callable) -> List[TargetedStation]:
    """
    Retire les k stations qui contribuent le plus à la distance totale
    (coût de retrait = distance économisée en retirant la station)
    """
    candidates = [sid for sid in tour if sid != 0]

    # Calculer le coût de retrait de chaque station
    removal_costs = []
    tour_index = {sid: i for i, sid in enumerate(tour)}

    for sid in candidates:
        idx = tour_index[sid]
        prev_id = tour[idx - 1]
        next_id = tour[idx + 1] if idx + 1 < len(tour) else tour[0]

        # Coût actuel: prev->station + station->next
        current_cost = get_distance(prev_id, sid) + get_distance(sid, next_id)

        # Coût après retrait: prev->next directement
        new_cost = get_distance(prev_id, next_id)

        # Saving = économie réalisée
        saving = current_cost - new_cost

        removal_costs.append((saving, sid))

    # Trier par saving décroissant (retirer celles qui économisent le plus)
    removal_costs.sort(reverse=True)

    k = min(k, len(removal_costs))
    removed_ids = [sid for _, sid in removal_costs[:k]]

    return [graph.get_station(sid) for sid in removed_ids]


def shaw_removal(graph: SolvingStationGraph, tour: List[int], k: int,
                 get_distance: Callable) -> List[TargetedStation]:
    """
    Retire k stations "similaires" (proches géographiquement)

    1. Choisir une station seed aléatoirement
    2. Retirer les k-1 stations les plus proches de seed
    """
    candidates = [sid for sid in tour if sid != 0]

    if not candidates:
        return []

    # 1. Station seed aléatoire
    seed_id = random.choice(candidates)
    seed_station = graph.get_station(seed_id)

    # 2. Calculer distance à seed pour toutes les autres
    distances = []
    for sid in candidates:
        if sid != seed_id:
            station = graph.get_station(sid)
            dist = seed_station.distance_to(station)
            distances.append((dist, sid))

    # 3. Trier par proximité
    distances.sort()

    # 4. Retirer seed + k-1 plus proches
    k = min(k, len(candidates))
    removed_ids = [seed_id]
    removed_ids.extend([sid for _, sid in distances[:k-1]])

    return [graph.get_station(sid) for sid in removed_ids]


# ============================================================================
# REPAIR OPERATOR
# ============================================================================

def greedy_repair(graph: SolvingStationGraph, current_tour: List[int],
                  removed_stations: List[TargetedStation],
                  vehicle_capacity: int) -> List[int] | None:
    """
    Réinsère les stations retirées en utilisant l'insertion la moins coûteuse
    (cheapest insertion) tout en respectant les contraintes de capacité
    """
    # Copier le tour actuel (sans les stations retirées)
    removed_ids = {s.id for s in removed_stations}
    tour = [sid for sid in current_tour if sid not in removed_ids]

    # Cache de distances
    def get_distance_cached(id1: int, id2: int) -> float:
        return graph.get_station(id1).distance_to(graph.get_station(id2))

    # Réinsérer chaque station
    for station in removed_stations:
        # Trouver la meilleure position d'insertion
        best_position = None
        best_cost = float('inf')

        for i in range(len(tour)):
            prev_id = tour[i]
            next_id = tour[i + 1] if i + 1 < len(tour) else tour[0]

            # Coût d'insertion entre prev et next
            cost_before = get_distance_cached(prev_id, next_id)
            cost_after = get_distance_cached(prev_id, station.id) + get_distance_cached(station.id, next_id)
            insertion_cost = cost_after - cost_before

            # Vérifier faisabilité
            if is_insertion_feasible_simple(tour, station, i, vehicle_capacity, graph):
                if insertion_cost < best_cost:
                    best_cost = insertion_cost
                    best_position = i + 1

        if best_position is None:
            # Échec: impossible de réinsérer cette station
            return None

        # Insérer à la meilleure position
        tour.insert(best_position, station.id)

    return tour


def is_insertion_feasible_simple(tour: List[int], station: TargetedStation,
                                  insert_after_index: int, vehicle_capacity: int,
                                  graph: SolvingStationGraph) -> bool:
    """
    Vérifie si insérer station après tour[insert_after_index] est faisable
    (respecte 0 <= load <= capacity tout le long du tour)
    """
    # Reconstruire le tour avec la nouvelle station
    new_tour = tour[:insert_after_index + 1] + [station.id] + tour[insert_after_index + 1:]

    # Vérifier les charges tout le long
    vehicle_load = 0
    for sid in new_tour:
        if sid == 0:
            continue

        s = graph.get_station(sid) if sid != station.id else station
        vehicle_load += s.bike_gap()

        if vehicle_load < 0 or vehicle_load > vehicle_capacity:
            return False

    return True


# ============================================================================
# UTILITAIRES
# ============================================================================

def roulette_wheel_selection(weights: List[float]) -> int:
    """
    Sélection par roulette wheel (probabilité proportionnelle aux poids)
    """
    total = sum(weights)
    r = random.random() * total
    cumulative = 0.0

    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return i

    return len(weights) - 1  # Fallback


def apply_turn(graph: SolvingStationGraph, turn: List[int]) -> None:
    """
    Applique un tour au graphe (remplace tous les edges)
    """
    # Supprimer tous les edges existants
    for sid in list(graph.successors.keys()):
        graph.successors[sid] = None
        graph.predecessors[sid] = None

    # Ajouter les nouveaux edges
    for i in range(len(turn) - 1):
        graph.successors[turn[i]] = turn[i + 1]
        graph.predecessors[turn[i + 1]] = turn[i]

    # Boucler sur le dépôt
    if turn:
        graph.successors[turn[-1]] = turn[0]
        graph.predecessors[turn[0]] = turn[-1]
