# Pre-enregistrement : M2 en 1 h sur les actifs de Moonshot (catalogue v4, ligne Moonshot), 16/11/2026

Ecrit avant toute collecte et tout calcul. Demande de Richard du 16/11/2026 (17 h 02 UTC) : « mon Moonshot est positif pour le moment mais
ne trade pas assez ». Choix de Richard du 16/11/2026 (17 h 09 UTC, carte de decision) : tester M2 en 1 h et, en parallele, reprendre pour
Moonshot un candidat du Lab v4 qui passerait (option 4c). Moonshot garde ses regles prudentes : ce test ne releve aucun risque.
Les parametres de M2 sont figes depuis le catalogue v1 et ne sont pas modifies ; seule l'unite de temps change.

## Donnees (jeu m2h1, collecte neuve)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a l'heure pleine du lancement.
- Actifs : les 13 actifs de Moonshot (BTC, ETH, SOL, ZEC, HYPE, NEAR, kPEPE, XRP, PUMP, XMR, LIT, UNI, AVAX), ceux presents dans le meta.
- Bougies 1 h (5000 au plus, environ 208 jours) et funding reel sur la fenetre.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.

## Candidat (un seul, fige)
- M2_1h_moonshot : croisement EMA 50 / 200 sur bougies 1 h closes, stop initial 3 x ATR(14) 1 h, sortie et retournement au croisement inverse,
  entree taker a l'ouverture suivante, glissement de stop 0,05 %, funding reel (simulation commune usine.sim). Une position par actif.
  Aucun filtre de volume (Moonshot n'en a pas : MIN_DAY_VOLUME_USD = 0).

## Information (non decisive)
- M2 4 h reconstruit depuis les memes bougies 1 h (agregation par tranches de 4 h UTC), meme fenetre et meme coupe : comparaison honnete
  du regime de marche, puisque M2 4 h n'est pas rejoue sur ce jeu pour decider.
- Publies : trades par mois sur les 13 actifs, stress frais x 3, acheter et garder, retrait de chaque actif a tour de role, pire serie de pertes.

## Criteres (evaluation), ceux de la priorite 1 et du Testeur durci
- au moins 30 trades ;
- PF >= 1,35 en frais de base et esperance > 0 en frais doubles (Testeur commun, peanut.replay_oos.verdict) ;
- borne basse de l'intervalle de confiance a 5 % de l'esperance en frais doubles > 0, blocs de jours, sur au moins 7 jours ;
- esperance d'entrainement > 0 ;
- l'avantage ne depend d'aucun actif seul (retrait de chaque actif a tour de role).

## Regle de decision
- AVANTAGE : papier deux semaines (instance separee du meme code, unite de temps par variable, suivi par Diogene), puis reel au risque
  de Moonshot sur un sous-compte que Richard cree et alimente lui-meme (option 4c). Tout relevement de risque reste soumis a sa confirmation ecrite.
- Esperance >= 0 sans avantage demontre : rien ne va en reel sur la foi de ce test ; Richard reste libre d'une exception ecrite.
- Esperance < 0 : M2 1 h est abandonne pour Moonshot, sans nouveau reglage.
