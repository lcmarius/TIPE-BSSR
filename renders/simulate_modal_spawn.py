"""renders/simulate_modal_spawn.py
Lance la fonction `run_all_days` déjà déployée sur Modal en mode
fire-and-forget (très court appel HTTP, contourne les problèmes de
connexion longue durée Python 3.14 + aiohttp + SSL).

Prérequis : `modal deploy renders/simulate_modal.py` doit avoir été
exécuté avant (l'app `bicloo-multi-day` doit exister).

Usage :
    python -m renders.simulate_modal_spawn

Ça schedule la simulation des 90 jours, affiche un FunctionCall ID, et
sort immédiatement. La simulation tourne ensuite côté Modal (~45-60 min)
et écrit ses résultats sur le Modal Volume `bicloo-multi-day-results`.

Pour récupérer le résultat plus tard :
    modal run renders/simulate_modal.py --fetch
    # ou si Modal CLI continue de planter :
    python -m renders.simulate_modal_fetch
"""

import glob
import os

import modal


APP_NAME      = "bicloo-multi-day"
FUNCTION_NAME = "run_all_days"


def main() -> None:
    dates = sorted([os.path.basename(f)[len("clean_"):-len(".sql")]
                    for f in glob.glob("data/clean/clean_*.sql")])
    if not dates:
        raise SystemExit("Aucun clean_*.sql trouvé dans data/clean/")

    print(f"Récupération de la fonction déployée {APP_NAME}.{FUNCTION_NAME}...")
    fn = modal.Function.from_name(APP_NAME, FUNCTION_NAME)

    print(f"Spawn de la simulation sur {len(dates)} jours...")
    call = fn.spawn(dates)

    print()
    print(f"  Function call ID : {call.object_id}")
    print(f"  Modal dashboard  : https://modal.com/apps/azirixxoffi/main/"
          f"deployed/{APP_NAME}")
    print()
    print("La simulation tourne maintenant côté Modal (~45-60 min).")
    print("Les résultats seront écrits sur le Modal Volume "
          "`bicloo-multi-day-results`.")
    print()
    print("Pour récupérer le résultat plus tard :")
    print("    python -m renders.simulate_modal_fetch")


if __name__ == "__main__":
    main()
