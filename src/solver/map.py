import os

import networkx as nx
import osmnx as ox
from datetime import datetime
from networkx.classes import Graph

from src.solver.algorithm.opt import get_distance


def locate_sources(sources_files):
    return os.path.exists(sources_files)

def generate_sources(sources_files, city="Nantes Métropole, France") -> nx.MultiDiGraph:
    g = ox.graph_from_place(city, network_type="drive")
    g = ox.add_edge_speeds(g)
    g = ox.add_edge_travel_times(g)

    g.graph['city'] = city
    g.graph['creation_date'] = datetime.now().isoformat()

    speed_factors = {
        'motorway': 0.90,      # Autoroutes légèrement ralenties
        'trunk': 0.85,
        'primary': 0.75,       # Routes principales urbaines
        'secondary': 0.70,
        'tertiary': 0.65,
        'residential': 0.60,   # Zones résidentielles avec stops fréquents
        'unclassified': 0.65
    }

    nodes_data = g.nodes(data=True)
    for u, v, k, route in g.edges(keys=True, data=True):
        if 'travel_time' in route:
            highway_type = route.get('highway')
            if isinstance(highway_type, list):
                highway_type = highway_type[0]

            factor = speed_factors.get(highway_type, 0.70)  # Par défaut 70%
            route['travel_time'] = route['travel_time'] / factor

            node_tags = nodes_data[v]
            is_traffic_signal = False
            if 'highway' in node_tags:
                val = node_tags['highway']
                if isinstance(val, list):
                    if 'traffic_signals' in val: is_traffic_signal = True
                elif val == 'traffic_signals':
                    is_traffic_signal = True
            if is_traffic_signal:
                route['travel_time'] += 15

    ox.save_graphml(g, sources_files)
    return g

def load_sources(sources_file, city="Nantes Métropole, France") -> nx.MultiDiGraph:
    g = ox.load_graphml(sources_file)

    if g.graph.get('city') != city:
        raise ValueError(f"Graph file city '{g.graph.get('city')}' does not match expected city '{city}'.")

    if g.graph.get('creation_date') is None:
        raise ValueError("Graph file is missing 'creation_date' metadata.")

    return g

class GeoPoint:
    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude


class Map:

    def __init__(self, sources_file, city="Nantes Métropole, France"):
        """
        Initialise la carte en chargeant ou créant le graphe routier pour la ville donnée
        :param sources_file: Chemin vers le fichier de graphe (GraphML)
        :param city: Nom de la ville reconnu par OSMnx
        """
        self.city = city

        if locate_sources(sources_file):
            self.graph = load_sources(sources_file)
        else:
            self.graph = generate_sources(sources_file, city)
        self.created_at = self.graph.graph.get('creation_date', 'unknown')

    def get_time(self, fr: GeoPoint, to: GeoPoint) -> float:
        origine_node = ox.nearest_nodes(self.graph, X=fr.longitude, Y=fr.latitude)
        destination_node = ox.nearest_nodes(self.graph, X=to.longitude, Y=to.latitude)

        return nx.shortest_path_length(
            self.graph,
            source=origine_node,
            target=destination_node,
            weight='travel_time'
        )

    def get_distance(self, fr: GeoPoint, to: GeoPoint) -> float:
        origine_node = ox.nearest_nodes(self.graph, X=fr.longitude, Y=fr.latitude)
        destination_node = ox.nearest_nodes(self.graph, X=to.longitude, Y=to.latitude)

        return nx.shortest_path_length(
            self.graph,
            source=origine_node,
            target=destination_node,
            weight='length'
        )


def test():
    map = Map("nantes_graph.graphml", city="Nantes Métropole, France")

    time_to_calculate = datetime.now()
    d = None
    t = None
    for _ in range(100):
        geo_a = GeoPoint(47.219717, -1.567036)
        geo_b = GeoPoint(47.228951, -1.556430)
        d = map.get_distance(geo_a, geo_b)
        t = map.get_time(geo_a, geo_b)

    print("Time from A to B:", t, "seconds", "(approx", t/60, "minutes)")
    print("Distance from A to B:", d, "meters")
    print("Calculations done in:", ((datetime.now() - time_to_calculate).total_seconds()/100/2, "seconds"))

    print("Map initialized for city:", len(map.graph.nodes), "nodes,", len(map.graph.edges), "edges", "created at", map.created_at)

test()


