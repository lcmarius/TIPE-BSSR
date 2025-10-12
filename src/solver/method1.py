import math
import random

from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph
from src.solver.solver import is_graph_solvable


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
        nearest_station: TargetedStation | None = graph.get_nearest_neighbor(
            cursor_station.id,
            lambda s:
                s.id != 0 and
                s.id != cursor_station.id and
                graph.get_predecessor(s.id) is None and
                alpha <= vehicle_load + s.bike_gap() <= q + alpha
        )

        if nearest_station is None:
            raise Exception("No valid successor found, graph might be unsolvable")

        graph.add_edge(cursor_station.id, nearest_station.id)
        vehicle_load += nearest_station.bike_gap()
        cursor_station = nearest_station

    graph.add_edge(cursor_station.id, 0)


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

    cursor_station: TargetedStation = graph.get_station(graph.get_successor(0))
    while cursor_station is not None and cursor_station.id != 0:
        vehicle_load += cursor_station.bike_gap()
        if abs(vehicle_load) > abs(max_station_load):
            max_station_load = vehicle_load
            max_station_id = cursor_station.id
        cursor_station = graph.get_station(graph.get_successor(cursor_station.id))


    if max_station_load <= vehicle_capacity:
        return True

    max_station_predecessor_id: int = graph.get_predecessor(max_station_id)
    max_station_successor_id: int = graph.get_successor(max_station_id)

    target_station_id: int = choice(graph, max_station_id, max_station_load, vehicle_capacity)
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
    while cursor_id is not None and cursor_id != 0:
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
        print("N: ", N)
        N+=1


def test_method1():
    """
    Test de la méthode 1 avec un graphe simple
    """
    print("=== Test de la méthode 1 ===\n")

    # Paramètres
    vehicle_capacity = 20  # Capacité du camion
    alpha = 0 # Paramètre d'optimisation

    # Création du dépôt (station 0)
    depot = Station(0, "Dépôt", 50, "1 Rue du Dépôt", -1.5536, 47.2173)

    # Création des stations avec bike_gap qui respectent les conditions:
    # - Somme des bike_gap = 0
    # - |bike_gap| < vehicle_capacity/2 = 10

    # Station 1: bike_gap = +6 (loading - trop de vélos, besoin de retirer 6)
    s1 = TargetedStation(1, "Station A", 20, "10 Rue A", -1.5500, 47.2200,
                         bike_count=16, bike_target=10)  # gap = +6

    # Station 2: bike_gap = +2 (loading - trop de vélos, besoin de retirer 2)
    s2 = TargetedStation(2, "Station B", 15, "20 Rue B", -1.5600, 47.2100,
                         bike_count=12, bike_target=10)  # gap = +2

    # Station 3: bike_gap = -4 (unloading - pas assez de vélos, besoin d'ajouter 4)
    s3 = TargetedStation(3, "Station C", 18, "30 Rue C", -1.5400, 47.2250,
                         bike_count=5, bike_target=9)  # gap = -4

    # Station 4: bike_gap = -4 (unloading - pas assez de vélos, besoin d'ajouter 4)
    s4 = TargetedStation(4, "Station D", 16, "40 Rue D", -1.5700, 47.2050,
                         bike_count=3, bike_target=7)  # gap = -4

    # Vérification: somme = 6 + 2 - 4 - 4 = 0 ✓

    # Création du graphe
    graph = SolvingStationGraph(depot)
    graph.add_station(s1)
    graph.add_station(s2)
    graph.add_station(s3)
    graph.add_station(s4)

    print(f"Graphe créé avec {graph.size()} stations:")
    print(f"  - {depot.name} (Dépôt)")
    for station in [s1, s2, s3, s4]:
        print(f"  - {station.name}: bike_gap = {station.bike_gap()}")

    print(f"\nSomme des bike_gap: {sum(s.bike_gap() for s in [s1, s2, s3, s4])}")
    print(f"Capacité du véhicule: {vehicle_capacity}")
    print(f"Alpha: {alpha}\n")

    assert is_graph_solvable(graph, vehicle_capacity)

    # Exécution de la méthode 1
    print("Exécution de la méthode 1...")
    try:
        method1(graph, vehicle_capacity, alpha)
        print("\nMéthode 1 terminée avec succès!")

        # Affichage du chemin résultant
        print("\nChemin résultant:")
        edges = graph.list_edges()
        print(f"  Nombre d'arêtes: {len(edges)}")

        # Reconstruction et affichage du chemin
        print("\n  Chemin du camion:")
        current_id = 0
        visited = set()
        vehicle_load = 0

        while current_id is not None and current_id not in visited:
            visited.add(current_id)
            station = graph.get_station(current_id)
            print(f"    Station {current_id} ({station.name}): charge = {vehicle_load} vélos")

            successor = graph.get_successor(current_id)
            if successor is not None:
                next_station = graph.get_station(successor)
                vehicle_load += next_station.bike_gap()

            current_id = successor

    except Exception as e:
        print(f"\n✗ Erreur lors de l'exécution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_method1()
