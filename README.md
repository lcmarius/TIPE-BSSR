# TIPE BSSR (Bike-Sharing System Routing)

Optimisation de tournées de véhicules pour le rééquilibrage du réseau de vélos en libre-service Bicloo (Nantes). Un camion de capacité limitée doit visiter les stations pour redistribuer les vélos, en minimisant la distance totale parcourue.

## Utilisation

### Scrapper

Collecte les données en temps réel depuis l'API de Nantes Métropole (nombre de vélos disponibles, capacités, arrivés et départs)

```
./tipe.sh scrapper                        # lancer le scrapper
./tipe.sh scrapper --interval 5           # intervalle polling en secondes (défaut: 5)
./tipe.sh scrapper --status-interval 300  # intervalle recalage en secondes (défaut: 300)
./tipe.sh scrapper --data-dir data        # répertoire des données (défaut: data)
./tipe.sh scrapper --no-archive           # ne pas archiver la session précédente
```

## TODO

- Analyser les donnés du scrapper pour voir si elle sont régulières et déterminer un bon interval de temps à utiliser pour le targeter (principe de l'intervalle de temps pour une loi de poisson), l'intervalle recommandé peut être différents selon la période de la journée.
