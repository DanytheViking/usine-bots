# Pré-enregistrement : catalogue v3, ligne Chasseur (memecoins), 12/11/2026

Écrit AVANT toute collecte et tout test. Demande de Richard : une équipe de traders « têtes brûlées » inspirée des plus grands traders, sur tous les memecoins possibles, compte Smart Peanut (Labo). Chaque trader de l'équipe est une stratégie en règles fixes, tirée d'un principe documenté de ce trader. Aucune optimisation. Les critères d'avantage sont ceux des v1 et v2, sans assouplissement.

## Univers memecoins (règle fixée avant les données)
Perps validateurs Hyperliquid (hors HIP-3, hors délistés) dont le nom figure dans la liste : kPEPE, kBONK, kSHIB, kFLOKI, kNEIRO, kDOGS, DOGE, WIF, POPCAT, FARTCOIN, TRUMP, MELANIA, PUMP, PENGU, MOODENG, GOAT, PNUT, SPX, MEW, BRETT, TURBO, CHILLGUY, USELESS, MEME, BOME, MYRO, GRIFFAIN, AI16Z, VINE, HPOS, plus tout perp listé pendant la fenêtre de données (candidat T5 seulement). Un nom absent du méta au moment de la collecte est ignoré. Données : 5000 bougies 4 h (et 1 h pour T5), funding réel.

## L'équipe (5 candidats)
- T1 « La Tortue » (Richard Dennis, système 2 des Turtles) : 4 h ; long si clôture > plus haut des 55 bougies précédentes, short si < plus bas des 55 ; stop initial 2 × ATR(20) ; sortie sur cassure inverse du canal 20.
- T2 « La Tortue disciplinée » (règle de Paul Tudor Jones : rien de bon sous la moyenne 200 jours) : T1, mais longs seulement si la clôture journalière de BTC est au-dessus de sa moyenne simple 200 jours, shorts seulement si elle est en dessous (filtre lu sur la dernière bougie journalière clôturée).
- T3 « Le Druckenmiller » (concentration sur la plus forte conviction) : chaque lundi 00:00 UTC, classement des memecoins par rendement 7 jours ; long du premier si rendement > 0 et clôture 4 h > EMA 50 (4 h) ; sortie au lundi suivant ou au stop 3 × ATR(14, 4 h).
- T4 « Le Contrarien » (fading des excès, à la GCR) : short si le funding horaire dépasse 0,05 % trois heures de suite ET si le prix a monté de plus de 30 % en 72 h ; stop 2 × ATR(14, 1 h) ; sortie quand le funding repasse sous 0,01 % ou après 48 h. Avertissement : l'idée voisine funding_contre (seuils plus bas, 15 min) a échoué le 01/11.
- T5 « Le Chasseur de listings » (momentum des nouveaux tokens) : pour tout perp listé pendant la fenêtre, 24 h après sa première bougie, long si la clôture dépasse le prix d'ouverture du listing, short sinon ; sortie après 72 h ou au stop 2 × ATR(14, 1 h).

## Règles communes (inchangées)
- Entrée taker à l'ouverture de la bougie suivant le signal ; stop testé avant la cible ; coûts maker 0,015 %, taker 0,045 %, glissement de stop 0,05 %, funding réel, scénario frais doublés. Sur les memecoins, le glissement réel peut être plus fort : le scénario frais doublés est le garde-fou minimal.
- Découpe : seconde moitié de la fenêtre en évaluation ; trades à cheval exclus.
- Critères d'avantage : au moins 30 trades, PF ≥ 1,2, espérance > 0 en frais doublés, borne basse de l'IC bootstrap par jour > 0 sur au moins 7 jours, espérance > 0 sur l'entraînement.
- Cinq candidats testés en même temps : un seul « gagnant » par hasard est possible ; seul un candidat qui passe TOUS les critères peut aller en réel.

## Rôles autour de l'équipe
- Visionnaire (Fable) : lecture du régime et des narratifs, propositions hebdomadaires, avis sur chaque signal (observation, sans veto tant que son apport n'est pas mesuré).
- Directeur des risques (règle de Paul Tudor Jones « la défense d'abord ») : le Gardien, 1 % de risque par trade sauf décision écrite de Richard, arrêt de ligne, chien de garde.
- Testeur : juge chaque trader sur l'historique, sans complaisance.

## Données à collecter pour une v4
Open interest et liquidations n'ont pas d'historique sur l'API Hyperliquid : un collecteur les enregistre toutes les 5 minutes à partir de l'installation, pour tester plus tard les cascades de liquidations.
