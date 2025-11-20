import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List

from src.objects.station import TargetedStation, Station
from src.solver.algorithm.method1 import method1
from src.solver.algorithm.method2 import method2

from src.solver.algorithm.opt import opt2, opt3
from src.solver.graph import SolvingStationGraph
from src.solver.reviewer import review_solution, SolutionMetrics
from src.solver.solver import is_graph_solvable


class BenchmarkResult:
    """Résultat d'un benchmark pour un algorithme"""
    def __init__(self, name: str):
        self.name = name
        self.scores: List[float] = []
        self.times: List[float] = []
        self.gaps: List[float] = []  # Écarts relatifs par rapport au meilleur pour chaque problème
        self.failed_seeds: List[int] = []
        self.success_count = 0

    def add_success(self, metrics: SolutionMetrics, time_ms: float):
        """Ajoute un résultat réussi"""
        self.scores.append(metrics.score)
        self.times.append(time_ms)
        self.success_count += 1

    def add_failure(self, seed: int):
        """Ajoute un échec"""
        self.failed_seeds.append(seed)

    def add_gap(self, gap_percent: float):
        """Ajoute un écart relatif"""
        self.gaps.append(gap_percent)

    def avg_score(self) -> float:
        """Score moyen"""
        return sum(self.scores) / len(self.scores) if self.scores else 0.0

    def avg_time(self) -> float:
        """Temps moyen en ms"""
        return sum(self.times) / len(self.times) if self.times else 0.0

    def avg_gap(self) -> float:
        """Écart moyen par rapport au meilleur (en %)"""
        return sum(self.gaps) / len(self.gaps) if self.gaps else 0.0

    def success_rate(self, total_problems: int) -> float:
        """Taux de succès en %"""
        return (self.success_count / total_problems * 100) if total_problems > 0 else 0.0


def run_benchmark(
    algorithms: Dict[str, Callable[[SolvingStationGraph, int], None]],
    generator_func: Callable[[int, int, int], tuple[SolvingStationGraph, Station, list]],
    n_stations: int = 10,
    vehicle_capacity: int = 15,
    num_problems: int = 50,
    base_seed: int = 42,
    verbose: bool = True,
    max_workers: int = None,
) -> Dict[str, BenchmarkResult]:
    """
    Lance un benchmark comparatif des algorithmes avec multithreading

    :param algorithms: Dictionnaire {nom: fonction_algorithme}
    :param n_stations: Nombre de stations par problème
    :param vehicle_capacity: Capacité du véhicule
    :param num_problems: Nombre de problèmes à tester
    :param base_seed: Graine de base pour la reproductibilité
    :param verbose: Afficher la progression
    :param generator_func: Fonction pour générer les instances de problèmes
    :param max_workers: Nombre de threads (None = auto)
    :return: Dictionnaire {nom: BenchmarkResult}
    """
    if verbose:
        print("="*80)
        print("🔬 BENCHMARK - Comparaison des algorithmes (multithreading)")
        print("="*80)
        print(f"\nParamètres:")
        print(f"  - Nombre de problèmes: {num_problems}")
        print(f"  - Stations par problème: {n_stations}")
        print(f"  - Capacité du véhicule: {vehicle_capacity}")
        print(f"  - Algorithmes testés: {list(algorithms.keys())}")
        print(f"  - Threads: {max_workers if max_workers else 'auto'}")
        print()

    seeds = [base_seed + i * 100 for i in range(num_problems)]
    results = {name: BenchmarkResult(name) for name in algorithms}

    def run_algorithm_on_problem(algo_name: str, algo_func: Callable, seed: int):
        """Exécute un algorithme sur un problème donné"""
        try:
            graph, depot, stations = generator_func(n_stations, vehicle_capacity, seed)
            assert is_graph_solvable(graph, vehicle_capacity), "Le graphe généré n'est pas solvable (seed: %s)" % seed

            start_time = time.time()
            algo_func(graph, vehicle_capacity)
            elapsed_time = (time.time() - start_time) * 1000  # en ms

            metrics = review_solution(graph)
            return algo_name, seed, metrics, elapsed_time, None
        except Exception as e:
            return algo_name, seed, None, None, e

    for i, seed in enumerate(seeds):
        if verbose and (i + 1) % 10 == 0:
            print(f"  Problème {i+1}/{num_problems}...")

        problem_results = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(run_algorithm_on_problem, algo_name, algo_func, seed): algo_name
                for algo_name, algo_func in algorithms.items()
            }

            for future in as_completed(futures):
                algo_name, returned_seed, metrics, elapsed_time, error = future.result()

                if error is None:
                    results[algo_name].add_success(metrics, elapsed_time)
                    problem_results[algo_name] = metrics.distance
                else:
                    results[algo_name].add_failure(returned_seed)
                    if verbose:
                        print(f"  ✗ {algo_name} a échoué sur seed {returned_seed}: {error}")

        if problem_results:
            best_distance = min(problem_results.values())
            for algo_name, distance in problem_results.items():
                gap_percent = ((distance - best_distance) / best_distance * 100) if best_distance > 0 else 0.0
                results[algo_name].add_gap(gap_percent)

    return results


def method1_only(graph: SolvingStationGraph, vehicle_capacity: int):
    """method1 seule"""
    s = method1(graph, vehicle_capacity)
    return s

def method1_with_opt2(graph: SolvingStationGraph, vehicle_capacity: int):
    """method1 + 2-opt"""
    s = method1(graph, vehicle_capacity)
    opt2(graph, vehicle_capacity)
    return s

def method1_with_opt2_then_opt3(graph: SolvingStationGraph, vehicle_capacity: int):
    """method1 + 2-opt + 3-opt"""
    s = method1(graph, vehicle_capacity)
    opt2(graph, vehicle_capacity)
    opt3(graph, vehicle_capacity)
    return s
  
def method2_only(graph: SolvingStationGraph, vehicle_capacity: int):
    """method2 seule"""
    s = method2(graph, vehicle_capacity)
    return s

def method2_with_opt2(graph: SolvingStationGraph, vehicle_capacity: int):
    """method2 + 2-opt"""
    s = method2(graph, vehicle_capacity)
    opt2(graph, vehicle_capacity)
    return s

def method2_with_opt2_then_opt3(graph: SolvingStationGraph, vehicle_capacity: int):
    """method2 + 2-opt + 3-opt"""
    s = method2(graph, vehicle_capacity)
    opt2(graph, vehicle_capacity)
    opt3(graph, vehicle_capacity)
    return s

def generate_random_instance(n_stations: int, vehicle_capacity: int, seed: int = None):
    """
    Génère une instance aléatoire uniforme
    :param n_stations: Nombre de stations (sans compter le dépôt)
    :param vehicle_capacity: Capacité du camion
    :param seed: Graine aléatoire pour la reproductibilité
    :return: (graph, depot, stations)
    """
    if seed is not None:
        random.seed(seed)

    depot = Station(0, "Dépôt", 50, "Centre", -1.5536, 47.2173)
    max_gap = vehicle_capacity // 2
    stations = []
    bike_gaps = []

    # Générer n-1 gaps aléatoires
    for i in range(n_stations - 1):
        if i % 2 == 0:
            gap = random.randint(1, max_gap)
        else:
            gap = random.randint(-max_gap, -1)
        bike_gaps.append(gap)

    # Le dernier gap est calculé pour que la somme = 0
    current_sum = sum(bike_gaps)
    last_gap = -current_sum

    # Vérifier que le dernier gap respecte la contrainte |gap| <= max_gap
    if abs(last_gap) > max_gap:
        # Si violation, redistribuer en ajustant les gaps existants
        excess = abs(last_gap) - max_gap
        last_gap = max_gap if last_gap > 0 else -max_gap

        # Distribuer l'excès sur les autres gaps
        for i in range(len(bike_gaps)):
            if bike_gaps[i] > 0 and last_gap < 0:
                # Réduire les gaps positifs si last_gap est négatif
                adjustment = min(excess, bike_gaps[i] - 1)
                bike_gaps[i] -= adjustment
                excess -= adjustment
            elif bike_gaps[i] < 0 and last_gap > 0:
                # Augmenter les gaps négatifs (les rendre moins négatifs) si last_gap est positif
                adjustment = min(excess, abs(bike_gaps[i]) - 1)
                bike_gaps[i] += adjustment
                excess -= adjustment

            if excess == 0:
                break

    bike_gaps.append(last_gap)

    for i in range(n_stations):
        long = depot.long + random.uniform(-0.05, 0.05)
        lat = depot.lat + random.uniform(-0.05, 0.05)

        capacity = random.randint(15, 30)
        bike_target = random.randint(5, capacity - 5)
        bike_count = bike_target + bike_gaps[i]

        station = TargetedStation(
            i + 1,
            f"Station {chr(65 + i)}" if i < 26 else f"Station {i + 1}",
            capacity,
            f"{i + 1} Rue {chr(65 + i)}" if i < 26 else f"{i + 1} Rue {i + 1}",
            long, lat, bike_count, bike_target
        )
        stations.append(station)

    graph = SolvingStationGraph(depot)
    for station in stations:
        graph.add_station(station)

    return graph, depot, stations


def generate_clustered_instance(n_stations: int, vehicle_capacity: int, seed: int = None):
    """
    Génère une instance avec stations groupées en clusters
    :return: (graph, depot, stations)
    """
    if seed is not None:
        random.seed(seed)

    depot = Station(0, "Dépôt", 50, "Centre", -1.5536, 47.2173)
    max_gap = vehicle_capacity // 2

    # Créer 3 clusters autour du dépôt
    num_clusters = 3
    cluster_centers = [
        (depot.long + 0.03, depot.lat + 0.03),   # Nord-Est
        (depot.long - 0.03, depot.lat + 0.02),   # Nord-Ouest
        (depot.long, depot.lat - 0.03),          # Sud
    ]

    stations = []
    bike_gaps = []

    # Générer n-1 gaps aléatoires
    for i in range(n_stations - 1):
        gap = random.randint(1, max_gap) if i % 2 == 0 else random.randint(-max_gap, -1)
        bike_gaps.append(gap)

    # Le dernier gap est calculé pour que la somme = 0
    current_sum = sum(bike_gaps)
    last_gap = -current_sum

    # Vérifier que le dernier gap respecte la contrainte |gap| <= max_gap
    if abs(last_gap) > max_gap:
        excess = abs(last_gap) - max_gap
        last_gap = max_gap if last_gap > 0 else -max_gap

        for i in range(len(bike_gaps)):
            if bike_gaps[i] > 0 and last_gap < 0:
                adjustment = min(excess, bike_gaps[i] - 1)
                bike_gaps[i] -= adjustment
                excess -= adjustment
            elif bike_gaps[i] < 0 and last_gap > 0:
                adjustment = min(excess, abs(bike_gaps[i]) - 1)
                bike_gaps[i] += adjustment
                excess -= adjustment

            if excess == 0:
                break

    bike_gaps.append(last_gap)

    for i in range(n_stations):
        # Assigner à un cluster
        cluster_idx = i % num_clusters
        center_long, center_lat = cluster_centers[cluster_idx]

        # Position proche du centre du cluster
        long = center_long + random.uniform(-0.01, 0.01)
        lat = center_lat + random.uniform(-0.01, 0.01)

        capacity = random.randint(15, 30)
        bike_target = random.randint(5, capacity - 5)
        bike_count = bike_target + bike_gaps[i]

        station = TargetedStation(
            i + 1,
            f"Station {chr(65 + i)}" if i < 26 else f"Station {i + 1}",
            capacity,
            f"{i + 1} Rue {chr(65 + i)}" if i < 26 else f"{i + 1} Rue {i + 1}",
            long, lat, bike_count, bike_target
        )
        stations.append(station)

    graph = SolvingStationGraph(depot)
    for station in stations:
        graph.add_station(station)

    return graph, depot, stations


def generate_hub_spoke_instance(n_stations: int, vehicle_capacity: int, seed: int = None):
    """
    Génère une instance hub-and-spoke (étoile autour du dépôt)
    :return: (graph, depot, stations)
    """
    if seed is not None:
        random.seed(seed)

    depot = Station(0, "Dépôt", 50, "Centre", -1.5536, 47.2173)
    max_gap = vehicle_capacity // 2

    stations = []
    bike_gaps = []

    # Générer n-1 gaps aléatoires
    for i in range(n_stations - 1):
        gap = random.randint(1, max_gap) if i % 2 == 0 else random.randint(-max_gap, -1)
        bike_gaps.append(gap)

    # Le dernier gap est calculé pour que la somme = 0
    current_sum = sum(bike_gaps)
    last_gap = -current_sum

    # Vérifier que le dernier gap respecte la contrainte |gap| <= max_gap
    if abs(last_gap) > max_gap:
        excess = abs(last_gap) - max_gap
        last_gap = max_gap if last_gap > 0 else -max_gap

        for i in range(len(bike_gaps)):
            if bike_gaps[i] > 0 and last_gap < 0:
                adjustment = min(excess, bike_gaps[i] - 1)
                bike_gaps[i] -= adjustment
                excess -= adjustment
            elif bike_gaps[i] < 0 and last_gap > 0:
                adjustment = min(excess, abs(bike_gaps[i]) - 1)
                bike_gaps[i] += adjustment
                excess -= adjustment

            if excess == 0:
                break

    bike_gaps.append(last_gap)

    for i in range(n_stations):
        # 70% des stations proches du dépôt, 30% éloignées
        if random.random() < 0.7:
            # Proche du dépôt
            long = depot.long + random.uniform(-0.02, 0.02)
            lat = depot.lat + random.uniform(-0.02, 0.02)
        else:
            # Éloignée (outliers)
            long = depot.long + random.uniform(-0.06, 0.06)
            lat = depot.lat + random.uniform(-0.06, 0.06)

        capacity = random.randint(15, 30)
        bike_target = random.randint(5, capacity - 5)
        bike_count = bike_target + bike_gaps[i]

        station = TargetedStation(
            i + 1,
            f"Station {chr(65 + i)}" if i < 26 else f"Station {i + 1}",
            capacity,
            f"{i + 1} Rue {chr(65 + i)}" if i < 26 else f"{i + 1} Rue {i + 1}",
            long, lat, bike_count, bike_target
        )
        stations.append(station)

    graph = SolvingStationGraph(depot)
    for station in stations:
        graph.add_station(station)

    return graph, depot, stations


def generate_tight_capacity_instance(n_stations: int, vehicle_capacity: int, seed: int = None):
    """
    Génère une instance avec des gaps proches de la limite de capacité
    :return: (graph, depot, stations)
    """
    if seed is not None:
        random.seed(seed)

    depot = Station(0, "Dépôt", 50, "Centre", -1.5536, 47.2173)
    max_gap = vehicle_capacity // 2

    stations = []
    bike_gaps = []

    # Créer des gaps proches de la limite (80-100% de max_gap)
    for i in range(n_stations - 1):
        if i % 2 == 0:
            gap = random.randint(int(max_gap * 0.8), max_gap)
        else:
            gap = random.randint(-max_gap, int(-max_gap * 0.8))
        bike_gaps.append(gap)

    # Le dernier gap est calculé pour que la somme = 0
    current_sum = sum(bike_gaps)
    last_gap = -current_sum

    # Vérifier que le dernier gap respecte la contrainte |gap| <= max_gap
    if abs(last_gap) > max_gap:
        excess = abs(last_gap) - max_gap
        last_gap = max_gap if last_gap > 0 else -max_gap

        for i in range(len(bike_gaps)):
            if bike_gaps[i] > 0 and last_gap < 0:
                adjustment = min(excess, bike_gaps[i] - 1)
                bike_gaps[i] -= adjustment
                excess -= adjustment
            elif bike_gaps[i] < 0 and last_gap > 0:
                adjustment = min(excess, abs(bike_gaps[i]) - 1)
                bike_gaps[i] += adjustment
                excess -= adjustment

            if excess == 0:
                break

    bike_gaps.append(last_gap)

    for i in range(n_stations):
        long = depot.long + random.uniform(-0.05, 0.05)
        lat = depot.lat + random.uniform(-0.05, 0.05)

        capacity = random.randint(15, 30)
        bike_target = random.randint(5, capacity - 5)
        bike_count = bike_target + bike_gaps[i]

        station = TargetedStation(
            i + 1,
            f"Station {chr(65 + i)}" if i < 26 else f"Station {i + 1}",
            capacity,
            f"{i + 1} Rue {chr(65 + i)}" if i < 26 else f"{i + 1} Rue {i + 1}",
            long, lat, bike_count, bike_target
        )
        stations.append(station)

    graph = SolvingStationGraph(depot)
    for station in stations:
        graph.add_station(station)

    return graph, depot, stations

def print_category_results(category_name: str, results: Dict[str, BenchmarkResult], num_problems: int):
    """Affiche les résultats d'une catégorie"""
    print("\n" + "=" * 110)
    print(f"📊 CATÉGORIE: {category_name}")
    print("=" * 110)

    print(f"\n{'Algorithme':<25} {'Gap vs Best (%)':<16} {'Score':<8} {'Temps (ms)':<12} {'Succès'}")
    print("-" * 110)

    sorted_results = sorted(results.items(), key=lambda x: x[1].avg_gap() if x[1].success_count > 0 else float('inf'))

    for name, result in sorted_results:
        if result.success_count > 0:
            print(f"{name:<25} {result.avg_gap():<16.2f}"
                  f"{result.avg_score():<8.4f} {result.avg_time():<12.2f} "
                  f"{result.success_count}/{num_problems} ({result.success_rate(num_problems):.1f}%)")
        else:
            print(f"{name:<25} {'N/A':<16} {'N/A':<15} {'N/A':<8} {'N/A':<12} "
                  f"0/{num_problems} (0.0%)")

    best_algo = sorted_results[0] if sorted_results and sorted_results[0][1].success_count > 0 else None
    if best_algo:
        print(f"\n  🏆 Meilleur: {best_algo[0]} (gap moyen: {best_algo[1].avg_gap():.2f}%)")


def print_global_summary(all_results: Dict[str, Dict[str, BenchmarkResult]]):
    """Affiche le bilan global sur toutes les catégories"""
    print("\n" + "=" * 110)
    print("🏆 BILAN GLOBAL (moyenne sur toutes les catégories)")
    print("=" * 110)

    algo_names = list(next(iter(all_results.values())).keys())
    global_stats = {}

    for algo_name in algo_names:
        total_gap = 0.0
        total_score = 0.0
        total_time = 0.0
        count = 0

        for category_results in all_results.values():
            result = category_results[algo_name]
            if result.success_count > 0:
                total_gap += result.avg_gap()
                total_score += result.avg_score()
                total_time += result.avg_time()
                count += 1

        if count > 0:
            global_stats[algo_name] = {
                'avg_gap': total_gap / count,
                'avg_score': total_score / count,
                'avg_time': total_time / count,
                'count': count
            }

    print(f"\n{'Algorithme':<30} {'Gap vs Best (%)':<16} {'Score':<10} {'Temps (ms)':<12}")
    print("-" * 110)

    for algo_name, stats in sorted(global_stats.items(), key=lambda x: x[1]['avg_gap']):
        print(f"{algo_name:<30} {stats['avg_gap']:<16.2f} {stats['avg_score']:<10.4f} {stats['avg_time']:<12.2f}")

    best_algo = min(global_stats.items(), key=lambda x: x[1]['avg_gap'])
    print("\n" + "=" * 110)
    print(f"🏆 CHAMPION GLOBAL: {best_algo[0]}")
    print(f"   Gap moyen: {best_algo[1]['avg_gap']:.2f}%")
    print(f"   Score moyen: {best_algo[1]['avg_score']:.4f}")
    print("=" * 110)


def run_benchmarks():
    """Lance les benchmarks sur plusieurs catégories en parallèle et affiche les résultats"""
    algorithms = {
        "method1": method1_only,
        "method1 + 2-opt": method1_with_opt2,
        "method1 + 2-opt + 3-opt": method1_with_opt2_then_opt3,
        "method2": method2_only,
        "method2 + 2-opt": method2_with_opt2,
        "method2 + 2-opt + 3-opt": method2_with_opt2_then_opt3
    }

    categories = {
        "Random Uniform": generate_random_instance,
        "Clustered": generate_clustered_instance,
        "Hub-and-Spoke": generate_hub_spoke_instance,
        "Tight Capacity": generate_tight_capacity_instance,
    }

    n_stations = 20
    vehicle_capacity = 12
    num_problems = 5
    base_seed = 9783

    print("\n" + "=" * 100)
    print("🚀 Lancement des benchmarks en parallèle...")
    print("=" * 100)

    def run_category_benchmark(category_name: str, generator_func: Callable):
        """Exécute le benchmark pour une catégorie"""
        print(f"🔄 Running benchmark: {category_name}...")
        return category_name, run_benchmark(
            algorithms=algorithms,
            generator_func=generator_func,
            n_stations=n_stations,
            vehicle_capacity=vehicle_capacity,
            num_problems=num_problems,
            base_seed=base_seed,
            verbose=True,
            max_workers=4
        )

    all_results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:  # 4 catégories en parallèle
        futures = {
            executor.submit(run_category_benchmark, category_name, generator_func): category_name
            for category_name, generator_func in categories.items()
        }

        for future in as_completed(futures):
            category_name, results = future.result()
            all_results[category_name] = results

    for category_name in categories.keys():
        if category_name in all_results:
            print_category_results(category_name, all_results[category_name], num_problems)

    print_global_summary(all_results)


def afficher():
    vc=15
    n=107
    s=8276
    graph, depot, stations = generate_random_instance(n, vc, s)
    graph2, depot2, stations2 = generate_random_instance(n, vc, s)
    graph3, depot3, stations3 = generate_random_instance(n, vc, s)
    graph4, depot4, stations4 = generate_random_instance(n, vc, s)
    method1_only(graph, vc)
    method1_with_opt2_then_opt3(graph2, vc)
    method2(graph3, vc)
    method2_with_opt2_then_opt3(graph4, vc)
    graph.render("output_method1.png", "Méthode 1 seule")
    graph2.render("output_method1_opt2_opt3.png", "Méthode 1 + 2-opt + 3-opt")
    graph3.render("output_method2.png", "Méthode 2 seule")
    graph4.render("output_method2_opt2_opt3.png", "Méthode 2 + 2-opt + 3-opt")

    print("methode1", review_solution(graph))
    print("methode1opted", review_solution(graph2))
    print("methode2", review_solution(graph3))
    print("methode2opted", review_solution(graph4))
    

if __name__ == "__main__":
    afficher()
