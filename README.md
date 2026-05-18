# TIPE BSSR — Bike-Sharing System Routing

## Problématique

Un camion de capacité limitée parcourt les stations Bicloo de Nantes pour rééquilibrer les vélos disponibles : il en prélève là où il y a un surplus pour les déposer là où il y a un déficit. On cherche la tournée qui minimise le temps total de redistribution.

C'est un **Vehicle Routing Problem (VRP) avec collecte et livraison**, généralisation NP-difficile du problème du voyageur de commerce. L'approche retenue combine des algorithmes d'approximation (constructions gloutonnes) et des algorithmes incrémentaux (2-opt, 3-opt) appliqués à la tournée initiale.

**Mots-clés** : vélos en libre service · problème de tournées de véhicule · théorie des graphes · optimisation · NP-difficile.

## Architecture

Trois sous-systèmes indépendants :

1. **`src/scrapper/`** — collecte temps réel des mouvements de vélos via l'API Bicloo (Cyclocity Nantes), persistance SQLite et nettoyage des données par jour.
2. **`src/targeter/`** — calcul du stock cible de chaque station via un modèle de Skellam (problème newsvendor à une période).
3. **`src/solver/`** — modélisation du réseau routier (OSMnx), construction puis amélioration de la tournée.

Pipeline : le scrapper produit la matière première (positions individuelles + mouvements unitaires), le targeter en déduit les `bike_target` par station, le solver calcule la tournée optimale.

## Installation

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Utilisation

### Scrapper — collecte temps réel

```bash
python -m src.main scrapper                          # défauts : poll 5 s, recalage 5 min, data/
python -m src.main scrapper --interval 5             # intervalle polling /bikes (s)
python -m src.main scrapper --status-interval 300    # intervalle recalage /station_status (s)
python -m src.main scrapper --data-dir data          # répertoire des données
python -m src.main scrapper --no-archive             # ne pas archiver la session précédente
```

Stratégie deux sources : polling rapide de `/bikes` (vélo par vélo, permet de reconstituer les mouvements et de classifier la source USER / TRUCK / MAINTENANCE) + recalage périodique sur les counts officiels `/station_status`.

### Postprocess — nettoyage d'une journée

```bash
python -m src.main postprocess <db> --date YYYY-MM-DD                   # extraction d'un jour
python -m src.main postprocess <db> --date YYYY-MM-DD --output-dir <d>  # cible alternative
python -m src.main postprocess <db> --date YYYY-MM-DD --no-keep-truck   # ne garder que USER
```

Pipeline en quatre étapes : tronquer au jour, filtrer par source, interpoler les valeurs aberrantes, supprimer les mouvements orphelins.

## TODO

- Critiquer les résultats et la démarche : impact des approximations successives (indépendance Poisson, troncature de Skellam, vitesses OSM réduites, heuristiques d'approximation au lieu d'une résolution exacte) sur la qualité de la tournée.
- Ajouter ref bibliographique :  Bräysy, O. & Gendreau, M. (2005). Vehicle Routing Problem with Time Windows, Part I: Route Construction and Local Search Algorithms. Transportation Science 39(1), 104-118.
- Ajouter ref bibliographique : Lourenço, H. R., Martin, O. C. & Stützle, T. (2003). Iterated Local Search. In F. Glover & G. Kochenberger (eds.), Handbook of Metaheuristics, vol. 57, pp. 320–353. Kluwer Academic.
- Ajouter ref bibliographique : Federgruen, A. & Groenevelt, H. (1986). The greedy procedure for resource allocation problems: necessary and sufficient conditions for optimality. Operations Research, 34(6), 909–918. (justifie l'optimalité du glouton dans `targeter/targeter.py`)
