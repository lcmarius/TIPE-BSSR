from enum import Enum

from src.objects.station import TargetedStation, Station
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.builder.method2 import method2
from src.solver.algorithm.incrementer.ils import ils
from src.solver.algorithm.incrementer.opt2 import opt2
from src.solver.algorithm.incrementer.or_opt import or_opt
from src.solver.graph import SolvingStationGraph

from src.solver.map import Map
from src.solver.reviewer import SolutionMetrics, review_solution


class SolvingAlgorithmBuilder(Enum):
    METHOD_1 = 1
    METHOD_2 = 2

class SolvingAlgorithmImprover(Enum):
    OPT_2 = 1
    OR_OPT = 2
    ILS = 3

def create_graph(stations: list[TargetedStation], depot_station: Station, map: Map) -> SolvingStationGraph:
    """Crée un graphe de résolution à partir de la liste des stations, en n'incluant que celles dont le bike_gap est non nul (et le dépôt). """
    graph = SolvingStationGraph(map, depot_station)

    for station in stations:
        if station.bike_gap() != 0:
            graph.add_station(station)





    return graph

def is_graph_solvable(graph: SolvingStationGraph, q: int) -> bool:
    """Vérifie si le graphe est solvable, c'est-à-dire si les contraintes de capacité sont respectées et si le bike_gap total est nul."""
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
    """Résout le problème de rééquilibrage des vélos en utilisant les algorithmes spécifiés"""

    print("Preloading travel times...")
    graph.preload_times()
    print("Travel times preloaded.")

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
            elif improver == SolvingAlgorithmImprover.OR_OPT:
                or_opt(graph, capacity, max_iterations=improver_max_iterations)
            elif improver == SolvingAlgorithmImprover.ILS:
                ils(graph, capacity)
            else:
                raise Exception("Unknown solving algorithm improver")

    return review_solution(graph, capacity)


def improve(graph: SolvingStationGraph, capacity: int,
            improvers: list[SolvingAlgorithmImprover],
            improver_max_iterations: int = 1000) -> SolutionMetrics:
    """Applique une chaîne d'améliorations à un graphe contenant déjà une tournée valide."""
    graph.preload_times()
    for improver in improvers:
        if improver == SolvingAlgorithmImprover.OPT_2:
            opt2(graph, capacity, max_iterations=improver_max_iterations)
        elif improver == SolvingAlgorithmImprover.OR_OPT:
            or_opt(graph, capacity, max_iterations=improver_max_iterations)
        elif improver == SolvingAlgorithmImprover.ILS:
            ils(graph, capacity)
        else:
            raise Exception("Unknown solving algorithm improver")
    return review_solution(graph, capacity)