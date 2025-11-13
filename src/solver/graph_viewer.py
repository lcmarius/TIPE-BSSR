import copy
from typing import Dict, Tuple, List
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx
import copy

from src.solver.graph import SolvingStationGraph

class GraphSnapshot:
    """Snapshot of a graph state for animation"""
    def __init__(self, graph: SolvingStationGraph,
                 description: str = "", highlighted_stations: List[int] = None,
                 highlighted_edge: Tuple[int, int] = None):
        self.stations = copy.deepcopy(graph.successors)
        self.station_map = copy.deepcopy(graph.station_map)
        self.description = description
        self.highlighted_stations = highlighted_stations or []
        self.highlighted_edge = highlighted_edge

def animate_graph(snapshots: List[GraphSnapshot], output_file: str = "algorithm_animation", interval: int = 1000, save_gif: bool = True, max_snapshots: int = None):
    """
    Créer une animation du graphe
    :param graph: Le graphe à animer
    :param output_file: Nom du fichier de sortie (sans extension)
    :param interval: Intervalle entre les frames en ms
    :param save_gif: Si True, sauvegarde l'animation en GIF, sinon l'affiche
    :param max_snapshots: Si spécifié, ne garde que max_snapshots frames (échantillonnage)
    :return:
    """

    # Échantillonnage des snapshots si trop nombreux
    if max_snapshots and len(snapshots) > max_snapshots:
        last=snapshots[-1]
        step = len(snapshots) // max_snapshots
        snapshots = [snapshots[i] for i in range(0, len(snapshots), step)]
        snapshots.append(last)

    fig, ax = plt.subplots(figsize=(12, 8), dpi=80)  # DPI réduit pour fichier plus léger

    pos = {}
    for station in list(snapshots[0].station_map.values()):
        pos[station.number] = (station.long, station.lat)

    # Calculer les limites des axes une seule fois pour éviter le redimensionnement
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    margin = 0.02  # Marge de 2% autour des stations
    x_margin = (max(all_x) - min(all_x)) * margin
    y_margin = (max(all_y) - min(all_y)) * margin
    xlim = (min(all_x) - x_margin, max(all_x) + x_margin)
    ylim = (min(all_y) - y_margin, max(all_y) + y_margin)

    def draw_frame(frame_num):
        ax.clear()
        snapshot = snapshots[frame_num]

        G = nx.DiGraph()
        for sid in snapshot.station_map:
            G.add_node(sid)
        for sid, neighbor in snapshot.stations.items():
            if neighbor is not None:
                G.add_edge(sid, neighbor)

        node_colors = []
        edge_colors_nodes = []
        linewidths = []

        for node in G.nodes():
            # Couleur de fond selon le gap
            gap = snapshot.station_map[node].bike_gap()
            if gap > 0:
                node_colors.append('lightgreen')  # Excès de vélos
            elif gap < 0:
                node_colors.append('lightcoral')  # Déficit de vélos
            else:
                node_colors.append('lightblue')  # Équilibré

            if node in snapshot.highlighted_stations:
                edge_colors_nodes.append('red')
                linewidths.append(2)
            else:
                edge_colors_nodes.append('none')
                linewidths.append(0)

        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700,
                              ax=ax, node_shape='s', edgecolors=edge_colors_nodes,
                              linewidths=linewidths)

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
            labels[sid] = f"{sid}\n{st.bike_gap()}"
        nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold', ax=ax)

        # Si deux stations sont highlightées, dessiner une flèche de permutation entre elles
        if len(snapshot.highlighted_stations) == 2:
            station1_id = snapshot.highlighted_stations[0]
            station2_id = snapshot.highlighted_stations[1]

            pos1 = pos[station1_id]
            pos2 = pos[station2_id]

            # Dessiner une flèche bidirectionnelle en pointillés pour montrer la permutation
            ax.annotate('', xy=pos2, xytext=pos1,
                       arrowprops=dict(arrowstyle='<->', color='orange', lw=3,
                                     linestyle='--', alpha=0.7))

            mid_x = (pos1[0] + pos2[0]) / 2
            mid_y = (pos1[1] + pos2[1]) / 2
            ax.text(mid_x, mid_y, '<>', fontsize=12, fontweight='bold',
                   color='orange', ha='center', va='center',
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='orange', lw=2))

        ax.set_title(f"Step {frame_num + 1}/{len(snapshots)}: {snapshot.description}",
                    fontsize=14, fontweight='bold')

        # Fixer les limites des axes pour éviter que les nœuds bougent
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        ax.axis('off')

    anim = animation.FuncAnimation(fig, draw_frame, frames=len(snapshots),
                                  interval=interval, repeat=True)

    if save_gif:
        # Utiliser un writer optimisé
        print(f"Génération de l'animation ({len(snapshots)} frames)...")
        anim.save(output_file + ".gif", writer='pillow', fps=1000//interval, dpi=80)
        print(f"Animation sauvegarde dans {output_file}.gif")
    else:
        plt.show()

    plt.close()


def save_final_solution(graph: SolvingStationGraph, output_file: str = "solution.png"):
    """
    Sauvegarde une image PNG de la solution finale
    :param graph: Le graphe avec la solution
    :param output_file: Nom du fichier de sortie
    """
    if not graph.snapshots:
        raise Exception("No snapshots recorded.")

    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)

    # Utiliser la dernière snapshot (solution finale)
    snapshot = graph.snapshots[-1]

    pos = {}
    for station in graph.list_stations():
        pos[station.number] = (station.long, station.lat)

    # Calculer les limites des axes
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    margin = 0.02
    x_margin = (max(all_x) - min(all_x)) * margin
    y_margin = (max(all_y) - min(all_y)) * margin
    xlim = (min(all_x) - x_margin, max(all_x) + x_margin)
    ylim = (min(all_y) - y_margin, max(all_y) + y_margin)

    G = nx.DiGraph()
    for sid in snapshot.station_map:
        G.add_node(sid)
    for sid, neighbor in snapshot.stations.items():
        if neighbor is not None:
            G.add_edge(sid, neighbor)

    node_colors = []
    for node in G.nodes():
        gap = snapshot.station_map[node].bike_gap()
        if gap > 0:
            node_colors.append('lightgreen')
        elif gap < 0:
            node_colors.append('lightcoral')
        else:
            node_colors.append('lightblue')

    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=700,
                          ax=ax, node_shape='s')

    nx.draw_networkx_edges(G, pos, edge_color='black', arrows=True,
                          arrowsize=20, width=2, ax=ax)

    labels = {}
    for sid, st in snapshot.station_map.items():
        labels[sid] = f"{sid}\n{st.bike_gap()}"
    nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold', ax=ax)

    ax.set_title("Solution finale", fontsize=16, fontweight='bold')
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)
    ax.axis('off')

    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()
