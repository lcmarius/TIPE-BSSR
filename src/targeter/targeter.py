# =============================================================================
# Ajustement global des cibles `bike_target` (newsvendor multi-stations)
# =============================================================================
#
# Les cibles isolées b*_i issues de `nb_velo_station.compute_target` ne
# respectent en général ni C1 (Σ (c_i − b_i) = 0, le camion part et revient
# vide) ni C2 (|c_i − b_i| < q/2, un seul transfert tient dans le camion). On
# les ajuste en deux temps : clip dans la boîte autorisée par C2, puis
# rééquilibrage glouton un cran à la fois vers la station de coût marginal le
# plus faible. L'optimum global est garanti par la convexité de f
# (Federgruen-Groenevelt 1986).
#
# Mécanisme de réserve : une visite camion coûte plusieurs minutes alors que
# la pénalité Skellam d'un écart de 1 vélo est minime — et un tel écart est
# typiquement dans le bruit d'estimation des λ (SE ≈ √λ/√n_jours). On évite
# donc ces visites quand C1 peut être bouclé sans elles.
#
# En pratique, les stations dont |b*_i − c_i| ≤ reservoir_threshold sont
# placées en réserve (target = count par défaut). Elles ne sont mobilisées
# dans la fermeture de C1 que si les stations à correction substantielle ne
# suffisent pas — la réserve sert de soupape garantissant C1 globalement.
# =============================================================================

from datetime import datetime

from src.objects.station import Station, TargetedStation
from src.targeter.lambda_predict import predict_lambdas
from src.targeter.nb_velo_station import compute_target


class InfeasibleInstance(Exception):
    """Un seul camion ne peut pas rééquilibrer le réseau dans ce créneau."""

def compute_adjusted_targets(stations: list[Station], bike_counts: dict[int, int],
                              when: datetime, q: int,
                              clean_dir: str = "data/clean",
                              reservoir_threshold: int = 1) -> list[TargetedStation]:
    """Calcule les cibles de vélos à chaque station, en ajustant les cibles optimales isolées pour respecter les contraintes globales du problème."""
    half = q // 2
    valid_stations, current, penalty, low, high = [], [], [], [], []
    for station in stations:
        if station.number == 0 or station.number not in bike_counts:
            continue

        c=bike_counts[station.number]

        valid_stations.append(station)
        current.append(c)
        penalty.append(compute_target(station.capacity, *predict_lambdas(station.number, when, clean_dir)))
        low.append(max(0, c - half + 1))
        high.append(min(station.capacity, c + half - 1))

    # Cible Skellam isolée, clipée par C2
    target_skellam = []
    for s in range(len(valid_stations)):
        b_star = penalty[s].index(min(penalty[s]))
        target_skellam.append(max(low[s], min(high[s], b_star)))

    # Réserve : stations dont la correction isolée est <= seuil (en valeur
    # absolue). Initialisées à target=count (skip), mobilisables uniquement
    # en phase B de la fermeture C1.
    reservoir = {s for s in range(len(valid_stations))
                 if abs(target_skellam[s] - current[s]) <= reservoir_threshold}

    target = [current[s] if s in reservoir else target_skellam[s]
              for s in range(len(valid_stations))]

    total_gap = sum(target) - sum(current)

    while total_gap != 0:
        direction = -1 if total_gap > 0 else +1
        marginal_cost = lambda s: penalty[s][target[s] + direction] - penalty[s][target[s]]

        # Phase A : ajuster d'abord les stations primary (hors réserve)
        primary_candidates = [s for s, b in enumerate(target)
                              if s not in reservoir and low[s] <= b + direction <= high[s]]
        if primary_candidates:
            best_candidat = min(primary_candidates, key=marginal_cost)
        else:
            # Phase B : la réserve s'active. On pioche la station dont
            # l'ajustement vers count±1 est le moins pénalisant — typiquement
            # celle dont la direction de C1 coïncide avec sa préférence
            # Skellam (coût marginal alors négatif).
            reservoir_candidates = [s for s in reservoir
                                    if low[s] <= target[s] + direction <= high[s]]
            if not reservoir_candidates:
                raise InfeasibleInstance(f"déséquilibre δ={total_gap} bloqué par les bornes")
            best_candidat = min(reservoir_candidates, key=marginal_cost)
            reservoir.discard(best_candidat)

        target[best_candidat] += direction
        total_gap += direction

    targeted_stations = []
    for s in range(len(valid_stations)):
        if current[s] != target[s]:
            targeted_stations.append(TargetedStation.from_station(valid_stations[s], current[s], target[s]))

    return targeted_stations
