"""renders/simulate_modal.py
Simulation multi-jours stratifiée sur Modal.com.

Architecture : UN seul conteneur (32 vCPU, 64 Go RAM), multiprocessing
interne pour paralléliser les ~90 jours sur 32 workers. Les résultats
sont écrits sur un Modal Volume → survivent à une déconnexion du
terminal local, et restent récupérables avec --fetch.

Politique camion : boucle 06:00 → 20:00, repos 30 min entre tournées.

Setup (une fois) :
    pip install modal
    modal token new

Lancement (mode détaché, ~45-60 min) :
    modal run --detach renders/simulate_modal.py

Si le terminal lâche en cours de route, récupération propre :
    modal run renders/simulate_modal.py --fetch

Itération rapide sur le rendu (depuis pickle local, pas de Modal) :
    python -m renders.simulate_modal --from-local-cache

Sortie : renders/simulate/simulate_multiday.png  (2×2 panneaux, médiane
+ bande IQR par strate jour/saison) et pickle local pour ré-itération.
"""

import argparse
import glob
import os
import pickle
from collections import defaultdict
from datetime import date, datetime
from enum import Enum

import modal


APP_NAME    = "bicloo-multi-day"
VOLUME_NAME = "bicloo-multi-day-results"
CACHE_LOCAL = "renders/simulate/multi_day_results.pkl"
RENDER_OUT  = "renders/simulate/simulate_multiday.png"

# Politique camion (override des défauts de simulate.py).
TRUCK_START    = "06:00"
TRUCK_END      = "20:00"
TRUCK_REST_MIN = 30
TRUCK_CAPACITY = 30
N_WORKERS      = 32

app = modal.App(APP_NAME)
results_volume = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

# Image : on n'inclut que les sources Python (`add_local_python_source`,
# qui ne surveille pas tout le répertoire) + les données nécessaires
# (clean SQL + graphml + time_matrix). `add_local_dir` sur renders/ posait
# problème car PyCharm / autres process touchent ponctuellement les .py
# pendant le build → Modal refuse.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements("requirements.txt")
    .add_local_python_source("src", "renders.simulate", "renders.simulate_modal",
                              copy=True)
    .add_local_dir("data", "/app/data", copy=True, ignore=["source/**"])
    .workdir("/app")
)


# ────────────────────────────────────────────────────────────────────────────
# Stratification (autonome : pas d'import du module simulate pour la phase
# locale de rendu, qui doit pouvoir tourner sans la chaîne OSMnx/scipy).
# ────────────────────────────────────────────────────────────────────────────

SPLIT_DATE = date(2026, 3, 20)


class DayType(Enum):
    WD = "Jours de semaine"
    WE = "Week-end"


class Season(Enum):
    COLD = "hiver"
    WARM = "printemps"


def _day_type(d: date) -> DayType:
    return DayType.WE if d.weekday() >= 5 else DayType.WD


def _season(d: date) -> Season:
    return Season.WARM if d >= SPLIT_DATE else Season.COLD


def _stratum_label(stratum: tuple[DayType, Season]) -> str:
    dt, ss = stratum
    return f"{dt.value} — {ss.value}"


# ────────────────────────────────────────────────────────────────────────────
# Worker — exécuté dans le conteneur Modal, en parallèle par multiprocessing.
# Fonction module-level pour être picklable par `Pool.map`.
# ────────────────────────────────────────────────────────────────────────────

def _safe_simulate(date_str: str) -> dict:
    """Simule une journée, isole erreurs + silence stdout pour ne pas
    écraser les logs des autres workers."""
    import contextlib
    import io
    import sys
    import traceback
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")
    try:
        from renders.simulate import simulate_for_date
        with contextlib.redirect_stdout(io.StringIO()):
            baseline, optimized = simulate_for_date(
                date_str,
                start_hhmm = TRUCK_START,
                end_hhmm   = TRUCK_END,
                rest_min   = TRUCK_REST_MIN,
                capacity   = TRUCK_CAPACITY,
                verbose    = False,
            )
        return {"date": date_str, "ok": True,
                "baseline": baseline, "optimized": optimized}
    except Exception as e:
        return {"date": date_str, "ok": False,
                "error": f"{e!r}\n{traceback.format_exc()}"}


@app.function(
    image    = image,
    cpu      = N_WORKERS,
    memory   = 65536,
    timeout  = 14400,
    volumes  = {"/results": results_volume},
)
def run_all_days(dates: list[str]) -> list[dict]:
    """Lance toutes les simulations sur 1 conteneur, parallélisme interne.

    Pré-calcule la matrice de temps une seule fois côté parent (sinon les
    16-32 workers s'écraseraient dessus en parallèle au premier démarrage),
    puis fork pour le Pool.

    Sauve sur Modal Volume avant retour : si le terminal local meurt, les
    résultats sont récupérables via `fetch_latest_results`.
    """
    import os
    import sys
    from multiprocessing import Pool, cpu_count

    os.chdir("/app")
    if "/app" not in sys.path:
        sys.path.insert(0, "/app")

    print(f"[{datetime.now():%H:%M:%S}] Pré-calcul matrice de temps (parent)...")
    from renders.simulate import (
        _load_day, _synthetic_depot, _warm_node_cache,
        _restrict_to_largest_scc, _load_or_build_time_matrix,
        GRAPHML_PATH, OSM_CITY,
    )
    from src.solver.map import Map
    sample_db = f"/app/data/clean/clean_{dates[0]}.sql"
    stations, _, _ = _load_day(sample_db)
    depot = _synthetic_depot(stations)
    road_map = Map(GRAPHML_PATH, city=OSM_CITY)
    _restrict_to_largest_scc(road_map)
    _warm_node_cache(road_map, [depot, *stations])
    _load_or_build_time_matrix(road_map, stations, depot, rebuild=False)
    print(f"[{datetime.now():%H:%M:%S}] Matrice prête.")

    nw = min(N_WORKERS, cpu_count())
    print(f"[{datetime.now():%H:%M:%S}] Pool {nw} workers (CPU dispo: {cpu_count()})")
    print(f"[{datetime.now():%H:%M:%S}] {len(dates)} jours à simuler, camion "
          f"{TRUCK_START}→{TRUCK_END} (repos {TRUCK_REST_MIN} min)")

    with Pool(nw) as pool:
        results = pool.map(_safe_simulate, dates)

    n_ok = sum(1 for r in results if r["ok"])
    print(f"[{datetime.now():%H:%M:%S}] {n_ok}/{len(results)} OK")

    # ─ Persiste sur Modal Volume (clé : survie à crash terminal local).
    stamp     = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_stamp = f"/results/multi_day_results_{stamp}.pkl"
    out_latest = "/results/multi_day_results_latest.pkl"
    with open(out_stamp, "wb") as f:
        pickle.dump(results, f)
    with open(out_latest, "wb") as f:
        pickle.dump(results, f)
    results_volume.commit()
    print(f"[{datetime.now():%H:%M:%S}] Volume écrit : {out_stamp} + latest")
    return results


@app.function(image=image, volumes={"/results": results_volume})
def fetch_latest_results() -> list[dict]:
    """Récupère la dernière sauvegarde depuis le Modal Volume.

    Utilisé après une déconnexion : la simulation a tourné en mode --detach,
    a écrit ses résultats sur Volume, et on les rapatrie ici.
    """
    import pickle
    with open("/results/multi_day_results_latest.pkl", "rb") as f:
        return pickle.load(f)


# ────────────────────────────────────────────────────────────────────────────
# Rendu — s'exécute localement, après réception des résultats.
# ────────────────────────────────────────────────────────────────────────────

def render_stratified(results: list[dict], out_path: str) -> str:
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import numpy as np

    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    by_stratum: dict[tuple[DayType, Season], list[dict]] = defaultdict(list)
    n_failed = 0
    for r in results:
        if not r["ok"]:
            n_failed += 1
            print(f"  [skip] {r['date']} : {r['error'].splitlines()[0]}")
            continue
        d = date.fromisoformat(r["date"])
        by_stratum[(_day_type(d), _season(d))].append(r)

    strata_order = [
        (DayType.WD, Season.COLD), (DayType.WE, Season.COLD),
        (DayType.WD, Season.WARM), (DayType.WE, Season.WARM),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10), sharex=True, sharey=True)
    fig.patch.set_facecolor("white")

    for ax, stratum in zip(axes.flat, strata_order):
        rs = by_stratum.get(stratum, [])
        ax.set_facecolor("#fafafa")
        ax.grid(True, alpha=0.3)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)

        if not rs:
            ax.text(0.5, 0.5,
                    f"{_stratum_label(stratum)}\n(0 jours dans la strate)",
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=12, color="#888", style="italic")
            continue

        # Tous les jours ont la même grille d'échantillonnage (1441 pts à
        # 1 min depuis 00:00). On convertit chaque datetime en "heures
        # écoulées depuis minuit" (float) pour que toutes les strates
        # partagent un axe x homogène — sans ça, les datetimes éparpillés
        # sur 3 mois écraseraient toutes les courbes en un sliver.
        base_arr = np.array([r["baseline"].rupture_min_cum  for r in rs])
        opt_arr  = np.array([r["optimized"].rupture_min_cum for r in rs])
        ref_times = rs[0]["baseline"].times
        t0 = ref_times[0]
        x = np.array([(t - t0).total_seconds() / 3600.0 for t in ref_times])

        # Moyenne ± SEM (écart-type / √N) — la bande montre la **précision
        # sur la moyenne**, pas la dispersion individuelle des jours.
        # Avec N=10, on connaît la moyenne ~3× mieux que la variabilité
        # jour-à-jour. C'est la quantité pertinente pour valider une
        # méthode sur ce sous-échantillon.
        sqrtN = max(1.0, np.sqrt(len(rs)))
        base_mean = base_arr.mean(axis=0)
        opt_mean  = opt_arr.mean(axis=0)
        base_sem  = (base_arr.std(axis=0, ddof=1) / sqrtN
                     if len(rs) > 1 else np.zeros_like(base_mean))
        opt_sem   = (opt_arr.std(axis=0, ddof=1) / sqrtN
                     if len(rs) > 1 else np.zeros_like(opt_mean))

        ax.fill_between(x, base_mean - base_sem, base_mean + base_sem,
                        color="#6c7a89", alpha=0.22)
        ax.plot(x, base_mean, color="#6c7a89", ls="--", lw=2,
                label="Réalité (moyenne ± SEM)")
        ax.fill_between(x, opt_mean - opt_sem, opt_mean + opt_sem,
                        color="#2d5a9e", alpha=0.24)
        ax.plot(x, opt_mean, color="#2d5a9e", ls="-", lw=2.5,
                label="+ 1 camion (moyenne ± SEM)")

        # Gain par jour : moyenne, et SEM de la moyenne (= σ/√N).
        per_day_gain = np.array([
            (b - o) / b * 100 if b > 0 else 0.0
            for b, o in zip(base_arr[:, -1], opt_arr[:, -1])
        ])
        g_mean = per_day_gain.mean()
        g_sem  = (per_day_gain.std(ddof=1) / sqrtN
                  if len(per_day_gain) > 1 else 0.0)
        n_bad  = int((per_day_gain < 0).sum())
        # Convention : gain positif = rupture diminuée (bénéfique).
        # On signe explicitement Δrupture (négatif = bon).
        delta = -g_mean
        sign = "−" if delta <= 0 else "+"
        bad_note = f"  ·  {n_bad}/{len(rs)} dégradés" if n_bad > 0 else ""
        ax.set_title(f"{_stratum_label(stratum)}  ·  {len(rs)} j  ·  "
                     f"Δrupture = {sign}{abs(delta):.1f}% ± {g_sem:.1f}%"
                     f"{bad_note}",
                     fontsize=10.5, fontweight="bold", pad=8)
        ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
        ax.set_xlim(0, 24)
        ax.set_xticks(range(0, 25, 4))
        ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 25, 4)])

    for ax in axes[1]:
        ax.set_xlabel("Heure", fontsize=11)
    for ax in axes[:, 0]:
        ax.set_ylabel("Rupture cumulée (min)", fontsize=11)

    n_ok = sum(len(v) for v in by_stratum.values())
    fig.suptitle(f"Valeur marginale d'1 camion supplémentaire (boucle "
                 f"{TRUCK_START}→{TRUCK_END}, repos {TRUCK_REST_MIN} min)\n"
                 f"Bicloo Nantes sur {n_ok} jours  ·  bande = SEM (σ/√N)"
                 + (f"  ({n_failed} échecs)" if n_failed else ""),
                 fontsize=13, fontweight="bold", y=1.005)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _print_summary(results: list[dict]) -> None:
    """Récap chiffré par strate (moyenne ± SEM sur les jours)."""
    import math
    import statistics
    by_stratum: dict[tuple[DayType, Season], list[dict]] = defaultdict(list)
    for r in results:
        if r["ok"]:
            d = date.fromisoformat(r["date"])
            by_stratum[(_day_type(d), _season(d))].append(r)
    print()
    print(f"  {'Strate':<35}  {'N':>3}  {'Baseline (méd.)':>15}  "
          f"{'Optimisé (méd.)':>15}  {'Δrupture moy. ± SEM':>21}  {'dégr.':>7}")
    print(f"  {'─' * 35}  {'─' * 3}  {'─' * 15}  {'─' * 15}  "
          f"{'─' * 21}  {'─' * 7}")
    for stratum in [(DayType.WD, Season.COLD), (DayType.WE, Season.COLD),
                    (DayType.WD, Season.WARM), (DayType.WE, Season.WARM)]:
        rs = by_stratum.get(stratum, [])
        if not rs:
            continue
        base = [r["baseline"].total_rupture_min  for r in rs]
        opt  = [r["optimized"].total_rupture_min for r in rs]
        per_day_gain = [(b - o) / b * 100 if b > 0 else 0
                        for b, o in zip(base, opt)]
        bm = statistics.median(base)
        om = statistics.median(opt)
        gm = statistics.fmean(per_day_gain)
        gsd = statistics.stdev(per_day_gain) if len(per_day_gain) > 1 else 0.0
        gsem = gsd / math.sqrt(len(per_day_gain))
        n_bad = sum(1 for g in per_day_gain if g < 0)
        # Convention : Δrupture < 0 = bon (rupture réduite)
        delta = -gm
        print(f"  {_stratum_label(stratum):<35}  {len(rs):>3}  "
              f"{bm:>11.0f} min  {om:>11.0f} min  "
              f"{delta:>+10.1f}% ± {gsem:>4.1f}%  {n_bad:>3d}/{len(rs):<3d}")


def _save_local_cache(results: list[dict]) -> None:
    os.makedirs(os.path.dirname(CACHE_LOCAL), exist_ok=True)
    # Le pickle peut contenir des SimulationResult dataclasses du module
    # `renders.simulate`. À la lecture depuis un autre context (e.g. via
    # `python -m`), le module peut être chargé comme `__main__`. On laisse
    # pickle standard ici car le rendu local fonctionne dans la même
    # process que la lecture.
    with open(CACHE_LOCAL, "wb") as f:
        pickle.dump(results, f)


def _load_local_cache() -> list[dict]:
    # Pour la même raison que ci-dessus on tolère __main__ -> renders.simulate.
    class _Unp(pickle.Unpickler):
        def find_class(self, module, name):
            if module == "__main__":
                module = "renders.simulate"
            return super().find_class(module, name)
    with open(CACHE_LOCAL, "rb") as f:
        return _Unp(f).load()


# ────────────────────────────────────────────────────────────────────────────
# Entrypoint local (Modal)
# ────────────────────────────────────────────────────────────────────────────

@app.local_entrypoint()
def main(fetch: bool = False, from_local_cache: bool = False):
    """
    Trois modes :
      (défaut)             → lance la simulation complète sur Modal
      --fetch              → récupère le dernier résultat depuis Modal Volume
                              (à utiliser après reconnexion d'un --detach)
      --from-local-cache   → re-rend seulement depuis le pickle local
    """
    if from_local_cache:
        if not os.path.exists(CACHE_LOCAL):
            raise SystemExit(f"Cache local introuvable : {CACHE_LOCAL}")
        print(f"Chargement cache local : {CACHE_LOCAL}")
        results = _load_local_cache()
    elif fetch:
        print("Récupération du dernier résultat depuis Modal Volume...")
        results = fetch_latest_results.remote()
        _save_local_cache(results)
        print(f"Cache local écrit : {CACHE_LOCAL}")
    else:
        dates = sorted([os.path.basename(f)[len("clean_"):-len(".sql")]
                        for f in glob.glob("data/clean/clean_*.sql")])
        print(f"Lancement de {len(dates)} simulations sur Modal "
              f"(camion {TRUCK_START}→{TRUCK_END}, repos {TRUCK_REST_MIN} min)...")
        results = run_all_days.remote(dates)
        _save_local_cache(results)
        print(f"Cache local écrit : {CACHE_LOCAL}")

    print("Rendu...")
    out = render_stratified(results, RENDER_OUT)
    print(f"OK — {out}")
    _print_summary(results)


# ────────────────────────────────────────────────────────────────────────────
# Standalone CLI — permet `python -m renders.simulate_modal --from-local-cache`
# (ré-itération sur le rendu sans dépendance Modal)
# ────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--from-local-cache", action="store_true",
                   help="Rejoue uniquement le rendu depuis renders/simulate/"
                        "multi_day_results.pkl, sans appel à Modal.")
    args = p.parse_args()
    if not args.from_local_cache:
        raise SystemExit(
            "Pour lancer une simulation, utiliser :\n"
            "    modal run --detach renders/simulate_modal.py\n"
            "Pour récupérer après déconnexion :\n"
            "    modal run renders/simulate_modal.py --fetch\n"
            "Pour rejouer uniquement le rendu depuis le pickle local :\n"
            "    python -m renders.simulate_modal --from-local-cache")
    if not os.path.exists(CACHE_LOCAL):
        raise SystemExit(f"Cache local introuvable : {CACHE_LOCAL}")
    print(f"Chargement cache local : {CACHE_LOCAL}")
    results = _load_local_cache()
    print("Rendu...")
    out = render_stratified(results, RENDER_OUT)
    print(f"OK — {out}")
    _print_summary(results)
