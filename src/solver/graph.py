from typing import Dict, List, Tuple, Optional
from src.objects.station import TargetedStation, Station


class SolvingStationGraph:
    """Directed unweighted graph for Station solving"""

    def __init__(self, depot_station: Station):
        self.successors: Dict[int, int | None] = {}  # station_id -> [successor_station_id | None]
        self.predecessors: Dict[int, int | None] = {}  # station_id -> [predecessor_station_id | None]
        self.station_map: Dict[int, TargetedStation] = {}  # station_id -> Station object

        assert depot_station.id == 0, "Depot must have id 0"
        self.add_station(TargetedStation.from_station(depot_station, 0, 0))

    def has_station(self, station_id: int) -> bool:
        return station_id in self.successors

    def add_station(self, station: TargetedStation) -> None:
        self.successors[station.id] = None
        self.predecessors[station.id] = None
        self.station_map[station.id] = station

    def get_station(self, station_id: int) -> TargetedStation:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")
        return self.station_map[station_id]

    def list_stations(self) -> List[TargetedStation]:
        return list(self.station_map.values())

    def list_edges(self) -> List[Tuple[int, int]]:
        edges = []
        for station_id in self.successors:
            neighbor = self.successors[station_id]
            if neighbor is not None:
                edges.append((station_id, neighbor))
        return edges

    def remove_station(self, station_id: int) -> None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")

        # Remove edges where this station is the successor
        for sid in self.successors:
            if station_id == self.successors[sid]:
                self.successors[sid] = None

        # Remove edges where this station is the predecessor
        for sid in self.predecessors:
            if station_id == self.predecessors[sid]:
                self.predecessors[sid] = None

        del self.successors[station_id]
        del self.predecessors[station_id]
        del self.station_map[station_id]

    def size(self) -> int:
        return len(self.successors)

    def has_edge(self, station_id1: int, station_id2: int) -> bool:
        return self.has_station(station_id1) and station_id2 == self.successors[station_id1]

    def add_edge(self, station_id1: int, station_id2: int) -> None:
        if not self.has_station(station_id1):
            raise Exception(f"Station {station_id1} does not exist")

        if not self.has_station(station_id2):
            raise Exception(f"Station {station_id2} does not exist")

        if self.has_edge(station_id1, station_id2):
            raise Exception(f"Edge {station_id1} -> {station_id2} already exists")

        self.successors[station_id1] = station_id2
        self.predecessors[station_id2] = station_id1

    def remove_edge(self, station_id1: int, station_id2: int) -> None:
        if not self.has_edge(station_id1, station_id2):
            raise Exception(f"Edge {station_id1} -> {station_id2} does not exist")

        self.successors[station_id1] = None
        self.predecessors[station_id2] = None

    def is_connex(self):
        return len(self.list_edges()) == self.size() - 1

    def get_successor(self, station_id: int) -> int | None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")
        return self.successors[station_id]

    def get_predecessor(self, station_id: int) -> int | None:
        if not self.has_station(station_id):
            raise Exception(f"Station {station_id} does not exist")

        return self.predecessors[station_id]

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

    def get_turn(self) -> list[int]:
        """
        Récupère le tour actuel du graphe sous forme de liste d'IDs
        :return: Liste des IDs dans l'ordre du tour
        """
        turn = []
        current_id = 0
        visited = set()

        while current_id is not None and current_id not in visited:
            turn.append(current_id)
            visited.add(current_id)
            current_id = self.get_successor(current_id)

        return turn

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