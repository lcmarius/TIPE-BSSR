"""renders/simulate_modal_fetch.py
Récupère les résultats d'une simulation multi-jours déjà tournée sur Modal
(et écrits sur le Volume `bicloo-multi-day-results`), puis génère le
rendu stratifié 2×2 en local.

Contourne `modal run --fetch` quand celui-ci plante sur la connexion
longue durée (Python 3.14 + SSL Modal).

Prérequis : `modal deploy renders/simulate_modal.py` + une simulation
spawned via `simulate_modal_spawn.py` qui s'est terminée (volume écrit).

Usage :
    python -m renders.simulate_modal_fetch
"""

import os
import pickle

import modal

from renders.simulate_modal import (
    CACHE_LOCAL, RENDER_OUT, APP_NAME,
    render_stratified, _print_summary,
)


FETCH_FUNCTION = "fetch_latest_results"


def main() -> None:
    print(f"Appel de {APP_NAME}.{FETCH_FUNCTION} pour récupérer les résultats...")
    fn = modal.Function.from_name(APP_NAME, FETCH_FUNCTION)
    results = fn.remote()
    print(f"{len(results)} résultats reçus.")

    os.makedirs(os.path.dirname(CACHE_LOCAL), exist_ok=True)
    with open(CACHE_LOCAL, "wb") as f:
        pickle.dump(results, f)
    print(f"Cache local écrit : {CACHE_LOCAL}")

    print("Rendu...")
    out = render_stratified(results, RENDER_OUT)
    print(f"OK — {out}")
    _print_summary(results)


if __name__ == "__main__":
    main()
