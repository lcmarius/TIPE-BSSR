from typing import Dict, List, Tuple, Optional


from src.objects.station import TargetedStation, Station



class SolvingStationGraph:
    """Directed unweighted graph for Station solving"""

    def __init__(self, depot_station: Station):
        self.successors: Dict[int, int | None] = {}  # station_number -> [successor_station_number | None]
        self.predecessors: Dict[int, int | None] = {}  # station_number -> [predecessor_station_number | None]
        self.station_map: Dict[int, TargetedStation] = {}  # station_number -> Station object

        assert depot_station.number == 0, "Depot must have number 0"
        self.add_station(TargetedStation.from_station(depot_station, 0, 0))

    def has_station(self, station_number: int) -> bool:
        return station_number in self.successors

    def add_station(self, station: TargetedStation) -> None:
        self.successors[station.number] = None
        self.predecessors[station.number] = None
        self.station_map[station.number] = station

    def get_station(self, station_number: int) -> TargetedStation:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")
        return self.station_map[station_number]

    def list_stations(self) -> List[TargetedStation]:
        return list(self.station_map.values())

    def list_edges(self) -> List[Tuple[int, int]]:
        edges = []
        for station_number in self.successors:
            neighbor = self.successors[station_number]
            if neighbor is not None:
                edges.append((station_number, neighbor))
        return edges

    def remove_station(self, station_number: int) -> None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")

        for snumber in self.successors:
            if station_number == self.successors[snumber]:
                self.successors[snumber] = None

        for snumber in self.predecessors:
            if station_number == self.predecessors[snumber]:
                self.predecessors[snumber] = None

        del self.successors[station_number]
        del self.predecessors[station_number]
        del self.station_map[station_number]

    def size(self) -> int:
        return len(self.successors)

    def has_edge(self, station_number1: int, station_number2: int) -> bool:
        return self.has_station(station_number1) and station_number2 == self.successors[station_number1]

    def add_edge(self, station_number1: int, station_number2: int) -> None:
        if not self.has_station(station_number1):
            raise Exception(f"Station {station_number1} does not exist")

        if not self.has_station(station_number2):
            raise Exception(f"Station {station_number2} does not exist")

        if self.has_edge(station_number1, station_number2):
            raise Exception(f"Edge {station_number1} -> {station_number2} already exists")

        self.successors[station_number1] = station_number2
        self.predecessors[station_number2] = station_number1

    def remove_edge(self, station_number1: int, station_number2: int) -> None:
        if not self.has_edge(station_number1, station_number2):
            raise Exception(f"Edge {station_number1} -> {station_number2} does not exist")

        self.successors[station_number1] = None
        self.predecessors[station_number2] = None

    def is_connex(self):
        return len(self.list_edges()) == self.size()

    def get_successor(self, station_number: int) -> int | None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")
        return self.successors[station_number]

    def get_predecessor(self, station_number: int) -> int | None:
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")

        return self.predecessors[station_number]

    def get_nearest_neighbor(self, station_number: int, condition) -> TargetedStation | None:
        """
        Trouve la station la plus proche d'une station de référence qui satisfait une condition donnée.
        :param station_number: Le numéro de la station de référence.
        :param condition: Une fonction prenant une station en entrée et retournant un booléen.
        :return: La station la plus proche qui satisfait la condition, ou None si aucune ne la satisfait.
        """
        if not self.has_station(station_number):
            raise Exception(f"Station {station_number} does not exist")

        reference_station = self.get_station(station_number)

        candidates = [
            (reference_station.distance_to(s), s)
            for s in self.list_stations()
            if s.number != station_number and condition(s)
        ]

        return min(candidates, key=lambda x: x[0])[1] if candidates else None

    def render(self, output_file: str = "graph.png", title: str = "Graphe title"):
        """
        Affiche et sauvegarde l'état actuel du graphe en PNG
        :param output_file: Nom du fichier de sortie
        :param title: Titre de l'image
        """
        import matplotlib.pyplot as plt
        import networkx as nx

        fig, ax = plt.subplots(figsize=(12, 8), dpi=150)

        pos = {}
        for station in self.list_stations():
            pos[station.number] = (station.long, station.lat)

        all_x = [p[0] for p in pos.values()]
        all_y = [p[1] for p in pos.values()]
        margin = 0.02
        x_margin = (max(all_x) - min(all_x)) * margin
        y_margin = (max(all_y) - min(all_y)) * margin
        xlim = (min(all_x) - x_margin, max(all_x) + x_margin)
        ylim = (min(all_y) - y_margin, max(all_y) + y_margin)

        G = nx.DiGraph()
        for sid in self.station_map:
            G.add_node(sid)
        for sid, neighbor in self.successors.items():
            if neighbor is not None:
                G.add_edge(sid, neighbor)

        node_colors = []
        for node in G.nodes():
            gap = self.station_map[node].bike_gap()
            if gap > 0:
                node_colors.append('lightgreen')  # Excès de vélos
            elif gap < 0:
                node_colors.append('lightcoral')  # Déficit de vélos
            else:
                node_colors.append('lightblue')  # Équilibré

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700,
                               ax=ax, node_shape='s')

        nx.draw_networkx_edges(G, pos, edge_color='black', arrows=True,
                               arrowsize=20, width=2, ax=ax)

        labels = {}
        for sid, st in self.station_map.items():
            labels[sid] = f"{sid}\n{st.bike_gap()}"
        nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold', ax=ax)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.axis('off')

        plt.savefig(output_file, dpi=150, bbox_inches='tight')
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