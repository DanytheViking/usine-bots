# Pré-enregistrement : addendum au catalogue v3 (12/11/2026, avant toute donnée)

Origine : revue externe demandée par Richard (une autre IA), retenue par Richard le 12/11. Richard garde Claude comme exécutant. Cet addendum complète PREREG-usine-catalogue-v3-chasseur.md ; il est figé avant toute collecte.

## A. Testeur durci (s'applique à T1 à T6)
- Base « acheter et garder » en plus de « ne rien trader » : rendement d'une position longue sans levier, également pondérée sur l'univers, sur la même fenêtre, pour séparer l'alpha du bêta.
- Funding compté des deux côtés (payé et reçu) : déjà le cas, conservé.
- Scénario de stress à frais × 3 en plus de × 2 ; le critère « espérance > 0 » s'applique au scénario × 2, le × 3 est publié.
- Leave-one-asset-out : le verdict est recalculé en retirant chaque actif à tour de rôle ; un candidat dont l'avantage disparaît sans un seul actif est déclaré « dépendant d'un actif » et ne passe pas.
- Actifs délistés réintégrés quand l'API fournit leur historique (déjà le cas pour l'univers point dans le temps).
- Seuil PF relevé à 1,35 pour le lot v3 (cinq candidats testés ensemble).

## B. T6 « Le Récolteur de cascades » (tête brûlée : achète les mèches de liquidation, en maker)
- Univers : les 8 perps memecoins les plus liquides de la liste v3, classés par profondeur acheteuse cumulée à 1 % du mid (moyenne de la semaine de collecte), liste figée chaque mois et hachée en sha256.
- Signal de cascade (les trois, dans cet ordre) : baisse ≥ 1,5 × ATR(5 min, bougies closes) en ≤ 60 s ; volume vendeur agresseur sur 60 s ≥ 3 × la médiane des 20 fenêtres de 60 s précédentes ; profondeur acheteuse à 1 % du mid ≥ 3 × le notionnel visé.
- Filtre de régime : pas d'entrée si la volatilité réalisée 1 h de BTC dépasse 3 × sa médiane 7 jours.
- Entrée : ordre ALO (post-only) à mid − 0,5 × profondeur de la mèche, expiration 90 s, une entrée par actif et par 30 minutes. Taille : 1 % de risque avec stop à 2,5 × ATR(5 min), notionnel plafonné à 20 % du capital, levier 3× isolé. ALO rejeté (croiserait le carnet) : nouvel essai avec un prix réduit de 0,05 %.
- Sortie, première condition atteinte : cible au VWAP 5 min d'avant la cascade ; stop trigger reduce-only côté serveur à 2,5 × ATR sous l'entrée, posé aussitôt le remplissage connu ; sortie au marché à 15 minutes ; sortie anticipée si le prochain funding horaire dépasse 0,05 % contre la position.
- Garde-fous : 2 cascades simultanées au plus, 6 trades par heure, arrêt à −2 % sur la journée puis pause 12 h, taille divisée par deux après 3 pertes consécutives jusqu'à 2 gains.
- Test : pas de backtest possible sur bougies (la cascade dure 1 à 3 minutes). Phase papier en temps réel (WebSocket trades + carnet), qui sert aussi de collecteur : toutes les cascades détectées sont enregistrées, prises ou non. Remplissage papier d'un ALO seulement si une transaction s'imprime STRICTEMENT au-delà du prix limite (file d'attente inconnue : hypothèse prudente).
- Journal obligatoire : latence, profondeur obtenue par rapport au mid, temps de réversion, MFE, MAE, funding, frais, champ libre « liquidation / news ».
- Critère d'abandon : après 60 trades papier, PF net < 1,2 (frais et funding inclus, stress frais × 3) → abandon sans discussion. Objectif de collecte : jusqu'à 500 remplissages ou 3 semaines.
- Pièges d'implémentation à traiter et tester : ALO rejeté ; triggers serveur reduce-only ; ATR sur bougies closes ; reconnexion WebSocket et trous de séquence (réinitialisation du carnet) ; budget de poids API et backoff exponentiel ; horodatage Hyperliquid et non celui du VPS. Tests exigés : remplissage partiel, annulation avant remplissage, stop envoyé immédiatement après le remplissage.

## C. Règle d'arrêt de la recherche
Si T1 à T6 échouent, on garde M2 sur Moonshot et on arrête d'empiler des stratégies.
