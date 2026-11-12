# Catalogue v1 : précisions de mise en œuvre (09/11/2026, avant toute exécution sur données réelles)

Le pré-enregistrement fixe les règles. Ce document fixe les détails que le code devait trancher. Il est écrit et figé avant tout résultat ; son sha256 est inscrit dans la spécification `USINE-SPEC-v1.json`.

## Commun
- ATR(14) : moyenne simple sur 14 bougies du true range, connue à la clôture de la bougie.
- EMA : moyenne exponentielle classique (span n, sans correction de démarrage).
- Une seule position par actif et par candidat à la fois.
- Entrée à l'ouverture de la bougie qui suit le signal, taker. Dans chaque bougie, le stop est testé avant la cible. Une sortie sur signal (lu à la clôture) se fait à l'ouverture de la bougie suivante.
- Embargo : M1 et M2 n'ont pas de durée maximale. Au lieu d'un embargo fixe, la découpe classe un trade en entraînement seulement s'il est sorti avant la coupe, en évaluation seulement si son signal est après la coupe. Les trades à cheval sont exclus et comptés. C'est plus strict qu'un embargo fixe : aucun chevauchement possible.
- Fenêtres : M1 et M2 sur les 5000 bougies 4 h téléchargées (environ 830 jours). P1, P2 et C1 sur la fenêtre du jeu du 01/11 (5000 × 15 min, environ 52 jours).

## P2
- Rebalancement aux heures UTC multiples de 4 (0 h, 4 h, 8 h…), avec les bougies 1 h clôturées à cette heure.
- Sortie à la clôture de la 4e bougie 1 h ou au stop.

## C1
- Réservoir : les 100 wallets du classement public Hyperliquid au plus gros volume du mois, compte entre 10 000 et 5 000 000 USDC. Le classement par volume, plutôt que par gain, limite le biais de survie sans l'éliminer.
- Fills sur 60 jours (au plus 5 pages de 2000).
- Sélection sur les 28 jours qui précèdent la coupe (4 semaines ; la première peut déborder avant le début de la fenêtre, avec des données passées seulement). « 30 trades » = 30 fills avec P&L réalisé non nul.
- Teneurs de marché : plus de 80 % de fills maker. Les vaults ne sont pas identifiés à part : ils sont écartés seulement s'ils dépassent 5 000 000 USDC ou s'ils sont teneurs de marché.
- Retard de 60 s : approché par un prix d'entrée dégradé de 0,10 % par rapport au prix du wallet, et une sortie dégradée de 0,10 %.
- Stop testé dès la bougie 1 h d'entrée, sur toute la bougie (choix pessimiste).
- Seules les ouvertures (passage de 0 à une position, ou retournement) sont copiées ; les renforcements et allègements partiels sont ignorés.
- Entraînement de C1 : la copie des wallets retenus sur la première moitié. Elle est biaisée vers le haut par construction (mêmes données que la sélection) ; seule l'évaluation compte.
