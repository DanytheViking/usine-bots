# Pre-enregistrement : Lab v5, entree en tendance M2 1 h pour Smart Peanut (22/11/2026)

Ecrit avant la collecte et tout calcul. Demande ecrite de Richard du 22/11/2026 (20 h 13 UTC) : « Smart Peanut ne trade toujours pas,
passons sur strategie reel plus agressive ». Constat du 22/11 : Smart Peanut 2.6.0 (M2 1 h, 2 %, 13 actifs de Moonshot) n'a ouvert aucun
trade depuis le 18/11 ; les 13 actifs sont en tendance baissiere (EMA 50 de 3 a 11 % sous l'EMA 200) et M2 n'entre qu'au croisement.
Les parametres ci-dessous sont figes et ne seront pas retouches apres lecture d'un resultat.

## Donnees (jeu m2t, collecte neuve avec usine.collecte_m2h1)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a l'heure pleine du lancement (22/11), donc la baisse recente est incluse.
- Les 13 actifs de Moonshot presents dans le meta ; bougies 1 h (5000 au plus, environ 208 jours) et funding reel.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.

## Candidat decisif (un seul, fige) : M2T_1h_tendance
- Tendance = signe de EMA 50 moins EMA 200 sur bougies 1 h closes (memes EMA que M2).
- Sans position sur l'actif : entree dans le sens de la tendance a l'ouverture suivante, stop initial 3 x ATR(14) 1 h.
- Sortie au croisement inverse (ouverture suivante), puis entree immediate dans le nouveau sens ; apres un stop, nouvelle entree des la
  cloture suivante si la tendance n'a pas change. Une position par actif.
- Filtre de volume du bot reel : volume des 24 h closes >= 2 M$ a l'entree (MIN_DAY_VOLUME_USD de deploy/env/peanut2.json).
- Simulation commune (usine.sim) : entree taker, stop teste en premier, glissement de stop 0,05 %, funding reel.

## Information (non decisive)
- M2 1 h au croisement seul, avec le meme filtre, sur le meme jeu : ce que Smart Peanut 2.6.0 aurait fait.
- Publies : trades par jour, stress frais x 3, intervalle de confiance par blocs de jours, sans les 3 meilleurs trades, entrainement,
  pire serie de pertes, baisse maximale en R, croissance composee a 2 %, 5 % et 10 %.

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles
- au moins 40 trades ; esperance >= +0,10 R ; croissance composee positive au risque en cours (moyenne de ln(1 + 0,02 x R) > 0).

## Regle de decision
- Passe : propose a Richard pour le reel au Lab a 2 %, apres sa confirmation ecrite du capital expose et des limites, tests et audit d'Aristote.
- Ne passe pas mais esperance >= 0 : publie ; reel seulement sur exception ecrite de Richard.
- Esperance < 0 : recommandation de ne pas la mettre en reel.
