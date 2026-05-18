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
# =============================================================================

from datetime import datetime

from src.objects.station import Station, TargetedStation
from src.targeter.lambda_predict import predict_lambdas
from src.targeter.nb_velo_station import compute_target


class InfeasibleInstance(Exception):
    """Un seul camion ne peut pas rééquilibrer le réseau dans ce créneau."""

def compute_adjusted_targets(stations: list[Station], bike_counts: dict[int, int],
                              when: datetime, q: int) -> list[TargetedStation]:
    """Calcule les cibles de vélos à chaque station, en ajustant les cibles optimales isolées pour respecter les contraintes globales du problème."""
    half = q // 2
    valid_stations, current, penalty, low, high = [], [], [], [], []
    for station in stations:
        if station.number == 0 or station.number not in bike_counts:
            continue

        c=bike_counts[station.number]

        valid_stations.append(station)
        current.append(c)
        penalty.append(compute_target(station.capacity, *predict_lambdas(station.number, when)))
        low.append(max(0, c - half + 1))
        high.append(min(station.capacity, c + half - 1))

    target = []
    for s in range(len(valid_stations)):
        b_star = penalty[s].index(min(penalty[s]))
        target.append(max(low[s], min(high[s], b_star)))

    total_gap = sum(target) - sum(current)

    while total_gap != 0:
        direction = -1 if total_gap > 0 else +1
        candidates = [s for s, b in enumerate(target) if low[s] <= b + direction <= high[s]]
        if not candidates:
            raise InfeasibleInstance(f"déséquilibre δ={total_gap} bloqué par les bornes")

        # On prend le candidat dont le changement de target est le moins pénalisant (coût marginal le plus faible)
        marginal_cost = lambda s: penalty[s][target[s] + direction] - penalty[s][target[s]]
        best_candidat = min(candidates, key=marginal_cost)

        target[best_candidat] += direction
        total_gap += direction

    return [TargetedStation.from_station(valid_stations[i], current[i], target[i]) for i in range(len(valid_stations))]

