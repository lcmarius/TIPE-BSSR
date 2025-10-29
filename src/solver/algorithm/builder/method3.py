"""
Méthode 3 : Algorithme d'Économies (Clarke-Wright, 1964)

PRINCIPE SIMPLE :
Au lieu de faire un aller-retour au dépôt pour chaque station (0->i->0, 0->j->0),
on cherche à relier deux stations dans le même trajet (0->i->j->0).
L'économie de distance réalisée est : distance(0,i) + distance(0,j) - distance(i,j)

ALGORITHME :
1. Calculer toutes les économies possibles entre paires de stations
2. Trier les économies par ordre décroissant
3. Fusionner les routes en respectant :
   - Les stations doivent être aux extrémités des routes
   - La capacité du camion ne doit pas être dépassée
"""

from src.solver.graph import SolvingStationGraph


def method3(graph: SolvingStationGraph, vehicle_capacity: int):
    """
    Algorithme de Clarke-Wright adapté au BSSRP

    Construit une tournée en fusionnant progressivement des routes selon leur économie
    """
    # Récupérer toutes les stations (sauf le dépôt)
    stations = [s for s in graph.list_stations() if s.number != 0]
    if len(stations) == 0:
        return []

    depot = graph.get_station(0)

    # ÉTAPE 1 : Calculer les économies pour toutes les paires de stations
    savings_list = []
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            """
            Calcul de l'économie réalisée entre le chemin (1) et le chemin (2): (1) - (2): 
            (1): depot -> station_i -> dépot -> station_j -> dépot  
            (2): dépot -> station_i -> station_j -> dépot
            """
            economy = (
                + stations[i].distance_to(depot)
                + depot.distance_to(stations[j])
                - stations[i].distance_to(stations[j])
           )

            savings_list.append((economy, stations[i].number, stations[j].number))

    # ÉTAPE 2 : Initialiser chaque station comme une route individuelle
    routes = {}
    route_id_from_station_number = {}
    next_route_id = 0
    for i in range(len(stations)):
        routes[next_route_id] = [stations[i].number]
        route_id_from_station_number[stations[i].number] = next_route_id
        next_route_id += 1

    # ÉTAPE 3 : On trie les économies des plus grandes aux plus petites pour traiter en priorité les plus intéressantes
    savings_list.sort(reverse=True, key=lambda x: x[0])

    # ÉTAPE 4 : Fusionner les routes selon les économies
    for economy, station_i_id, station_j_id in savings_list:
        # On ignore les stations déjà fusionnées
        if station_i_id not in route_id_from_station_number or station_j_id not in route_id_from_station_number:
            continue

        route_i_id = route_id_from_station_number[station_i_id]
        route_j_id = route_id_from_station_number[station_j_id]

        # On ignore si les deux stations sont déjà dans la même route (évite les cycles)
        if route_i_id == route_j_id:
            continue

        route_i = routes[route_i_id]
        route_j = routes[route_j_id]

        # Déterminer la position des stations dans leurs routes respectives
        i_position = 'start' if route_i[0] == station_i_id else ('end' if route_i[-1] == station_i_id else 'middle')
        j_position = 'start' if route_j[0] == station_j_id else ('end' if route_j[-1] == station_j_id else 'middle')

        # Impossible de fusionner si une station est au milieu de sa route
        if i_position == 'middle' or j_position == 'middle':
            continue

        # Construire la route fusionnée dans le bon ordre
        oriented_route_i = route_i if i_position == 'end' else route_i[::-1]
        oriented_route_j = route_j if j_position == 'start' else route_j[::-1]
        merged_route = oriented_route_i + oriented_route_j

        # Vérifier la faisabilité de la nouvelle route
        if not is_route_faisable(graph, vehicle_capacity, merged_route):
            continue

        # On enregistre la nouvelle route fusionnée
        routes[next_route_id] = merged_route
        for station_number in merged_route:
            route_id_from_station_number[station_number] = next_route_id
        next_route_id += 1

        # On supprime les anciennes routes
        del routes[route_i_id]
        del routes[route_j_id]

    # ÉTAPE 5 : Construire la tournée finale
    final_route = max(routes.values(), key=lambda r: len(r))

    graph.add_edge(0, final_route[0])
    for i in range(len(final_route)-1):
        graph.add_edge(final_route[i], final_route[i + 1])
    graph.add_edge(final_route[-1], 0)

    return None


def is_route_faisable(graph: SolvingStationGraph, capacity: int, stations: list[int]) -> bool:
    """
    Vérifie que la route respecte les contraintes de capacité du camion

    La charge du camion doit rester dans l'intervalle [0, capacity] à chaque étape
    """
    load = 0
    for station_number in stations:
        load += graph.get_station(station_number).bike_gap()
        if load < 0 or load > capacity:
            return False

    return True
