"""Rendus visuels liés au solveur de tournée (TIPE BSSR).

Trois charts produits dans `renders/` :
  * map.png          — tournée GPS réelle sur la carte de Nantes
  * load_profile.png — profil de charge du camion le long de la tournée
  * bounds.png       — ratio d'approximation par algorithme vs borne inférieure

Usage :
    python -m src.solver.render
    python -m src.solver.render --show              # ouvre la carte interactive
    python -m src.solver.render --no-real-path      # tournée à vol d'oiseau
"""

import argparse
import colorsys
import math
import os
import sqlite3
from datetime import datetime

import matplotlib.colors as mc
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.transforms import blended_transform_factory
from scipy.spatial import cKDTree

from src.objects.station import Station, TargetedStation
from src.solver.algorithm.builder.method1 import method1
from src.solver.algorithm.builder.method2 import method2
from src.solver.algorithm.incrementer.ils import ils
from src.solver.algorithm.incrementer.opt2 import opt2
from src.solver.algorithm.incrementer.or_opt import or_opt
from src.solver.graph import SolvingStationGraph
from src.solver.map import Map
from src.solver.reviewer import _tour_time, compute_lower_bound, review_solution


# ============================================================================
# Constantes
# ============================================================================

TRUCK_CAPACITY    = 30
TARGET_FILL_RATIO = 0.4
ILS_MAX_ITER      = 20

DEFAULT_DB       = "data/clean/clean_2026-05-11.sql"
DEFAULT_SNAPSHOT = "2026-05-11 18:00:00"
DEFAULT_OUT_DIR  = "renders"

_COLOR_DEPOT    = "#0b3d91"
_COLOR_SURPLUS  = "#2ca02c"
_COLOR_DEFICIT  = "#d62728"
_COLOR_OFF      = "#777777"
_COLOR_ROUTE    = "#1a3d7a"
_COLOR_CAPACITY = "#d62728"

# Palette algorithmes : teinte = constructeur, intensité = puissance improver.
COLOR_M1 = ["#d6e4ff", "#aac4f5", "#6090d8", "#2e5fb0", "#0b3d91"]
COLOR_M2 = ["#ffd9b3", "#ffae66", "#ff8019", "#d65a00", "#963f00"]
ALGO_COLORS = {
    "method1 seul":             COLOR_M1[0],
    "method1 + OPT_2":          COLOR_M1[1],
    "method1 + OR_OPT":         COLOR_M1[2],
    "method1 + OPT_2 + OR_OPT": COLOR_M1[3],
    "method1 + ILS":            COLOR_M1[4],
    "method2 seul":             COLOR_M2[0],
    "method2 + OPT_2":          COLOR_M2[1],
    "method2 + OR_OPT":         COLOR_M2[2],
    "method2 + OPT_2 + OR_OPT": COLOR_M2[3],
    "method2 + ILS":            COLOR_M2[4],
}

_ROAD_TIERS = {
    'major': ({'motorway', 'motorway_link', 'trunk', 'trunk_link',
               'primary', 'primary_link'}, "#5a5a5a", 1.4),
    'mid':   ({'secondary', 'secondary_link', 'tertiary', 'tertiary_link'},
              "#9a9a9a", 0.8),
}
_ROAD_MINOR_STYLE = ("#dadada", 0.35)


# ============================================================================
# A — Chargement instance + préparation carte
# ============================================================================

def load_stations(db_path: str) -> list[Station]:
    """Charge le référentiel des stations depuis un clean_*.sql."""
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT station_number, name, capacity, address, geo_lat, geo_long "
        "FROM stations ORDER BY station_number"
    ).fetchall()
    con.close()
    # Attention : Station(..., long, lat) — l'ordre est (longitude, latitude).
    return [Station(n, name, cap, addr, lon, lat) for n, name, cap, addr, lat, lon in rows]


def load_counts(db_path: str, snapshot: str) -> dict[int, int]:
    """Compte de vélos par station au plus proche du timestamp donné."""
    con = sqlite3.connect(db_path)
    rows = con.execute(
        """
        SELECT station_number, available_bikes
        FROM station_history h1
        WHERE timestamp = (
            SELECT MAX(timestamp) FROM station_history h2
            WHERE h2.station_number = h1.station_number AND h2.timestamp <= ?
        )
        """,
        (snapshot,),
    ).fetchall()
    con.close()
    return {n: c for n, c in rows}


def build_targeted(stations: list[Station], counts: dict[int, int],
                   truck_capacity: int) -> tuple[list[TargetedStation], Station, TargetedStation]:
    """Construit des `TargetedStation` solvables + un dépôt synthétique au barycentre.

    Garantit : 0 ≤ bike_count, bike_target ≤ capacité ; |bike_gap| ≤ q/2 ;
    sum(bike_gap) = 0 ; dépôt à gap nul.
    """
    max_gap = truck_capacity // 2
    targets     = {s.number: round(s.capacity * TARGET_FILL_RATIO) for s in stations}
    bike_counts = {s.number: min(counts.get(s.number, 0), s.capacity) for s in stations}

    for s in stations:
        gap = bike_counts[s.number] - targets[s.number]
        if gap > max_gap:
            targets[s.number] = bike_counts[s.number] - max_gap
        elif gap < -max_gap:
            targets[s.number] = bike_counts[s.number] + max_gap
        targets[s.number] = max(0, min(s.capacity, targets[s.number]))

    def residual() -> int:
        return sum(bike_counts[s.number] - targets[s.number] for s in stations)

    safety = 10 * len(stations)
    while residual() != 0 and safety > 0:
        r = residual()
        step = 1 if r > 0 else -1
        moved = False
        for s in stations:
            if r == 0:
                break
            new_target = targets[s.number] + step
            new_gap = bike_counts[s.number] - new_target
            if 0 <= new_target <= s.capacity and abs(new_gap) <= max_gap:
                targets[s.number] = new_target
                r -= step
                moved = True
        if not moved:
            break
        safety -= 1

    assert residual() == 0, f"Échec d'équilibrage, résiduel = {residual()}"

    targeted = [TargetedStation.from_station(s, bike_counts[s.number], targets[s.number])
                for s in stations]
    mean_lat  = sum(s.lat  for s in stations) / len(stations)
    mean_long = sum(s.long for s in stations) / len(stations)
    depot          = Station(0, "DÉPÔT (barycentre)", 0, "", mean_long, mean_lat)
    depot_targeted = TargetedStation.from_station(depot, 0, 0)
    return targeted, depot, depot_targeted


def restrict_to_largest_scc(nantes: Map) -> None:
    """Restreint le graphe routier à sa plus grande composante fortement connexe."""
    sccs = list(nx.strongly_connected_components(nantes.graph))
    largest = max(sccs, key=len)
    if len(largest) < len(nantes.graph.nodes):
        nantes.graph = nantes.graph.subgraph(largest).copy()


def warm_node_cache(nantes: Map, stations: list[Station]) -> None:
    """Pré-remplit `Map._node_cache` via scipy (évite la dépendance sklearn d'osmnx)."""
    node_ids = list(nantes.graph.nodes)
    coords = np.array([(nantes.graph.nodes[n]['x'], nantes.graph.nodes[n]['y'])
                       for n in node_ids])
    tree = cKDTree(coords)
    queries = np.array([(s.long, s.lat) for s in stations])
    _, idx = tree.query(queries, k=1)
    for s, i in zip(stations, idx):
        nantes._node_cache[(s.lat, s.long)] = node_ids[int(i)]


# ============================================================================
# B — Helpers de rendu
# ============================================================================

def _ordered_tour(graph: SolvingStationGraph) -> list[TargetedStation]:
    """Lit la tournée depuis le dépôt (station 0)."""
    tour = [graph.get_station(0)]
    current = graph.get_successor(0)
    seen = {0}
    while current is not None and current not in seen:
        seen.add(current)
        tour.append(graph.get_station(current))
        current = graph.get_successor(current)
    return tour


def _marker_size(station: TargetedStation) -> float:
    if station.number == 0:
        return 240.0
    return 60.0 + 18.0 * abs(station.bike_gap())


def _plot_roads(ax, road_graph) -> None:
    """Trame routière OSM hiérarchisée par type de voie."""
    import osmnx as ox
    edges = ox.graph_to_gdfs(road_graph, nodes=False)
    edges['_hw'] = edges['highway'].map(lambda v: v[0] if isinstance(v, list) else v)
    plotted = set()
    for types, color, lw in _ROAD_TIERS.values():
        subset = edges[edges['_hw'].isin(types)]
        if not subset.empty:
            subset.plot(ax=ax, color=color, linewidth=lw, zorder=1)
            plotted.update(subset.index)
    minor = edges.drop(index=plotted)
    if not minor.empty:
        c, lw = _ROAD_MINOR_STYLE
        minor.plot(ax=ax, color=c, linewidth=lw, zorder=1)


def _plot_water(ax, bbox: tuple[float, float, float, float],
                cache_file: str = "data/nantes_water.geojson") -> None:
    """Loire/Erdre/plans d'eau — téléchargés OSM puis cachés."""
    import geopandas as gpd
    import osmnx as ox
    if os.path.exists(cache_file):
        gdf = gpd.read_file(cache_file)
    else:
        west, south, east, north = bbox
        gdf = ox.features_from_bbox(
            bbox=(west, south, east, north),
            tags={"natural": "water", "waterway": True, "water": True})
        gdf = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon',
                                           'LineString', 'MultiLineString'])]
        os.makedirs(os.path.dirname(cache_file) or '.', exist_ok=True)
        gdf.to_file(cache_file, driver="GeoJSON")
    polys = gdf[gdf.geometry.type.isin(['Polygon', 'MultiPolygon'])]
    lines = gdf[gdf.geometry.type.isin(['LineString', 'MultiLineString'])]
    if not polys.empty:
        polys.plot(ax=ax, color="#cfe4f5", edgecolor="#a8c8e0",
                   linewidth=0.4, zorder=0)
    if not lines.empty:
        lines.plot(ax=ax, color="#a8c8e0", linewidth=0.6, zorder=0)


def _road_path_coords(road_graph, src_node: int, dst_node: int) -> list[tuple[float, float]]:
    """Polyline (x=lon, y=lat) du plus court chemin routier entre 2 nœuds OSM."""
    path = nx.shortest_path(road_graph, src_node, dst_node, weight='length')
    coords: list[tuple[float, float]] = []
    for u, v in zip(path[:-1], path[1:]):
        data = min(road_graph[u][v].values(),
                   key=lambda e: e.get('length', float('inf')))
        geom = data.get('geometry')
        if geom is not None:
            xs, ys = geom.xy
            seg = list(zip(xs, ys))
        else:
            seg = [(road_graph.nodes[u]['x'], road_graph.nodes[u]['y']),
                   (road_graph.nodes[v]['x'], road_graph.nodes[v]['y'])]
        if coords and seg and coords[-1] == seg[0]:
            coords.extend(seg[1:])
        else:
            coords.extend(seg)
    return coords


def _station_to_node(map_obj, station: Station) -> int:
    return map_obj._node_cache[(station.lat, station.long)]


# ============================================================================
# C — Fonctions de rendu
# ============================================================================

def render_map(graph: SolvingStationGraph,
               all_stations: list[Station],
               output_file: str | None = None,
               title: str | None = None,
               show_roads: bool = True,
               show_water: bool = True,
               real_path: bool = True,
               show: bool = False) -> None:
    """Carte géographique de la tournée (trajet routier réel par défaut)."""
    if not all_stations:
        raise ValueError("all_stations doit contenir au moins une station.")
    if output_file is None and not show:
        raise ValueError("Préciser au moins output_file ou show=True.")

    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_facecolor("#fafafa")

    lats  = [s.lat  for s in all_stations]
    longs = [s.long for s in all_stations]
    pad_lat  = 0.05 * (max(lats)  - min(lats))
    pad_long = 0.05 * (max(longs) - min(longs))
    xlim = (min(longs) - pad_long, max(longs) + pad_long)
    ylim = (min(lats)  - pad_lat,  max(lats)  + pad_lat)

    if show_water:
        _plot_water(ax, bbox=(xlim[0], ylim[0], xlim[1], ylim[1]))
    if show_roads:
        _plot_roads(ax, graph.map.graph)

    visited = {s.number for s in graph.list_stations()}
    off = [s for s in all_stations if s.number not in visited]
    if off:
        ax.scatter([s.long for s in off], [s.lat for s in off],
                   s=12, c=_COLOR_OFF, zorder=2,
                   edgecolors="white", linewidths=0.4)

    tour = _ordered_tour(graph)
    edges_seq = list(zip(tour, tour[1:] + [tour[0]]))

    if real_path:
        for s1, s2 in edges_seq:
            src_node = _station_to_node(graph.map, s1)
            dst_node = _station_to_node(graph.map, s2)
            coords: list[tuple[float, float]]
            if src_node == dst_node:
                coords = [(s1.long, s1.lat), (s2.long, s2.lat)]
            else:
                try:
                    coords = _road_path_coords(graph.map.graph, src_node, dst_node)
                except nx.NetworkXNoPath:
                    coords = [(s1.long, s1.lat), (s2.long, s2.lat)]
            if len(coords) < 2:
                coords = [(s1.long, s1.lat), (s2.long, s2.lat)]
            xs, ys = zip(*coords)
            ax.plot(xs, ys, color=_COLOR_ROUTE, lw=2.2, alpha=0.85, zorder=3,
                    solid_capstyle='round', solid_joinstyle='round')
            mid_idx = max(1, int(0.8 * len(coords)))
            x1, y1 = coords[mid_idx - 1]
            x2, y2 = coords[min(mid_idx, len(coords) - 1)]
            if (x1, y1) != (x2, y2):
                ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                            arrowprops=dict(arrowstyle="-|>",
                                            color=_COLOR_ROUTE, lw=0,
                                            mutation_scale=12), zorder=3)
    else:
        for s1, s2 in edges_seq:
            rA = math.sqrt(_marker_size(s1)) / 2 + 2.0
            rB = math.sqrt(_marker_size(s2)) / 2 + 3.0
            ax.annotate("", xy=(s2.long, s2.lat), xytext=(s1.long, s1.lat),
                        arrowprops=dict(arrowstyle="-|>", color=_COLOR_ROUTE,
                                        alpha=0.9, lw=1.4,
                                        shrinkA=rA, shrinkB=rB,
                                        mutation_scale=14), zorder=3)

    for station in graph.list_stations():
        if station.number == 0:
            ax.scatter([station.long], [station.lat], s=_marker_size(station),
                       c=_COLOR_DEPOT, marker="s",
                       edgecolors="white", linewidths=1.6, zorder=5)
        else:
            color = _COLOR_SURPLUS if station.bike_gap() > 0 else _COLOR_DEFICIT
            ax.scatter([station.long], [station.lat], s=_marker_size(station),
                       c=color, edgecolors="white", linewidths=1.0, zorder=4)

    ax.legend(handles=[
        Line2D([], [], marker="s", linestyle="", markerfacecolor=_COLOR_DEPOT,
               markeredgecolor="white", markersize=12, label="Dépôt"),
        Line2D([], [], marker="o", linestyle="", markerfacecolor=_COLOR_SURPLUS,
               markeredgecolor="white", markersize=11, label="Surplus (à collecter)"),
        Line2D([], [], marker="o", linestyle="", markerfacecolor=_COLOR_DEFICIT,
               markeredgecolor="white", markersize=11, label="Déficit (à remplir)"),
        Line2D([], [], marker="o", linestyle="", markerfacecolor=_COLOR_OFF,
               markeredgecolor="white", markersize=7,  label="Station hors tournée"),
        Line2D([], [], color=_COLOR_ROUTE, lw=2.0, label="Tournée du camion"),
    ], loc="upper right", frameon=True, framealpha=0.95, fontsize=10)

    ax.set_xlim(*xlim); ax.set_ylim(*ylim)
    ax.set_aspect(1.0 / math.cos(math.radians(sum(lats) / len(lats))))
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    if title:
        ax.set_title(title)

    fig.tight_layout()
    if output_file is not None:
        fig.savefig(output_file, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)


def render_load_profile(graph: SolvingStationGraph, capacity: int,
                        output_file: str, title: str | None = None) -> None:
    """Charge du camion en vélos le long de la tournée (step function)."""
    tour = _ordered_tour(graph)
    loads = [0]
    for s in tour[1:]:
        loads.append(loads[-1] + s.bike_gap())
    loads.append(loads[-1])
    xs = list(range(len(loads)))

    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.set_facecolor("#fafafa")
    ax.axhline(capacity, color=_COLOR_CAPACITY, lw=1.0, ls='--', alpha=0.8,
               label=f"Capacité = {capacity}")
    ax.axhline(0, color="#888", lw=0.7, ls=':')
    ax.fill_between(xs, 0, loads, step='post', color=_COLOR_ROUTE, alpha=0.15)
    ax.step(xs, loads, where='post', color=_COLOR_ROUTE, lw=1.8,
            label="Charge du camion")

    for i, s in enumerate(tour):
        if s.number == 0:
            ax.scatter([i], [loads[i]], s=80, c=_COLOR_DEPOT, marker="s",
                       edgecolors="white", linewidths=1.0, zorder=5)
        else:
            color = _COLOR_SURPLUS if s.bike_gap() > 0 else _COLOR_DEFICIT
            ax.scatter([i], [loads[i]], s=40, c=color,
                       edgecolors="white", linewidths=0.8, zorder=5)

    peak, trough = max(loads), min(loads)
    ax.annotate(f"pic {peak} vélos", xy=(loads.index(peak), peak),
                xytext=(0, 14), textcoords='offset points',
                fontsize=9, color="#444", ha='center')
    if trough < 0:
        ax.annotate(f"creux {trough}", xy=(loads.index(trough), trough),
                    xytext=(0, -16), textcoords='offset points',
                    fontsize=9, color="#444", ha='center')

    ax.set_xlim(-0.5, len(loads) - 0.5)
    ax.set_ylim(min(-1, trough - 1), max(capacity + 2, peak + 3))
    ax.set_xlabel("Position dans la tournée (n° d'arrêt)")
    ax.set_ylabel("Vélos dans le camion")
    if title:
        ax.set_title(title)
    ax.legend(loc='upper right', fontsize=9, frameon=True, framealpha=0.95)
    ax.grid(axis='y', alpha=0.3)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)

    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)


def render_bounds(graph: SolvingStationGraph, capacity: int,
                  output_file: str, title: str | None = None,
                  main_label: str = "Solution",
                  extra_solutions: dict[str, float] | None = None,
                  colors: dict[str, str] | None = None,
                  ordered_labels: list[str] | None = None) -> None:
    """Bar chart style p-approximation : ratio = sol/borne_inf."""
    lb  = compute_lower_bound(graph)
    sol = _tour_time(graph)

    palette_extra = ["#1f77b4", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2"]
    bars: list[tuple[str, float, str]] = [(main_label, sol, _COLOR_ROUTE)]
    if extra_solutions:
        for i, (name, t) in enumerate(extra_solutions.items()):
            bars.append((name, t, palette_extra[i % len(palette_extra)]))
    if colors:
        bars = [(name, t, colors.get(name, c)) for name, t, c in bars]
    if ordered_labels:
        order = {name: i for i, name in enumerate(ordered_labels)}
        bars.sort(key=lambda b: order.get(b[0], len(order)))
    else:
        bars.sort(key=lambda b: b[1])

    labels = [b[0] for b in bars]
    values = [b[1] / 60 for b in bars]
    ratios = [b[1] / lb if lb > 0 else float('inf') for b in bars]
    bar_colors = [b[2] for b in bars]

    def _luminance(hex_color: str) -> float:
        r, g, b = mc.to_rgb(hex_color)
        return 0.299 * r + 0.587 * g + 0.114 * b

    def _darken(hex_color: str, amount: float = 0.45) -> tuple:
        h, l, s = colorsys.rgb_to_hls(*mc.to_rgb(hex_color))
        return colorsys.hls_to_rgb(h, max(0, l * (1 - amount)), s)

    text_in_bar    = ['black' if _luminance(c) > 0.6 else 'white' for c in bar_colors]
    text_above_bar = [_darken(c, 0.5) if _luminance(c) > 0.55 else c for c in bar_colors]

    lb_min = lb / 60
    v_max  = max(values)
    margin = (v_max - lb_min) * 0.18
    band_h = (v_max - lb_min) * 0.13
    y_bottom = lb_min - band_h
    y_top    = v_max + margin

    fig, ax = plt.subplots(figsize=(max(7, len(bars) * 1.4), 6))
    ax.set_facecolor("#fafafa")
    pos = list(range(len(bars)))
    ax.bar(pos, [v - lb_min for v in values], bottom=lb_min,
           color=bar_colors, edgecolor="white", linewidth=1.2, width=0.7)

    for i, (v, r) in enumerate(zip(values, ratios)):
        ax.text(i, v + margin * 0.06, f"{r:.2f}×",
                ha='center', va='bottom', fontsize=14, fontweight='bold',
                color=text_above_bar[i])
        ax.text(i, v - (v - lb_min) * 0.08, f"{v:.1f} min",
                ha='center', va='top', fontsize=9, color=text_in_bar[i],
                fontweight='bold')

    ax.axhspan(y_bottom, lb_min, facecolor="#e8f3e0", edgecolor="#2a7a2a",
               hatch='///', alpha=0.65, linewidth=0, zorder=0)
    ax.axhline(lb_min, color="#1e5a1e", lw=2.8, ls='-', alpha=1.0, zorder=6)
    ax.text((len(bars) - 1) / 2, (y_bottom + lb_min) / 2,
            f"Borne inférieure  =  {lb_min:.1f} min  ·  1.00×",
            ha='center', va='center', fontsize=10, fontweight='bold',
            color="#1e5a1e", zorder=7)

    trans = blended_transform_factory(ax.transAxes, ax.transData)
    tick_h = band_h * 0.15
    ax.plot([-0.013, 0.013], [y_bottom + tick_h * 0.4, y_bottom + tick_h * 1.6],
            transform=trans, color="black", lw=1.3, clip_on=False, zorder=10)
    ax.plot([-0.013, 0.013], [y_bottom - tick_h * 0.4, y_bottom + tick_h * 0.8],
            transform=trans, color="black", lw=1.3, clip_on=False, zorder=10)

    ax2 = ax.twinx()
    ax2.set_ylim(y_bottom / lb_min, y_top / lb_min)
    ax2.set_ylabel("Ratio  (sol / borne inf)", color="#444")
    ax2.tick_params(axis='y', colors="#444")
    ax2.spines['top'].set_visible(False)

    ax.text(0.01, 0.98,
            "Ratio observé = temps / borne inférieure",
            transform=ax.transAxes, ha='left', va='top', fontsize=9,
            bbox=dict(boxstyle='round,pad=0.4', facecolor='white',
                      edgecolor='#bbb', alpha=0.95))

    ax.set_xticks(pos)
    ax.set_xticklabels(labels, rotation=15, ha='right', fontsize=10)
    ax.set_ylabel("Temps de parcours (minutes)")
    ax.set_ylim(y_bottom, y_top)
    ax.grid(axis='y', alpha=0.3)
    for spine in ('top', 'right'):
        ax.spines[spine].set_visible(False)
    if title:
        ax.set_title(title)

    fig.tight_layout()
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# D — Orchestration : résoudre 10 configs + produire les 3 charts
# ============================================================================

def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db",       default=DEFAULT_DB)
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    p.add_argument("--out-dir",  default=DEFAULT_OUT_DIR)
    p.add_argument("--no-roads", action="store_true")
    p.add_argument("--no-water", action="store_true")
    p.add_argument("--no-real-path", action="store_true",
                   help="Tournée en droites vol d'oiseau au lieu du trajet routier")
    p.add_argument("--show", action="store_true",
                   help="Ouvre la carte interactive matplotlib (zoom/pan)")
    args = p.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    out = lambda name: os.path.join(args.out_dir, name)

    print(f"[{datetime.now():%H:%M:%S}] Chargement {args.db}")
    stations = load_stations(args.db)
    counts   = load_counts(args.db, args.snapshot)
    print(f"  {len(stations)} stations, {sum(counts.values())} vélos au snapshot {args.snapshot}")

    targeted, depot, depot_targeted = build_targeted(stations, counts, TRUCK_CAPACITY)
    n_surplus = sum(1 for t in targeted if t.bike_gap() > 0)
    n_deficit = sum(1 for t in targeted if t.bike_gap() < 0)
    print(f"  {n_surplus} surplus, {n_deficit} déficit, "
          f"|gap| max = {max(abs(t.bike_gap()) for t in targeted)}")

    print(f"[{datetime.now():%H:%M:%S}] Chargement carte Nantes")
    nantes = Map("data/nantes_graph.graphml")
    restrict_to_largest_scc(nantes)
    warm_node_cache(nantes, stations + [depot])

    def fresh_graph(shared_cache: dict | None = None) -> SolvingStationGraph:
        g = SolvingStationGraph(nantes, depot)
        g.station_map[0] = depot_targeted
        for t in targeted:
            if t.bike_gap() != 0:
                g.add_station(t)
        if shared_cache is not None:
            g.time_cache = shared_cache
        return g

    def run_config(name, builder_fn, improvers, shared_cache):
        g = fresh_graph(shared_cache)
        g.preload_times()
        try:
            builder_fn(g, TRUCK_CAPACITY)
            for imp in improvers:
                imp(g, TRUCK_CAPACITY)
            metrics = review_solution(g, TRUCK_CAPACITY)
        except Exception as exc:
            print(f"  {name:30s}  ÉCHEC ({exc})")
            return None, g.time_cache
        print(f"  {name:30s}  temps = {metrics.time/60:6.1f} min  ·  ratio = {metrics.ratio:.2f}×")
        return (metrics.time, metrics.ratio, g), g.time_cache

    def imp_opt2 (g, c): opt2  (g, c, max_iterations=500)
    def imp_oropt(g, c): or_opt(g, c, max_iterations=500)
    def imp_ils  (g, c): ils   (g, c, max_iterations=ILS_MAX_ITER)

    configs = [
        ("method1 seul",             method1, []),
        ("method1 + OPT_2",          method1, [imp_opt2]),
        ("method1 + OR_OPT",         method1, [imp_oropt]),
        ("method1 + OPT_2 + OR_OPT", method1, [imp_opt2, imp_oropt]),
        ("method1 + ILS",            method1, [imp_ils]),
        ("method2 seul",             method2, []),
        ("method2 + OPT_2",          method2, [imp_opt2]),
        ("method2 + OR_OPT",         method2, [imp_oropt]),
        ("method2 + OPT_2 + OR_OPT", method2, [imp_opt2, imp_oropt]),
        ("method2 + ILS",            method2, [imp_ils]),
    ]

    results: dict[str, tuple[float, SolvingStationGraph]] = {}
    shared_cache: dict | None = None
    for name, builder_fn, improvers in configs:
        print(f"[{datetime.now():%H:%M:%S}] Résolution — {name}")
        outcome, shared_cache = run_config(name, builder_fn, improvers, shared_cache)
        if outcome is not None:
            t, _, g = outcome
            results[name] = (t, g)

    if not results:
        raise SystemExit("Toutes les configurations ont échoué.")

    best_name, (best_time, best_graph) = min(results.items(), key=lambda kv: kv[1][0])
    print(f"[{datetime.now():%H:%M:%S}] Meilleure config : {best_name}  ({best_time/60:.1f} min)")

    suffix     = f"  ·  {best_time/60:.1f} min  ·  {best_name}"
    base_title = f"Tournée Bicloo Nantes — {best_graph.size()-1}/{len(stations)} stations"

    print(f"[{datetime.now():%H:%M:%S}] (1/3) map.png")
    render_map(
        best_graph, all_stations=stations,
        output_file=out("map.png"),
        title=base_title + suffix,
        show_roads=not args.no_roads, show_water=not args.no_water,
        real_path=not args.no_real_path, show=args.show)

    print(f"[{datetime.now():%H:%M:%S}] (2/3) load_profile.png")
    render_load_profile(
        best_graph, TRUCK_CAPACITY, output_file=out("load_profile.png"),
        title=f"Profil de charge — {best_name} · camion {TRUCK_CAPACITY} vélos{suffix}")

    print(f"[{datetime.now():%H:%M:%S}] (3/3) bounds.png")
    extras = {name: t for name, (t, _) in results.items() if name != best_name}
    ordered_labels = [name for name, _, _ in configs if name in results]
    render_bounds(
        best_graph, TRUCK_CAPACITY,
        output_file=out("bounds.png"),
        title="Ratio d'approximation par algorithme",
        main_label=best_name, extra_solutions=extras,
        colors=ALGO_COLORS, ordered_labels=ordered_labels)

    print(f"[{datetime.now():%H:%M:%S}] Écrits dans {args.out_dir}/ : map.png, load_profile.png, bounds.png")


if __name__ == "__main__":
    main()
