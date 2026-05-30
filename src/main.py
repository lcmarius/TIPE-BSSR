import argparse
import os
from datetime import date, datetime

from src.utils.timezone import local_to_utc_naive, now_utc_naive, utc_naive_to_local


# Imports paresseux dans les `cmd_*` : on ne charge le solver / OSMnx que si on
# lance effectivement une commande qui en a besoin.


# Présets de villes : slug court → (nom OSMnx complet, chemin du graphml caché).
# Toute autre valeur de --city est passée telle quelle à OSMnx, le cache étant
# alors écrit dans data/<slug>_graph.graphml (slug dérivé du premier mot).
CITY_PRESETS: dict[str, tuple[str, str]] = {
    "nantes": ("Nantes Métropole, France", "data/nantes_graph.graphml"),
}

# Itérations max passées aux improvers opt2 / or_opt (ILS utilise son propre
# défaut). Aligné sur `src/solver/render.py`.
IMPROVER_ITERS = 500


def _resolve_city(city_arg: str) -> tuple[str, str]:
    """Renvoie (nom OSMnx complet, chemin graphml) à partir d'un --city."""
    key = city_arg.lower().strip()
    if key in CITY_PRESETS:
        return CITY_PRESETS[key]
    slug = city_arg.split(",")[0].strip().lower().replace(" ", "_")
    return city_arg, f"data/{slug}_graph.graphml"


def _load_clean_snapshot(db_path: str, snapshot: str):
    """Charge le référentiel des stations et leurs counts à `snapshot`."""
    import sqlite3
    from src.objects.station import Station
    con = sqlite3.connect(db_path)
    # Attention : Station(..., long, lat) — l'ordre des arguments est (longitude, latitude).
    rows = con.execute(
        "SELECT station_number, name, capacity, address, geo_lat, geo_long "
        "FROM stations ORDER BY station_number"
    ).fetchall()
    stations = [Station(n, name, cap, addr, lon, lat)
                for n, name, cap, addr, lat, lon in rows]
    count_rows = con.execute(
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
    return stations, {n: c for n, c in count_rows}


def _synthetic_depot(stations):
    """Dépôt fictif au barycentre des stations (number=0, gap=0)."""
    from src.objects.station import Station
    if not stations:
        raise SystemExit("Aucune station chargée.")
    mean_lat  = sum(s.lat  for s in stations) / len(stations)
    mean_long = sum(s.long for s in stations) / len(stations)
    return Station(0, "DÉPÔT (barycentre)", 0, "", mean_long, mean_lat)


def _restrict_to_largest_scc(road_map):
    """Restreint le graphe routier à sa plus grande composante fortement connexe."""
    import networkx as nx
    sccs = list(nx.strongly_connected_components(road_map.graph))
    largest = max(sccs, key=len)
    if len(largest) < len(road_map.graph.nodes):
        road_map.graph = road_map.graph.subgraph(largest).copy()


def _warm_node_cache(road_map, stations):
    """Pré-remplit Map._node_cache via scipy (évite la dépendance sklearn d'osmnx)."""
    import numpy as np
    from scipy.spatial import cKDTree
    node_ids = list(road_map.graph.nodes)
    coords = np.array([(road_map.graph.nodes[n]['x'], road_map.graph.nodes[n]['y'])
                       for n in node_ids])
    tree = cKDTree(coords)
    queries = np.array([(s.long, s.lat) for s in stations])
    _, idx = tree.query(queries, k=1)
    for s, i in zip(stations, idx):
        road_map._node_cache[(s.lat, s.long)] = node_ids[int(i)]


def cmd_scrapper(args):
    from src.scrapper.database import archive_db
    from src.scrapper.scrapper import Scrapper
    db_path = os.path.join(args.data_dir, "current.sql")
    if args.archive:
        archive_db(db_path)
    Scrapper(
        db_path=db_path,
        poll_interval=args.interval,
        status_interval=args.status_interval,
    ).run()


def cmd_postprocess(args):
    from src.scrapper.postprocess import run_postprocess
    run_postprocess(
        args.db_path,
        date.fromisoformat(args.date),
        args.output_dir,
        keep_truck=args.keep_truck,
    )


def cmd_solve(args):
    from src.solver.algorithm.builder.method1 import method1
    from src.solver.algorithm.builder.method2 import method2
    from src.solver.algorithm.incrementer.ils import ils
    from src.solver.algorithm.incrementer.opt2 import opt2
    from src.solver.algorithm.incrementer.or_opt import or_opt
    from src.solver.map import Map
    from src.solver.reviewer import review_solution
    from src.solver.solver import create_graph, is_graph_solvable
    from src.targeter.targeter import compute_adjusted_targets, InfeasibleInstance

    # `--snapshot` est de l'heure locale Paris (intuition utilisateur). On
    # convertit en UTC naïf pour matcher les timestamps en base (cf.
    # src/utils/timezone.py). Le nom de fichier clean_*.sql reste indexé sur
    # la date locale.
    when = datetime.fromisoformat(args.snapshot)
    when_utc = local_to_utc_naive(when)
    db_path = os.path.join(args.clean_dir, f"clean_{when.date().isoformat()}.sql")
    if not os.path.isfile(db_path):
        raise SystemExit(f"Fichier introuvable : {db_path}")

    print(f"[1/5] Snapshot  · {db_path} @ {args.snapshot}")
    stations, counts = _load_clean_snapshot(db_path, when_utc.strftime("%Y-%m-%d %H:%M:%S"))
    print(f"      → {len(stations)} stations, {len(counts)} counts disponibles")

    depot = _synthetic_depot(stations)

    print(f"[2/5] Targeter  · Skellam sur historique {args.clean_dir}/  ·  camion = {args.capacity} vélos")
    try:
        targeted = compute_adjusted_targets(stations, counts, when, args.capacity,
                                             clean_dir=args.clean_dir)
    except InfeasibleInstance as exc:
        raise SystemExit(f"      Cibles infaisables : {exc}")
    print(f"      → {len(targeted)} stations à rééquilibrer (bike_gap ≠ 0)")
    from collections import Counter
    gap_dist = Counter(t.bike_gap() for t in targeted)
    gap_summary = "  ".join(f"{k:+d}×{v}" for k, v in sorted(gap_dist.items()))
    print(f"      → distribution gaps : {gap_summary}")

    full_city, graphml = _resolve_city(args.city)
    print(f"[3/5] Carte     · {full_city}")
    road_map = Map(graphml, city=full_city)
    _restrict_to_largest_scc(road_map)
    _warm_node_cache(road_map, [depot, *targeted])
    print(f"      → {len(road_map.graph.nodes)} nœuds (SCC restreinte + cache spatial pré-rempli)")

    # ────────────────────────────────────────────────────────────────────────
    # [4/5] Pour chaque config : on repart d'un graphe neuf et on relance le
    # builder + la chaîne d'improvers (pas de waterfall — chaque ligne est
    # autonome et reproductible). Seule la matrice des temps de trajet, qui
    # ne dépend que du réseau routier, est calculée UNE fois sur un graphe
    # maître puis partagée par référence à tous les graphes des configs.
    # ────────────────────────────────────────────────────────────────────────
    print(f"[4/5] Solveur   · pré-calcul des temps de trajet")
    master = create_graph(targeted, depot, road_map)
    if not is_graph_solvable(master, args.capacity):
        raise SystemExit("      Graphe non solvable (contraintes C1/C2 violées).")
    master.preload_times()
    time_cache = master.time_cache
    n_pairs = (len(targeted) + 1) * len(targeted)
    print(f"      → {n_pairs} temps de trajet en cache (partagés entre toutes les configs)")

    # Wrappers d'improvers : capturent capacité + nombre d'itérations, pour
    # uniformiser la signature (g) → None côté boucle de configs.
    def imp_opt2 (g): opt2  (g, args.capacity, max_iterations=IMPROVER_ITERS)
    def imp_oropt(g): or_opt(g, args.capacity, max_iterations=IMPROVER_ITERS)
    def imp_ils  (g): ils   (g, args.capacity)

    # 12 configs : 2 builders × {seul, +opt2, +or_opt, +opt2+or_opt, +or_opt+opt2, +ils}.
    configs = [
        ("method1",                  method1, []),
        ("method1 + opt2",           method1, [imp_opt2]),
        ("method1 + or_opt",         method1, [imp_oropt]),
        ("method1 + opt2 + or_opt",  method1, [imp_opt2, imp_oropt]),
        ("method1 + or_opt + opt2",  method1, [imp_oropt, imp_opt2]),
        ("method1 + ils",            method1, [imp_ils]),
        ("method2",                  method2, []),
        ("method2 + opt2",           method2, [imp_opt2]),
        ("method2 + or_opt",         method2, [imp_oropt]),
        ("method2 + opt2 + or_opt",  method2, [imp_opt2, imp_oropt]),
        ("method2 + or_opt + opt2",  method2, [imp_oropt, imp_opt2]),
        ("method2 + ils",            method2, [imp_ils]),
    ]

    print()
    print(f"      {'Configuration':<33}  {'Temps':>10}  {'Ratio':>8}")
    print(f"      {'─' * 33}  {'─' * 10}  {'─' * 8}")

    results: list[tuple[str, object]] = []
    for label, builder_fn, improvers in configs:
        g = create_graph(targeted, depot, road_map)
        g.time_cache = time_cache  # cache partagé avec le maître
        builder_fn(g, args.capacity)
        for imp in improvers:
            imp(g)
        m = review_solution(g, args.capacity)
        results.append((label, m))
        print(f"      {label:<33}  {m.time/60:>7.1f} min  {m.ratio:>7.3f}×")

    ranking = sorted(results, key=lambda r: r[1].time)
    print()
    print(f"[5/5] Classement (du meilleur au moins bon) :")
    print(f"      {'#':>2}  {'Configuration':<33}  {'Temps':>10}  {'Ratio':>8}")
    print(f"      {'─' * 2}  {'─' * 33}  {'─' * 10}  {'─' * 8}")
    for i, (label, m) in enumerate(ranking, 1):
        print(f"      {i:>2}  {label:<33}  {m.time/60:>7.1f} min  {m.ratio:>7.3f}×")


def main():
    parser = argparse.ArgumentParser(
        description="TIPE-BSSR — pipeline complet Bicloo Nantes : "
                    "collecte, nettoyage, calcul de cibles, optimisation de tournée.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sp = subparsers.add_parser("scrapper", help="Collecte temps réel des mouvements de vélos")
    sp.add_argument("--interval", type=int, default=5,
                    help="Intervalle polling /bikes en secondes (défaut: 5)")
    sp.add_argument("--status-interval", type=int, default=300,
                    help="Intervalle recalage /station_status en secondes (défaut: 300)")
    sp.add_argument("--data-dir", type=str, default="data",
                    help="Répertoire des données (défaut: data)")
    sp.add_argument("--no-archive", dest="archive", action="store_false",
                    help="Ne pas archiver la session précédente")
    sp.set_defaults(func=cmd_scrapper)

    sp_pp = subparsers.add_parser("postprocess", help="Nettoyage d'une journée de scrap")
    sp_pp.add_argument("db_path", help="Chemin vers la DB brute à nettoyer")
    sp_pp.add_argument("--date", required=True, help="Jour à extraire (YYYY-MM-DD)")
    sp_pp.add_argument("--output-dir", default=None,
                       help="Dossier de sortie (défaut: dossier de la DB source)")
    sp_pp.add_argument("--no-keep-truck", dest="keep_truck", action="store_false",
                       help="Ne conserver que les mouvements USER (par défaut on garde USER + TRUCK)")
    sp_pp.set_defaults(func=cmd_postprocess)

    sp_solve = subparsers.add_parser(
        "solve",
        help="Calcul de la tournée optimale (targeter + solver)")
    sp_solve.add_argument("clean_dir", nargs="?", default="data/clean",
                          help="Dossier des clean_*.sql (défaut: data/clean)")
    sp_solve.add_argument("--snapshot",
                          default=utc_naive_to_local(now_utc_naive()).strftime("%Y-%m-%d %H:%M:%S"),
                          help="Instant cible 'YYYY-MM-DD HH:MM:SS' (heure locale Paris ; "
                               "défaut: instant courant)")
    sp_solve.add_argument("--city", default="nantes",
                          help=f"Préset (ex: 'nantes') ou nom OSMnx complet. "
                               f"Présets connus : {', '.join(CITY_PRESETS)}")
    sp_solve.add_argument("--capacity", type=int, default=30,
                          help="Capacité du camion (défaut: 30)")
    sp_solve.set_defaults(func=cmd_solve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
