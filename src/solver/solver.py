from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph

def create_graph(stations: list[TargetedStation], depot_station: Station) -> SolvingStationGraph:
    """
    Crée un graphe à partir d'une liste de stations
    :param stations: Liste de stations avec leurs objectifs et score actuel
    :param depot_station: Station correspondant au dépot
    :return: Le graphe nécessaire pour résoudre le problème
    """
    targeted_depot_station = TargetedStation.from_station(depot_station, 0, 0)
    graph = SolvingStationGraph(targeted_depot_station)

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
        if station.id != 0:
            gap: int = station.bike_gap()
            if abs(gap) < q//2:
                return False
            total += station.bike_gap()

    return total == 0




