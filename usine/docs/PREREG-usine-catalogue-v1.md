# Pré-enregistrement : catalogue v1 de l'usine (09/11/2026)

Écrit AVANT tout test de ces candidats. Paramètres figés : aucune optimisation. Toute modification donne une nouvelle version, annoncée.

## Résultat de départ (rapports du 01/11 sur VPS, sha256 replay_pit.md cd0fa44a…, replay_oos.md b1fe51f5…)
Les trois stratégies de Smart Peanut v0.1.x : PAS D'AVANTAGE, perdantes dans les deux moitiés et dans les deux scénarios de frais.
- rebond_flush : 496 trades, PF 0,56, -0,37 R/trade (frais base).
- retour_vwap : 2956 trades, PF 0,80, -0,13 R/trade.
- funding_contre : 176 trades, PF 0,80, -0,10 R/trade.
Elles sont retirées du catalogue. Les actifs positifs isolés ne sont pas retenus (petits échantillons, sélection a posteriori interdite).
Enseignement : sur BTC, ETH et SOL, le retour à la moyenne a été le plus perdant (-0,5 à -1 R) sur la période. Hypothèse à tester, pas une conclusion : la tendance a dominé.

## Candidats ligne Moonshot (BTC, ETH, SOL)
- M1 cassure_donchian_4h : long si clôture 4 h > plus haut des 20 bougies précédentes ; short si clôture < plus bas des 20 précédentes. Stop initial 2 × ATR(14). Sortie : cassure inverse du canal 10 bougies. Entrée à l'ouverture de la bougie suivante, taker.
- M2 croisement_ema_4h : long quand EMA 50 passe au-dessus de l'EMA 200 (4 h), short à l'inverse. Stop initial 3 × ATR(14). Sortie au croisement inverse.

## Candidats ligne Smart Peanut (univers point dans le temps, règle v0.1.3)
- P1 cassure_volume_1h : long si clôture 1 h > plus haut des 24 bougies précédentes ET volume > 2 × moyenne des 24 précédentes ; short symétrique. Stop 1,5 × ATR(14, 1 h), cible 3 × ATR, durée max 24 h.
- P2 momentum_rotation_4h : toutes les 4 h, classement de l'univers par rendement 24 h ; long des 2 premiers si rendement > 0 et clôture > EMA 50 (1 h). Sortie après 4 h ou stop 2 × ATR(14, 1 h).

## Candidat Copieur
- C1 copie_baleines : sélection des wallets sur la première moitié de la fenêtre uniquement (au moins 30 trades, résultat positif sur au moins 3 des 4 dernières semaines de cette moitié, valeur de compte entre 10 000 et 5 000 000 USDC, vaults et teneurs de marché exclus). Copie sur la seconde moitié de toute nouvelle position sur BTC, ETH, SOL et l'univers point dans le temps, avec 60 s de retard, entrée taker. Sortie quand le wallet ferme ou stop 2 × ATR(14, 1 h).
- Limite connue : le réservoir de wallets candidats vient du classement actuel (biais de survie). Atténuation : sélection et test sur des moitiés séparées.

## Règles communes
- Risque 1 % de l'equity par trade, levier max 5, isolé. Coûts identiques pour tous : maker 0,015 %, taker 0,045 %, glissement de stop 0,05 %, funding réel, scénario frais doublés.
- Holdout : dernière moitié de chaque fenêtre, embargo égal à la durée max d'un trade.
- Critères d'avantage (identiques à OOS-SP04-ext-b-v1) : au moins 30 trades, PF ≥ 1,2, espérance > 0 en frais doublés, borne basse de l'IC bootstrap par jour > 0 sur au moins 7 jours, espérance > 0 sur l'entraînement.
- Comparaison systématique à « ne rien trader » et comptes par actif.
- Un candidat qui passe entre en réel petit (décision de Richard du 09/11) ; sinon il reste coupé.
