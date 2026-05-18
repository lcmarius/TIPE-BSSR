---
title: Modèle Skellam pour le targeter — choix et limites
lang: fr
geometry: a4paper, margin=2cm
fontsize: 11pt
numbersections: true
header-includes:
  - \usepackage{titling}
  - \setlength{\droptitle}{-5em}
  - \usepackage{titlesec}
  - \titlespacing*{\section}{0pt}{1.0ex}{0.6ex}
  - \titlespacing*{\subsection}{0pt}{0.8ex}{0.4ex}
---

# Le modèle

Sur un créneau d'une heure, à une station, on note deux variables
aléatoires à valeurs dans $\mathbb{N}$ :

- $N_{\text{in}}$ : nombre de vélos qui **arrivent** à la station ;
- $N_{\text{out}}$ : nombre de vélos qui **en repartent**.

**Hypothèses :** $N_{\text{in}} \sim \mathrm{Poisson}(\lambda_{\text{in}})$,
$N_{\text{out}} \sim \mathrm{Poisson}(\lambda_{\text{out}})$, et $N_{\text{in}}$,
$N_{\text{out}}$ **indépendantes**.

La grandeur que le targeter cherche à anticiper est la **variation nette
du stock** sur l'heure : $\Delta = N_{\text{in}} - N_{\text{out}}$.
Comme différence de deux lois de Poisson indépendantes, $\Delta$ suit
la **loi de Skellam** $(\lambda_{\text{in}}, \lambda_{\text{out}})$.

Les paramètres $\lambda_{\text{in}}, \lambda_{\text{out}}$ dépendent de
**quatre variables explicatives** :

- la **station** ;
- l'**heure** $h \in \{0, \dots, 23\}$ ;
- le **type de jour** $\in$ \{ouvré (lun--ven), week-end (sam--dim)\} ;
- la **saison** $\in$ \{froid (avant 20 mars 2026), tempéré (à partir)\}.

# Justification du modèle

## Pourquoi Poisson pour $N_{\text{in}}$ et $N_{\text{out}}$

Les trois hypothèses caractéristiques d'un processus de Poisson sont
qualitativement vérifiées :

- **événements rares** sur l'heure ($< 10$ mouvements/h/station typiquement) ;
- **inter-événements sans mémoire** (pas d'effet de groupe à grande échelle) ;
- **taux $\lambda$ stable** dans la fenêtre d'une heure.

Conditions valides en régime non saturé (station ni vide ni pleine).

## Pourquoi $N_{\text{in}}$ et $N_{\text{out}}$ indépendantes

Déposer un vélo et en retirer un sont deux décisions individuelles
décorrélées. La corrélation n'apparaît qu'aux **saturations** : un
usager ne peut pas déposer sur une station pleine, donc forcer la
station vers le plein bloque mécaniquement les arrivées suivantes.

## Pourquoi conditionner sur le type de jour et la saison

Vérification empirique sur les $\approx 90$ jours scrappés
(cf. `src/targeter/render.py`) :

- **ouvré vs week-end** : pic matinal 8h marqué en semaine, absent le
  week-end ; profils horaires nettement distincts.
- **froid vs tempéré** : demande tempérée $\approx +60\%$ par rapport
  au froid, à type de jour fixé.

Coupure froid/tempéré au **20 mars 2026** : équinoxe de printemps,
repère astronomique neutre, sans biais de calendrier.

Croiser donne $2 \times 2 = 4$ strates de 10 à 40 jours chacune.
Ajouter une 5\textsuperscript{e} variable (vacances, jour précis) ferait
passer certaines strates sous 5 jours et dégraderait la précision de
$\lambda$.

\newpage

# Limites

1. **Période courte.** $\approx 90$ jours seulement (février $\to$ mai
   2026). Aucune couverture estivale ni automnale ; aucune année
   complète pour observer les cycles annuels.

2. **Coupure climatique brutale.** Le 19 et le 21 mars sont en pratique
   quasi-identiques mais classés dans des saisons différentes — c'est
   une approximation grossière d'un passage progressif.

3. **Pas de météo locale.** Un mardi tempéré sous pluie battante est
   prédit comme un mardi tempéré ensoleillé, alors que la demande peut
   chuter d'un facteur 2 sous la pluie.

4. **Vacances scolaires non modélisées.** Effet visible mais données
   insuffisantes pour les caractériser comme une 5\textsuperscript{e}
   dimension du découpage.

5. **Stations saturées (censure).** Quand une station est régulièrement
   pleine, certains *ARRIVAL potentiels* n'apparaissent pas dans la
   base (l'usager ne peut physiquement pas déposer) ;
   $\lambda_{\text{in}}$ y est mécaniquement sous-estimé. Effet à
   corriger spécifiquement pour les stations chroniquement saturées.

6. **Indépendance des heures.** $\lambda_h$ et $\lambda_{h+1}$ sont
   estimés séparément, sans tirer parti de la continuité naturelle de
   la demande au cours de la journée. Un lissage (noyau gaussien sur
   $h$, spline) gagnerait en précision sur les strates peu peuplées.
