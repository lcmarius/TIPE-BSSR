# =============================================================================
# Modélisation du réseau routier pour le calcul de distances et temps de trajet
# =============================================================================
#
# Hypothèses de modélisation :
#
#   H1 – Graphe routier statique
#       Le réseau routier est extrait d'OpenStreetMap via OSMnx et considéré
#       comme fixe dans le temps. On ne modélise pas les variations dynamiques
#       (travaux, routes fermées, embouteillages en temps réel).
#
#   H2 – Pas de variabilité temporelle du trafic
#       Les temps de parcours sont identiques quelle que soit l'heure de la
#       journée (pas de distinction heure de pointe / heures creuses).
#       Justification : le rééquilibrage s'effectue typiquement tôt le matin
#       ou en journée creuse, quand le trafic est relativement stable.
#
#   H3 – Facteurs de réduction de vitesse par type de voie
#       Les vitesses maximales autorisées (fournies par OSM) sont réduites par
#       un coefficient dépendant du type de route pour refléter les conditions
#       réelles de circulation d'un camion utilitaire en milieu urbain :
#           - motorway  : ×0.90  (flux fluide, peu d'arrêts)
#           - trunk     : ×0.85
#           - primary   : ×0.75  (feux, intersections fréquentes)
#           - secondary : ×0.70
#           - tertiary  : ×0.65
#           - residential : ×0.60 (stops, stationnement, manœuvres)
#           - autres    : ×0.70  (valeur prudente par défaut)
#       Justification : ces ordres de grandeur sont cohérents avec les études
#       de vitesse moyenne en milieu urbain (rapport CEREMA 2018, données TomTom
#       Traffic Index) qui montrent qu'en ville la vitesse effective représente
#       60-80 % de la vitesse autorisée selon le type de voie.
#
#   H4 – Pénalité fixe aux feux tricolores (+15 s)
#       Chaque passage par un nœud identifié comme feu de signalisation dans
#       OSM ajoute 15 secondes au temps de parcours.
#       Justification : le temps d'attente moyen à un feu urbain est estimé
#       entre 15 et 30 secondes (Webster, 1958 ; données empiriques CERTU).
#       On retient la borne basse car le camion ne s'arrête pas à chaque feu.
#
#   H5 – Plus court chemin (Dijkstra)
#       Le trajet entre deux stations est calculé comme le plus court chemin
#       sur le graphe routier pondéré. On suppose que le conducteur suit
#       toujours l'itinéraire optimal, sans détours ni erreurs de navigation.
#
# =============================================================================

import os

import networkx as nx
import osmnx as ox
from datetime import datetime

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
            print("Resource loading...")
            self.graph = load_sources(sources_file)
            print("Resource loaded from file:", sources_file)
        else:
            print("Resource not found, generating new graph map...")
            self.graph = generate_sources(sources_file, city)
            print("Resource generated and saved to file:", sources_file)
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


