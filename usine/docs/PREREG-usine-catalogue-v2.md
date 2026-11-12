# Pré-enregistrement : catalogue v2 de l'usine (12/11/2026)

Écrit AVANT toute collecte et tout test des candidats v2, après lecture des verdicts v1 (VERDICTS-usine-v1-2026-11-12). Paramètres des stratégies inchangés : aucune optimisation. Les critères d'avantage sont ceux de la v1, sans assouplissement.

## Pourquoi ces deux candidats
- M2 a été le seul candidat v1 positif sur l'entraînement et sur l'évaluation, sur les 3 actifs, mais avec 40 trades seulement. On cherche une preuve indépendante : les mêmes règles sur d'autres actifs, jamais regardés.
- C1 n'a pas pu être testé : le réservoir trié par volume ne contenait que des wallets hyperactifs dont l'historique est tronqué par l'API. Le réservoir est corrigé ; les règles de sélection et de copie restent celles de la v1.

## Candidat M2_etendu (ligne Moonshot)
- Règles identiques à M2 v1 : croisement EMA 50 / EMA 200 en 4 h, long au croisement haussier, short au croisement baissier, stop initial 3 × ATR(14), sortie au croisement inverse, entrée taker à l'ouverture de la bougie suivante.
- Actifs, choisis par règle au moment de la collecte : les 10 perps validateurs (hors HIP-3, hors délistés) au plus gros volume notionnel 24 h (`dayNtlVlm` de `metaAndAssetCtxs`), hors BTC, ETH et SOL, ayant au moins 1500 bougies 4 h d'historique (environ 250 jours).
- Données : 5000 bougies 4 h au plus par actif et funding réel.
- Verdict principal : sur ces 10 nouveaux actifs réunis. Verdict secondaire, pour information : 13 actifs (avec BTC, ETH, SOL).

## Candidat C1_v2 (Copieur)
- Réservoir : parmi les lignes du classement public avec un compte entre 10 000 et 5 000 000 USDC et un volume du mois entre 1 et 50 millions USD, un échantillon aléatoire de 150 wallets (graine 20261112). L'échantillon aléatoire, plutôt qu'un tri par gain ou par volume, limite le biais de survie et évite les robots hyperactifs.
- Fills sur 60 jours ; sélection, copie et stop identiques à C1 v1 (MISE-EN-OEUVRE-catalogue-v1).
- Fenêtre : 60 jours de fills, coupe au milieu ; univers joué = BTC, ETH, SOL et les actifs du jeu 1 h collecté pour l'occasion (actifs du méta au volume 24 h ≥ 5 M$ au moment de la collecte).

## Règles communes (inchangées)
- Coûts : maker 0,015 %, taker 0,045 %, glissement de stop 0,05 %, funding réel, scénario frais doublés.
- Découpe : seconde moitié de la fenêtre en évaluation ; trades à cheval exclus.
- Critères d'avantage : au moins 30 trades, PF ≥ 1,2, espérance > 0 en frais doublés, borne basse de l'IC bootstrap par jour > 0 sur au moins 7 jours, espérance > 0 sur l'entraînement. Bootstrap 2000 tirages, graine 20261112.
- Un candidat qui passe entre en réel petit (1 % de risque par trade, décision de Richard du 09/11).

## Fable (décision de Richard du 12/11)
Claude Fable entre dans l'équipe en Chercheur (propositions hebdomadaires, toujours soumises au Testeur), en Anticipation (avis enregistrés sur chaque signal, en observation 3 à 4 semaines, veto en réel seulement si son apport est mesuré) et en Rapporteur (Telegram). Fable ne décide aucun trade tant que son apport n'est pas prouvé.
