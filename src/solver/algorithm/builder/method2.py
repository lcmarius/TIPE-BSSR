import sys
import os

# Ajoute le dossier racine du projet au PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../')))


from typing import List
from src.objects.station import TargetedStation, Station
from src.solver.graph import SolvingStationGraph
from src.solver.graph_viewer import GraphSnapshot


def construire_chemin_surplus_graph(graph: SolvingStationGraph):
    """
    Construit un chemin en parcourant uniquement les stations en surplus,
    à partir du dépôt (0).
    """
    start = graph.get_station(0)
    chemin = [start]

    # Liste des stations en surplus (écart positif)
    surplus = [s for s in graph.list_stations() if s.number != 0 and s.bike_gap() > 0] #ceration d'une liste par compréhension avec toutes les stations qui ont un surplus

    if not surplus:
        return chemin

    current_station = start

    # Boucle gloutonne : on ajoute le plus proche voisin en surplus à chaque étape
    while surplus:
        nearest = graph.get_nearest_neighbor(current_station.number,lambda s: s in surplus)

        if nearest is None:
            break  # On a pas trouvé de station valide

        chemin.append(nearest)
        surplus.remove(nearest)
        current_station = nearest

    return chemin


def method2(graph: SolvingStationGraph, capacite: int):
    snapshots = [GraphSnapshot(graph, "État initial", [], None)]

    chemin = construire_chemin_surplus_graph(graph)
    #start = graph.get_station(0)

    if len(chemin) == 1:
        snapshots.append(GraphSnapshot(graph, "Aucune station à visiter", [0], None))
        return snapshots

    deficits = [s for s in graph.list_stations() if s.number != 0 and s.bike_gap() < 0]
    remaining_gap = {s.number: s.bike_gap() for s in graph.list_stations()}

    # On commence par la première station en surplus après le dépôt
    current_station = chemin[1]
    graph.add_edge(0, current_station.number)
    snapshots.append(GraphSnapshot(
        graph,
        f"Première station en surplus : {current_station.name}",
        [current_station.number],
        (0, current_station.number)
    ))

    camion = remaining_gap[current_station.number]
    remaining_gap[current_station.number] = 0

    # Parcours des stations en surplus
    for next_station in chemin[2:]:
        # Insérer des déficits possibles entre current_station et next_station
        while deficits:
            possibles = [d for d in deficits if -remaining_gap[d.number] <= camion]
            if not possibles:
                break

            nearest_deficit = graph.get_nearest_neighbor(current_station.number,lambda s: s in possibles)

            if nearest_deficit is None:
                break

            if current_station.distance_to(nearest_deficit) < current_station.distance_to(next_station):
                besoin = -remaining_gap[nearest_deficit.number]
                camion -= besoin
                remaining_gap[nearest_deficit.number] = 0
                graph.add_edge(current_station.number, nearest_deficit.number)
                snapshots.append(GraphSnapshot(
                    graph,
                    f"Insertion déficit : {nearest_deficit.name} (camion = {camion})",
                    [nearest_deficit.number],
                    (current_station.number, nearest_deficit.number)
                ))
                current_station = nearest_deficit
                deficits.remove(nearest_deficit)
            else:
                break

        # Passage à la prochaine station en surplus
        graph.add_edge(current_station.number, next_station.number)
        snapshots.append(GraphSnapshot(
            graph,
            f"Station suivante en surplus : {next_station.name}",
            [next_station.number],
            (current_station.number, next_station.number)
        ))
        current_station = next_station

        diff = remaining_gap[next_station.number]
        if diff > 0:
            prise = min(diff, capacite - camion)
            camion += prise
            remaining_gap[next_station.number] -= prise
        elif diff < 0:
            depot = min(-diff, camion)
            camion -= depot
            remaining_gap[next_station.number] += depot

    # Ajouter les déficits restants à la fin du parcours
    for d in deficits[:]:
        if remaining_gap[d.number] < 0:
            besoin = -remaining_gap[d.number]
            camion -= besoin
            remaining_gap[d.number] = 0
            graph.add_edge(current_station.number, d.number)
            snapshots.append(GraphSnapshot(
                graph,
                f"Ajout déficit final : {d.name} (camion = {camion})",
                [d.number],
                (current_station.number, d.number)
            ))
            current_station = d

    # Retour au dépôt
    graph.add_edge(current_station.number, 0)
    snapshots.append(GraphSnapshot(
        graph,
        f"Retour au dépôt (charge finale : {camion})",
        [0],
        (current_station.number, 0)
    ))
    return snapshots
