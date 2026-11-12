# T6, le Récolteur de cascades : précisions de mise en œuvre (12/11/2026, avant toute donnée)

Complète l'addendum v3, point B (PREREG-usine-catalogue-v3-addendum-T6.md). Figé avant la première connexion ; son sha256 est imprimé au démarrage et inscrit dans le journal. Papier uniquement : aucune clé d'exchange, aucun ordre réel.

## Données
- Flux public Hyperliquid (WebSocket) : trades, bbo (meilleur bid et ask), l2Book agrégé à 3 chiffres significatifs (pour la profondeur à 1 % du mid), candle 5 min, activeAssetCtx (funding prévu). Amorçage et trous par l'API publique REST (candleSnapshot).
- Horloge : horodatage Hyperliquid (plus grand ts reçu, tous flux confondus). L'heure du VPS sert seulement à mesurer la latence.
- Liste : les 30 memecoins du catalogue v3 présents et non délistés dans le méta au démarrage. BTC pour le filtre de régime.

## Univers (8 actifs)
- Semaine de mesure (J0 à J7) : profondeur acheteuse cumulée à 1 % du mid échantillonnée chaque minute sur toute la liste. Les cascades sont journalisées, sans trade papier.
- À J7 : les 8 meilleures moyennes forment l'univers ; liste et sha256 journalisés. Reclassement tous les 30 jours sur les 7 derniers jours. Les cascades restent journalisées sur toute la liste, prises ou non.
- Profondeur : somme px × taille des niveaux bid du carnet agrégé dont le prix est ≥ 0,99 × mid. Approximation par niveaux agrégés, assumée.

## Signal
- ATR : moyenne simple du true range sur 14 bougies 5 min closes (dernière valeur du flux à la clôture).
- Actif prêt : 21 minutes de flux continu, ATR disponible, bbo et carnet de moins de 10 s.
- À chaque transaction (ts t, prix p) : H = plus haut des transactions de [t − 60 s, t].
  1. H − p ≥ 1,5 × ATR ;
  2. notionnel vendeur agresseur (side A) de ]t − 60 s, t] ≥ 3 × la médiane des 20 fenêtres de 60 s précédentes ;
  3. profondeur acheteuse à 1 % ≥ 3 × le notionnel visé.
- Une fois la condition 1 remplie, les conditions 2 et 3 sont évaluées au plus toutes les 250 ms par actif (charge de calcul).
- Une cascade est journalisée au plus une fois par actif et par tranche de 5 minutes.
- Régime : vol 1 h de BTC = racine de la somme des carrés des rendements log des 12 dernières bougies 5 min closes ; médiane 7 jours sur les 2016 dernières valeurs. Pas d'entrée au-delà de 3 × la médiane.

## Ordres papier
- Capital papier : 100 USDC ; équité = capital + résultat réalisé.
- Taille : risque 1 % de l'équité (0,5 % en mode réduit) ; stop = 2,5 × ATR ; notionnel plafonné à 20 % de l'équité ; levier 3× isolé ; taille arrondie aux décimales de l'actif ; notionnel < 10 USD : pas d'ordre (journalisé).
- Cible : VWAP des transactions de [t − 360 s, t − 60 s]. Si la cible n'est pas au-dessus du prix d'entrée : pas d'ordre (journalisé).
- Entrée ALO : prix = mid − 0,5 × (H − p), arrondi à 5 chiffres significatifs. Si le prix est ≥ au meilleur ask : nouveau prix × (1 − 0,0005), 5 essais au plus. Expiration 90 s.
- Remplissage : chaque transaction strictement sous le prix limite remplit min(reste, taille). Frais maker 0,015 %. Un remplissage partiel arme le stop pour la quantité remplie ; le reste est annulé à l'expiration.
- Stop : dès qu'une transaction s'imprime ≤ stop, sortie au prix de cette transaction × (1 − 0,0005), frais taker 0,045 %.
- Cible : sortie quand une transaction s'imprime strictement au-dessus, pour toute la quantité, frais maker.
- Temps : 15 minutes après le premier remplissage, sortie au meilleur bid, frais taker.
- Funding : si le funding prévu dépasse 0,05 % contre la position, sortie au meilleur bid. Funding réglé à chaque heure pleine : taux × notionnel au mid.

## Garde-fous
- Au plus 2 lignes (ordres en attente et positions) ; 6 ordres par heure glissante ; 1 entrée par actif et par 30 minutes.
- Résultat réalisé du jour UTC ≤ −2 % de l'équité de 00:00 : pause de 12 h.
- 3 pertes de suite : mode réduit jusqu'à 2 gains de suite.

## Trous de flux et redémarrages
- Après une déconnexion ou un redémarrage : actif froid pendant 21 minutes ; ordres en attente annulés.
- Positions ouvertes : la période du trou est rejouée sur les bougies 1 min (REST), bougie par bougie, stop testé avant la cible (stop au prix du stop × (1 − 0,0005)) ; l'échéance de 15 minutes sort à la clôture de la minute concernée.
- Reconnexion : attente exponentielle de 1 à 60 s ; ping toutes les 50 s.

## Journal et verdict
- Journal JSONL chaîné SHA-256. On y trouve :
  - toutes les cascades : latence, conditions, prise ou motif du refus ;
  - les ordres et les remplissages ;
  - les sorties : MFE et MAE en R, durée, temps de réversion, profondeur obtenue par rapport au mid, funding, frais, champ libre « liquidation / news ».
- Rapport : PF net en frais × 1, × 2 et × 3. Après 60 trades papier, PF (frais × 3) < 1,2 : ABANDON, plus aucun trade papier. Fin de phase à 500 remplissages ou 21 jours de phase papier.
