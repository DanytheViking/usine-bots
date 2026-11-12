# Pré-enregistrement : vérification de M2 sur les memecoins (Smart Peanut v2), 12/11/2026

Écrit avant tout calcul. Smart Peanut v2 trade M2 en réel depuis le 12/11 sur la liste des 30 memecoins (décision d'exception de Richard). M2 n'a jamais été testé sur ces actifs. Le jeu de données v3 (manifeste 4b5f27a5…) a déjà été lu pour T1 à T5, pas pour M2. Les paramètres de M2 sont figés depuis le catalogue v1 et ne sont pas modifiés.

## Règles
- M2 identique au Testeur et au bot réel : croisement EMA 50/200 sur bougies 4 h closes, stop initial 3 × ATR(14), sortie et retournement au croisement inverse, entrée taker à l'ouverture suivante, funding réel.
- Données : bougies 4 h et funding des memecoins du jeu v3 (délistés compris), fenêtre du jeu, coupe au milieu, trades à cheval exclus.
- Vue B (réplique du réel, décisive) : une entrée n'est prise que si le volume des 24 h précédant le signal (somme volume × clôture des 6 dernières bougies 4 h) atteint 2 M$, comme le filtre MIN_DAY_VOLUME_USD du bot.
- Vue A (information) : sans filtre de volume.
- Critères : ceux des catalogues v1 et v2 (au moins 30 trades, PF ≥ 1,2, espérance > 0 en frais doublés, borne basse de l'IC à 5 % > 0 sur au moins 7 jours, espérance d'entraînement > 0). Publiés en plus : stress frais × 3, acheter et garder, retrait de chaque actif à tour de rôle.

## Règle de décision (vue B, évaluation, frais doublés)
- Espérance < 0 : recommandation de mettre Smart Peanut en pause. La décision reste à Richard.
- Espérance ≥ 0 sans avantage démontré : Smart Peanut continue à 1 % de risque, sans augmentation.
- Avantage démontré : Smart Peanut continue.
