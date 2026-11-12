# Usine, paquet 1 : note de limites (09/11/2026)

## Ce que le paquet fait
- Il code les 5 candidats du catalogue v1 (M1, M2, P1, P2, C1), conformes au pré-enregistrement et aux précisions de mise en œuvre, toutes deux figées avant toute exécution.
- Il collecte les données qui manquent : bougies 4 h et funding de BTC, ETH et SOL (environ 830 jours), puis classement et fills des baleines.
- Il rend les verdicts sur la seconde moitié de chaque fenêtre, avec frais doublés, base « ne rien trader », comptes par actif et funding réel.
- Il n'envoie aucun ordre, ne lit aucune clé et ne touche à aucun fichier existant. Le jeu du 01/11 (`/root/replay-pit-data`) est lu en lecture seule, après vérification de son manifeste.

## Ce que je n'ai pas pu faire
- Je n'ai rien exécuté sur données réelles : mon espace de travail ne joint pas Hyperliquid. Les tests tournent sur des données synthétiques et sur le faux Hyperliquid de l'extension (a).
- Format du classement public (`stats-data.hyperliquid.xyz/Mainnet/leaderboard`) : supposé `leaderboardRows[]`, avec `ethAddress`, `accountValue` et `windowPerformances` (dont `month.vlm`). Les lignes illisibles sont ignorées ; si le format diffère, le réservoir sera vide et C1 « non concluant ».
- Ordre et pagination de `userFillsByTime` : supposés du plus ancien au plus récent, 2000 par réponse, 10 000 fills récents au plus. Un wallet dont l'historique n'est pas complet sur la période de sélection est exclu.

## Limites de méthode
- **Un seul découpage par candidat.** Pour P1, P2 et C1, la fenêtre fait environ 52 jours, donc environ 26 jours d'évaluation : un seul régime de marché probable. M1 et M2 couvrent environ 830 jours, ce qui est plus solide.
- **Copie approchée.** Le retard de 60 s est modélisé par 0,10 % de prix dégradé, sans carnet d'ordres. Le réservoir de wallets vient du classement actuel : biais de survie résiduel, atténué par le tri sur le volume et la sélection sur la première moitié seulement.
- **Bougies, pas carnet.** Entrées et sorties au prix des bougies plus le glissement déclaré. Sur les memecoins peu liquides, le glissement réel peut être plus fort ; le scénario frais doublés couvre une partie de cet écart, pas tout.
- **Verdict sur le signal, pas sur le bot.** Le test ne simule ni le plafond de positions simultanées, ni l'arrondi des tailles minimales Hyperliquid (10 USDC), ni les pannes réseau.
- **Bootstrap par jours.** Il suppose des jours indépendants : une tendance de plusieurs jours rend l'intervalle trop étroit. C'est un critère parmi cinq.

## Temps estimés sur le VPS
- Collecte 4 h : environ 5 minutes. Collecte des baleines : 30 à 100 minutes selon l'activité des wallets, reprenable.
- Verdicts : quelques minutes (chargement et vérification du jeu du 01/11 compris).
