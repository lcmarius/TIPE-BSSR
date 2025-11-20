# TIPE BSSR (Bike-sharing system routing)
Plan a truck route to minimize the time spent on bicycle stations in the Nantes network.

## TODO
- Supprimer le fichier benchmark une fois fini (car après on sera confronté qu'à la situation réelle, plus besoin de simuler des situations)
- Dans le fichier principal solver, compléter la méthode solve avec un paramètre enum algorithme qui permet de choisir l'algorithme à utiliser, il renverra le solving graph + les metrics associés (la review)
- Dans la partie scrapping, savoir quelles données récupérer (définir une structure de donnée) + review le code
- Commencer à élaborer une stratégie dans le targeter (définir mathématiquement le problème ?), revoir les contraintes et les donnés en notre posséssion.
- Voir aussi un nouveau système de calcule de distance entre 2 points géographique (pour remplacer celui actuellement):
  - via une API en ligne d'itinéraire de routes
  - système de cache pour éviter de faire trop d'appels 
  - Est-ce que sur ce système on prend en compte le temps de trajet, la distance ? les 2 ? 
  - Il faudra prendre en compte le fais que la distance n'est pas la même lorsque que l'on va de A à B ou de B à A (sens unique, sens interdit, etc)
  - On ne prendra pas en compte le trafic routier (pas pour problème de complexité, mais parce que cela prendrait trop de temps à récupérer les données en ligne pour chaque situation etc)