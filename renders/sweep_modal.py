"""Sweep BSSR parallélisé sur Modal (container 32 CPUs).

Lance les runs (n_values × instances × 10 configs) en parallèle via
ProcessPoolExecutor dans un container Modal, agrège mean/stdev/sem, puis
sauve le résultat en JSON local pour rendu via `render_sweep.py --from-cache`.

Usage :
    .venv/bin/modal run renders/sweep_modal.py
    .venv/bin/modal run renders/sweep_modal.py --instances 100
"""

import json
from pathlib import Path

import modal

REMOTE_ROOT = "/root/bssr"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy", "scipy", "networkx", "osmnx", "matplotlib")
    .add_local_dir(
        ".", remote_path=REMOTE_ROOT,
        ignore=[
            "**/.venv/**", "**/.git/**", "data/**", "mds/**",
            "renders/*.png", "renders/sweep_data.json",
            "renders/sweep/**", "**/__pycache__/**",
            "*.gif", "*.pdf",
        ],
    )
)

app = modal.App("bssr-sweep", image=image)


@app.function(cpu=32.0, memory=16384, timeout=3600)
def run_full_sweep(n_values: list[int], instances: int, capacity: int,
                   truck: int, seed: int, ils_max_iter: int,
                   instance_offset: int = 0) -> dict:
    """Calcule `instances` instances par valeur de n, à partir de l'index
    `instance_offset` (utilisé pour ne pas refaire ce qui est déjà en cache).
    Les seeds suivent `seed + i + 1000*n` avec `i ∈ [offset, offset+instances)`.
    """
    import os, statistics, sys, time
    sys.path.insert(0, REMOTE_ROOT)
    os.chdir(REMOTE_ROOT)

    from concurrent.futures import ProcessPoolExecutor, as_completed
    from renders.sweep_worker import run_one

    jobs = [
        (n, capacity, truck, seed + i + 1000 * n, ils_max_iter)
        for n in n_values
        for i in range(instance_offset, instance_offset + instances)
    ]

    n_workers = os.cpu_count() or 16
    print(f"Lancement de {len(jobs)} jobs sur {n_workers} cores")
    t0 = time.time()

    config_names: list[str] | None = None
    results_by_n: dict[int, dict[str, list[float]]] = {}

    with ProcessPoolExecutor(max_workers=n_workers) as ex:
        futures = [ex.submit(run_one, j) for j in jobs]
        done = 0
        for fut in as_completed(futures):
            n, ratios = fut.result()
            if config_names is None:
                config_names = list(ratios.keys())
                for nn in n_values:
                    results_by_n[nn] = {name: [] for name in config_names}
            for name, r in ratios.items():
                if r is not None:
                    results_by_n[n][name].append(r)
            done += 1
            if done % 100 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}  ({time.time()-t0:.1f}s)")

    assert config_names is not None
    mean_ratios:  dict[str, list[float | None]] = {n: [] for n in config_names}
    stdev_ratios: dict[str, list[float]]        = {n: [] for n in config_names}
    sem_ratios:   dict[str, list[float]]        = {n: [] for n in config_names}
    n_success:    dict[str, list[int]]          = {n: [] for n in config_names}

    for n in n_values:
        for name in config_names:
            rs = results_by_n[n][name]
            if rs:
                m = statistics.fmean(rs)
                s = statistics.pstdev(rs) if len(rs) > 1 else 0.0
                sem = s / (len(rs) ** 0.5) if len(rs) > 1 else 0.0
            else:
                m, s, sem = None, 0.0, 0.0
            mean_ratios[name].append(m)
            stdev_ratios[name].append(s)
            sem_ratios[name].append(sem)
            n_success[name].append(len(rs))

    return {
        "n_values": list(n_values),
        "config_names": config_names,
        "instances": instances,
        "mean_ratios": mean_ratios,
        "stdev_ratios": stdev_ratios,
        "sem_ratios": sem_ratios,
        "n_success": n_success,
    }


def _merge_caches(old: dict, new: dict) -> dict:
    """Fusionne stats anciens + nouveaux instances (mêmes n_values & configs).

    Combine moyennes et variances (Welford / formule des E[X²]) à partir des
    comptes `n_success` (ou `instances` par défaut côté old).
    """
    config_names = old["config_names"]
    n_values     = old["n_values"]
    assert new["n_values"] == n_values, "n_values must match between old and new"

    def _ns_list(cache, name):
        return cache.get("n_success", {}).get(name, [cache["instances"]] * len(n_values))

    out_mean:    dict[str, list] = {name: [] for name in config_names}
    out_stdev:   dict[str, list] = {name: [] for name in config_names}
    out_sem:     dict[str, list] = {name: [] for name in config_names}
    out_n_succ:  dict[str, list] = {name: [] for name in config_names}

    for name in config_names:
        ns_old_arr = _ns_list(old, name)
        ns_new_arr = _ns_list(new, name)
        for j, _ in enumerate(n_values):
            m_o, s_o, n_o = old["mean_ratios"][name][j], old["stdev_ratios"][name][j], ns_old_arr[j]
            m_n, s_n, n_n = new["mean_ratios"][name][j], new["stdev_ratios"][name][j], ns_new_arr[j]

            if m_o is None and m_n is None:
                m_t, s_t, n_t = None, 0.0, 0
            elif m_o is None:
                m_t, s_t, n_t = m_n, s_n, n_n
            elif m_n is None:
                m_t, s_t, n_t = m_o, s_o, n_o
            else:
                n_t = n_o + n_n
                m_t = (n_o * m_o + n_n * m_n) / n_t
                ex2 = (n_o * (s_o**2 + m_o**2) + n_n * (s_n**2 + m_n**2)) / n_t
                s_t = max(0.0, ex2 - m_t**2) ** 0.5
            sem_t = (s_t / n_t**0.5) if n_t > 1 else 0.0
            out_mean[name].append(m_t)
            out_stdev[name].append(s_t)
            out_sem[name].append(sem_t)
            out_n_succ[name].append(n_t)

    return {
        "n_values":     n_values,
        "config_names": config_names,
        "instances":    old["instances"] + new["instances"],
        "mean_ratios":  out_mean,
        "stdev_ratios": out_stdev,
        "sem_ratios":   out_sem,
        "n_success":    out_n_succ,
    }


@app.local_entrypoint()
def main(n_values: str = "2,5,10,15,20,25,30,40,50,60,70,80,90,95,100,110,115,120,125,140",
         instances: int = 70,
         instance_offset: int = 30,
         capacity: int = 25,
         truck: int = 30,
         seed: int = 2026,
         ils_max_iter: int = 20,
         existing_cache: str = "renders/sweep_data.json",
         out_path: str = "renders/sweep_data.json"):
    """Par défaut : 70 nouvelles instances (offset 30) fusionnées avec le cache
    existant (30 instances) → 100 instances au total. Pour repartir de zéro :
    `--instance-offset 0 --existing-cache ""`.
    """
    n_list = [int(x) for x in n_values.split(",")]
    n_runs = len(n_list) * instances * 10
    print(f"Sweep : n ∈ {n_list}")
    print(f"        × {instances} nouvelles instances (offset {instance_offset}) "
          f"× 10 configs = {n_runs} runs")

    data_new = run_full_sweep.remote(
        n_list, instances, capacity, truck, seed, ils_max_iter, instance_offset)

    if existing_cache and Path(existing_cache).exists():
        with open(existing_cache) as f:
            old = json.load(f)
        if old.get("n_values") == n_list:
            print(f"Fusion avec {existing_cache} ({old['instances']} instances existantes)")
            data = _merge_caches(old, data_new)
        else:
            print(f"n_values du cache existant diffèrent → pas de fusion, on écrase")
            data = data_new
    else:
        data = data_new

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Écrit : {out_path}  ({data['instances']} instances totales)")
