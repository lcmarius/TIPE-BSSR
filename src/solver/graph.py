from typing import Dict, List, Tuple, Optional
from src.objects.station import TargetedStation, Station
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx
import copy


class GraphSnapshot:
    """Snapshot of a graph state for animation"""
    def __init__(self, stations: Dict[int, int|None], station_map: Dict[int, TargetedStation],
                 description: str = "", highlighted_stations: List[int] = None,
                 highlighted_edge: Tuple[int, int] = None):
        self.stations = copy.deepcopy(stations)
        self.station_map = copy.deepcopy(station_map)
        self.description = description
        self.highlighted_stations = highlighted_stations or []
        self.highlighted_edge = highlighted_edge


class SolvingStationGraph:
    """Directed unweighted graph for Station solving"""

    def __init__(self, depot_station: Station):
        self.stations: Dict[int, int|None] = {}  # station_id -> [neighbor_ids]
        self.station_map: Dict[int, TargetedStation] = {}  # station_id -> Station object
        self.snapshots: List[GraphSnapshot] = []  # For animation

        assert depot_station.id == 0, "Depot must have id 0"
        self.add_station(TargetedStation.from_station(depot_station, 0, 0))

    def has_station(self, station_id: int) -> bool:
        return station_id in self.stations

    def add_station(self, station: TargetedStation) -> None:
        self.stations[station.id] = None
        self.station_map[station.id] = station

    def get_station(self, station_id: int) -> TargetedStation:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")
        return self.station_map[station_id]

    def list_stations(self) -> List[TargetedStation]:
        return list(self.station_map.values())

    def list_edges(self) -> List[Tuple[int, int]]:
        edges = []
        for station_id in self.stations:
            neighbor = self.stations[station_id]
            if neighbor is not None:
                edges.append((station_id, neighbor))
        return edges

    def remove_station(self, station_id: int) -> None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")

        for sid in self.stations:
            if station_id == self.stations[sid]:
                self.stations[sid] = None
        del self.stations[station_id]
        del self.station_map[station_id]

    def size(self) -> int:
        return len(self.stations)

    def has_edge(self, station_id1: int, station_id2: int) -> bool:
        return self.has_station(station_id1) and station_id2 == self.stations[station_id1]

    def add_edge(self, station_id1: int, station_id2: int) -> None:
        if not self.has_station(station_id1):
            raise Exception(f"Station {station_id1} does not exist")

        if not self.has_station(station_id2):
            raise Exception(f"Station {station_id2} does not exist")

        if self.has_edge(station_id1, station_id2):
            raise Exception(f"Edge {station_id1} -> {station_id2} already exists")

        self.stations[station_id1] = station_id2

    def remove_edge(self, station_id1: int, station_id2: int) -> None:
        if not self.has_edge(station_id1, station_id2):
            raise Exception(f"Edge {station_id1} -> {station_id2} does not exist")

        self.stations[station_id1] = None

    def is_connex(self):
        return len(self.list_edges()) == self.size() - 1

    def get_successor(self, station_id: int) -> int | None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")
        return self.stations[station_id]

    def get_predecessor(self, station_id: int) -> int | None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")

        for sid in self.stations:
            if self.stations[sid] == station_id:
                return sid

        return None

    def get_nearest_neighbor(self, station_id: int, condition) -> TargetedStation | None:
        """
        Trouve la station la plus proche d'une station de référence qui satisfait une condition donnée.
        :param station_id: L'ID de la station de référence.
        :param condition: Une fonction prenant une station en entrée et retournant un booléen.
        :return: La station la plus proche qui satisfait la condition, ou None si aucune ne la satisfait.
        """
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")

        reference_station = self.get_station(station_id)
        nearest_station = None
        min_distance = float('inf')

        for candidate in self.list_stations():
            if candidate.id != station_id and condition(candidate):
                distance = reference_station.distance_to(candidate)
                if distance < min_distance:
                    min_distance = distance
                    nearest_station = candidate

        return nearest_station

    def take_snapshot(self, description: str = "", highlighted_stations: List[int] = None,
                     highlighted_edge: Tuple[int, int] = None):
        """
        Capture l'état actuel du graphe pour l'animation
        :param description: Information textuelle sur l'état actuel
        :param highlighted_stations: Liste des stations à mettre en évidence
        :param highlighted_edge: Arête à mettre en évidence (station_id1, station_id2)
        :return:
        """
        snapshot = GraphSnapshot(self.stations, self.station_map, description,
                                highlighted_stations, highlighted_edge)
        self.snapshots.append(snapshot)

    def clear_snapshots(self) -> None:
        """Efface toutes les captures"""
        self.snapshots = []


def animate_graph(graph: SolvingStationGraph, output_file: str = "algorithm_animation", interval: int = 1000, save_gif: bool = True):
    """
    Créer une animation du graphe
    :param graph: Le graphe à animer
    :param output_file: Nom du fichier de sortie (sans extension)
    :param interval: Intervalle entre les frames en ms
    :param save_gif: Si True, sauvegarde l'animation en GIF, sinon l'affiche
    :return:
    """

    if not graph.snapshots:
        raise Exception("No snapshots recorded. Use take_snapshot() during your algorithm.")

    fig, ax = plt.subplots(figsize=(12, 8))

    pos = {}
    for station in graph.list_stations():
        pos[station.id] = (station.long, station.lat)

    def draw_frame(frame_num):
        ax.clear()
        snapshot = graph.snapshots[frame_num]

        G = nx.DiGraph()
        for sid in snapshot.station_map:
            G.add_node(sid)
        for sid, neighbor in snapshot.stations.items():
            if neighbor is not None:
                G.add_edge(sid, neighbor)

        node_colors = []
        for node in G.nodes():
            if node in snapshot.highlighted_stations:
                node_colors.append('orange')
            elif node == 0:
                node_colors.append('lightblue')
            else:
                node_colors.append('lightgreen')

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700,
                              ax=ax, node_shape='s')

        edge_colors = []
        for edge in G.edges():
            if snapshot.highlighted_edge == edge:
                edge_colors.append('red')
            else:
                edge_colors.append('black')

        nx.draw_networkx_edges(G, pos, edge_color=edge_colors, arrows=True,
                              arrowsize=20, width=2, ax=ax)

        labels = {}
        for sid, st in snapshot.station_map.items():
            labels[sid] = f"{sid}\n{st.bike_count}/{st.bike_target}"
        nx.draw_networkx_labels(G, pos, labels, font_size=8, ax=ax)

        ax.set_title(f"Step {frame_num + 1}/{len(graph.snapshots)}: {snapshot.description}",
                    fontsize=14, fontweight='bold')
        ax.axis('off')

    anim = animation.FuncAnimation(fig, draw_frame, frames=len(graph.snapshots),
                                  interval=interval, repeat=True)

    if save_gif:
        anim.save(output_file + ".gif", writer='pillow', fps=1000//interval)
        print(f"Animation saved to {output_file}.gif")
    else:
        plt.show()

    plt.close()


def test():
    s0 = Station(0, "Station init", 1, "Addr 1", -1.5, 47.2)
    g = SolvingStationGraph(s0)

    s1 = TargetedStation(1, "Station 1", 10, "Addr 1", -1.5, 47.2, 5, 8)
    s2 = TargetedStation(2, "Station 2", 10, "Addr 2", -1.6, 47.3, 7, 4)
    s3 = TargetedStation(3, "Station 3", 10, "Addr 3", -1.7, 47.4, 2, 6)

    g.add_station(s1)
    g.add_station(s2)
    g.add_station(s3)
    assert g.size() == 4
    assert g.has_station(1)
    assert g.get_station(1) == s1

    g.add_edge(1, 2)
    g.add_edge(2, 3)
    assert len(g.list_edges()) == 2
    assert g.get_successor(1) == 2
    assert g.has_edge(1, 2)
    assert g.has_edge(2, 3)
    assert not g.has_edge(1, 3)

    g.remove_edge(1, 2)
    assert len(g.list_edges()) == 1

    g.remove_station(3)
    assert g.size() == 3
    assert len(g.list_edges()) == 0

    print("All tests passed!")

if __name__ == "__main__":
    test()