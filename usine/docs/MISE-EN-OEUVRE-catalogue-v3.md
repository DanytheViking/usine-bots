# Catalogue v3 : précisions de mise en œuvre (12/11/2026, avant toute collecte)

Complète PREREG-usine-catalogue-v3-chasseur.md et l'addendum v3 (point A, Testeur durci ; le point B, T6, sera testé à part en temps réel). Figé avant les données ; son sha256 est inscrit dans USINE-SPEC-v3.json.

## Données
- Source : API publique Hyperliquid uniquement, comme pré-enregistré (pas de données Binance dans ce verdict).
- Univers : les noms de la liste présents dans le méta au moment de la collecte, délistés compris quand l'historique existe (l'addendum A prime sur « hors délistés »).
- Fenêtres : 5000 bougies 4 h pour T1, T2, T3 ; 5000 bougies 1 h (environ 208 jours) pour T4 et T5 ; 5000 bougies journalières de BTC pour le filtre de T2.
- Listings (T5) : un perp est « listé dans la fenêtre » si sa première bougie journalière est postérieure au début de la fenêtre 1 h plus un jour. La date de listing est sa première bougie 1 h.

## Règles de calcul
- ATR : moyenne simple du true range (n = 20 pour T1 et T2, 14 sinon), sur bougies closes.
- T2 : à l'heure du signal (clôture de la bougie 4 h), on lit la dernière bougie journalière de BTC déjà close et sa SMA 200.
- T3 : rebalancement chaque lundi 00:00 UTC sur la bougie 4 h close à cette heure ; rendement 7 jours = 42 bougies 4 h ; sortie à la clôture de la 42e bougie ou au stop.
- T4 : le funding retenu pour une bougie 1 h est celui réglé à sa clôture (heure pleine). Les trois heures consécutives incluent la bougie du signal. La sortie « funding < 0,01 % » se lit à la clôture et s'exécute à l'ouverture suivante.
- T5 : signal à la clôture de la 24e bougie 1 h depuis le listing, comparée à l'ouverture de la première ; un seul trade par listing.
- Une position à la fois par actif et par candidat ; T3 n'a qu'une position à la fois.

## Testeur durci (addendum A)
- Fenêtre de chaque candidat : de la première bougie disponible (T1 à T3) ou du début de la fenêtre 1 h (T4, T5) jusqu'à la fin des données ; coupe au milieu ; trades à cheval exclus.
- Acheter et garder : rendement moyen, également pondéré, d'une position longue sans levier de la coupe à la fin, sur les actifs du candidat déjà cotés à la coupe.
- « Stratégie à 1 % » : somme des R de l'évaluation (frais doublés) × 1 %, sans capitalisation, pour comparer à acheter et garder.
- Stress frais × 3 : métriques publiées ; le critère d'espérance reste au scénario × 2.
- Leave-one-asset-out : appliqué seulement si le candidat passe tous les critères ; si le verdict retombe en retirant un seul actif, le candidat ne passe pas.
- PF minimal : 1,35.
