"""
Méthode 3 : Savings Algorithm (Clarke-Wright)
"""

from src.solver.graph import SolvingStationGraph


def method3(graph: SolvingStationGraph, vehicle_capacity: int):
    """
    Savings Algorithm (Clarke-Wright) pour BSSRP

    Fusionne itérativement les routes selon les "savings" : s_ij = d(0,i) + d(0,j) - d(i,j)
    """
    stations = [s for s in graph.list_stations() if s.id != 0]
    if len(stations) == 0:
        return []

    # Calculer savings : économie de distance si on visite i et j dans la même route
    # savings = d(0,i) + d(0,j) - d(i,j)
    depot = graph.get_station(0)
    savings = []

    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            si, sj = stations[i], stations[j]
            s_ij = depot.distance_to(si) + depot.distance_to(sj) - si.distance_to(sj)
            savings.append((s_ij, si.id, sj.id))

    savings.sort(reverse=True, key=lambda x: x[0])

    # Initialiser routes (chaque station = 1 route)
    route_id = 0
    routes = {}
    station_to_route = {}

    for station in stations:
        routes[route_id] = {
            'first': station.id,
            'last': station.id,
            'stations': [station.id]
        }
        station_to_route[station.id] = route_id
        route_id += 1

    # Fusionner routes par ordre de savings décroissants
    for _, i, j in savings:
        if i not in station_to_route or j not in station_to_route:
            continue

        ri_id = station_to_route[i]
        rj_id = station_to_route[j]

        if ri_id == rj_id:
            continue

        ri = routes[ri_id]
        rj = routes[rj_id]

        # Vérifier que i et j sont aux extrémités
        i_first = (ri['first'] == i)
        i_last = (ri['last'] == i)
        j_first = (rj['first'] == j)
        j_last = (rj['last'] == j)

        if not ((i_first or i_last) and (j_first or j_last)):
            continue

        # Déterminer ordre de fusion
        if i_last and j_first:
            new_stations = ri['stations'] + rj['stations']
        elif i_first and j_last:
            new_stations = rj['stations'] + ri['stations']
        elif i_last and j_last:
            new_stations = ri['stations'] + rj['stations'][::-1]
        elif i_first and j_first:
            new_stations = ri['stations'][::-1] + rj['stations']
        else:
            continue

        # Vérifier faisabilité
        if not is_feasible(graph, new_stations, vehicle_capacity):
            continue

        # Fusionner
        new_route_id = route_id
        route_id += 1

        routes[new_route_id] = {
            'first': new_stations[0],
            'last': new_stations[-1],
            'stations': new_stations
        }

        for sid in new_stations:
            station_to_route[sid] = new_route_id

        del routes[ri_id]
        del routes[rj_id]

    # Construire tour final (prendre la plus longue route)
    final_route = max(routes.values(), key=lambda r: len(r['stations']))
    tour = [0] + final_route['stations'] + [0]

    for i in range(len(tour) - 1):
        graph.add_edge(tour[i], tour[i + 1])

    return []


def is_feasible(graph: SolvingStationGraph, stations: list[int], capacity: int) -> bool:
    """Vérifie que 0 ≤ charge ≤ capacité tout au long du parcours"""
    load = 0
    for sid in stations:
        load += graph.get_station(sid).bike_gap()
        if load < 0 or load > capacity:
            return False
    return True
