from src.objects.station import TargetedStation, Station
from src.solver.algorithm.method1 import method1
from src.solver.algorithm.method2 import method2
from src.solver.algorithm.opt import opt2, opt3
from src.solver.graph import SolvingStationGraph
from enum import Enum

from src.solver.reviewer import SolutionMetrics, review_solution


class SolvingAlgorithmBuilder(Enum):
    METHOD_1 = 1
    METHOD_2 = 2

class SolvingAlgorithmImprover(Enum):
    OPT_2 = 1
    OPT_3 = 2

def create_graph(stations: list[TargetedStation], depot_station: Station) -> SolvingStationGraph:
    """
    Crée un graphe à partir d'une liste de stations
    :param stations: Liste de stations avec leurs objectifs et score actuel
    :param depot_station: Station correspondant au dépot
    :return: Le graphe nécessaire pour résoudre le problème
    """
    graph = SolvingStationGraph(depot_station)

    for station in stations:
        if station.bike_gap() != 0:
            graph.add_station(station)




    return graph

def is_graph_solvable(graph: SolvingStationGraph, q: int) -> bool:
    """
    Conditions pour qu'un graphe soit solvable :
    – La somme des bike_gap doit être nulle (le nombre total de vélos à déplacer doit être égal au nombre total de vélos à ajouter).
    - Pour Tout bike_gape : |bike_gape| < q/2
    :param graph: Le graphe à vérifier
    :param q: Capacité du camion
    :return: True si le graphe est solvable, False sinon
    """
    total: int = 0
    for station in graph.list_stations():
        if station.number != 0:
            gap: int = station.bike_gap()
            if abs(gap) > q//2:
                return False
            total += station.bike_gap()

    return total == 0

def solve(graph: SolvingStationGraph, capacity: int,
          builder: SolvingAlgorithmBuilder,
          improvers: list[SolvingAlgorithmImprover] = None, improver_max_iterations: int = 1000) -> SolutionMetrics:
    """
    Résout le problème de rééquilibrage des vélos en utilisant les algorithmes spécifiés
    :param graph: Le graphe du problème
    :param capacity: Capacité du camion
    :param builder: Algorithme de construction du chemin initial
    :param improvers: Liste d'algorithmes d'amélioration à appliquer après la construction initiale
    :param improver_max_iterations: Nombre maximum d'itérations pour chaque algorithme d'amélioration
    :return: None (le graphe est modifié en place pour contenir la solution
    """

    if builder == SolvingAlgorithmBuilder.METHOD_1:
        method1(graph, capacity)
    elif builder == SolvingAlgorithmBuilder.METHOD_2:
        method2(graph, capacity)
    else:
        raise Exception("Unknown solving algorithm builder")

    if improvers:
        for improver in improvers:
            if improver == SolvingAlgorithmImprover.OPT_2:
                opt2(graph, capacity, max_iterations=improver_max_iterations)
            elif improver == SolvingAlgorithmImprover.OPT_3:
                opt3(graph, capacity, max_iterations=improver_max_iterations)
            else:
                raise Exception("Unknown solving algorithm improver")

    return review_solution(graph)