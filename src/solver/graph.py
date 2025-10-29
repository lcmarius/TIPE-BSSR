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

        # Remove edges where this station is the successor
        for snumber in self.successors:
            if station_number == self.successors[snumber]:
                self.successors[snumber] = None

        # Remove edges where this station is the predecessor
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
        return len(self.list_edges()) == self.size() - 1

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

    def get_turn(self) -> list[int]:
        """
        Récupère le tour actuel du graphe sous forme de liste de numéros de stations.
        :return: Liste des numéros de station dans l'ordre du tour
        """
        turn = []
        current_number = 0
        visited = set()

        while current_number is not None and current_number not in visited:
            turn.append(current_number)
            visited.add(current_number)
            current_number = self.get_successor(current_number)

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