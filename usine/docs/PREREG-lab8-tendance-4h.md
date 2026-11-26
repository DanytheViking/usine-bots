# Pre-enregistrement : Lab v8 « Tendance 4 h confirmee » pour Smart Peanut (26/11/2026)

Ecrit avant la collecte et tout calcul sur ces regles. Demande ecrite de Richard du 26/11/2026 (20 h 30 UTC) : « sur Smart Peanut trouve une
nouvelle strategy optimal ». Recherche seulement : rien ne change en reel par ce test.
Les parametres ci-dessous sont figes et ne seront pas retouches apres lecture d'un resultat.

## D'ou vient l'idee (faits connus avant ce test)
- La seule famille positive dans toutes les coupes de l'usine est la tendance EMA 50 / 200 en 4 h (M2 : +0,24 R en evaluation et +0,68 R
  a l'entrainement sur 13 actifs, verdicts v1 et v2). En 1 h, la meme tendance a un entrainement negatif (M2 1 h, M2T, Furie Momentum).
- M2 en 4 h trade rarement (environ 10 trades par mois, 2 signaux reels en deux semaines) parce qu'il n'entre qu'au croisement.
- En reel, M2T 1 h (entree dans la tendance a toute heure) a perdu ses six premieres entrees (deux prises, quatre ecartees par Thales et
  suivies en papier). Les 13 veto de Thales du 23/11 avaient tous la meme raison : le prix etait repasse du mauvais cote de l'EMA 50.
- Portage (Lab v7), cassures, compressions, top movers, rotation, copie, HIP-3 : echecs ou non concluants.
- Idee : garder la tendance 4 h, la rejoindre sans attendre un croisement, mais seulement quand le prix est du bon cote de l'EMA 50.
  C'est la raison des veto de Thales ecrite en regle fixe, donc mesurable et sans appel paye.

## Donnees (jeu t4h, collecte neuve avec usine.collecte_t4h)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a la cloture 4 h qui precede le lancement.
- Les 13 actifs de Moonshot presents dans le meta ; bougies 4 h (5000 au plus, environ 833 jours, moins pour les actifs recents) et funding reel.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.
- Limite assumee : la fenetre recouvre celles des jeux majeurs et etendu, ou le resultat de M2 au croisement est connu. L'entree dans la
  tendance en 4 h et la condition sur l'EMA 50 n'ont jamais ete calculees sur ces donnees.

## Candidat decisif (un seul, fige) : T4H_confirmee
- Bougies 4 h closes. Tendance = signe de EMA 50 moins EMA 200 (memes EMA que M2).
- Sans position sur l'actif : long si tendance haussiere ET cloture > EMA 50 ; short si tendance baissiere ET cloture < EMA 50.
- Entree a l'ouverture suivante (taker), stop initial 3 x ATR(14) 4 h, jamais deplace.
- Sortie au croisement inverse des EMA (ouverture suivante) ou au stop. Apres une sortie, nouvelle entree des que les conditions sont reunies.
- Filtre de volume du bot reel : volume des 24 h closes >= 2 M$ a l'entree. Une position par actif.
- Au plus deux positions ouvertes tous actifs confondus, dans l'ordre des entrees (strategies_lab4.capacite).
- Simulation commune (usine.sim) : stop teste en premier, glissement de stop 0,05 %, funding reel.

## Information (non decisive)
- T4H_tendance : memes regles sans la condition sur l'EMA 50 (M2T en 4 h), pour mesurer ce que la confirmation apporte.
- M2_4h_croisement (temoin) : M2 au croisement seul sur le meme jeu, ce que fait Moonshot.
- Publies : trades par jour, frais x 3, intervalle de confiance par blocs de jours, sans les 3 meilleurs, entrainement, pire serie,
  baisse maximale en R, croissance composee a 2 %, 5 % et 10 %, resultat par actif.

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles, deux positions au plus
- au moins 40 trades ; esperance >= +0,10 R ; croissance composee positive a 2 % (moyenne de ln(1 + 0,02 x R) > 0).

## Regle de decision (fixee avant les donnees)
- Niveau « reel » : passe la voie rapide ET entrainement > 0 ET esperance sans les 3 meilleurs > 0 : propose a Richard pour remplacer M2T 1 h
  au Lab a 2 % par trade, apres sa confirmation ecrite, le code du bot, les tests d'execution et l'audit d'Aristote.
- Niveau « papier » : passe la voie rapide sans le reste : deux semaines en observation (aucun ordre) avant toute proposition de reel.
- Moins de 40 trades en evaluation : NON CONCLUANT, publie, aucun seuil retouche.
- Ne passe pas : rien en reel. Esperance < 0 : abandon sans nouveau reglage.
- La variante d'information et le temoin ne peuvent pas etre promus par ce test, quel que soit leur resultat.

## Regle d'arret en reel (fixee avant les donnees)
- Abandon a -6 R cumules, ou si l'esperance reelle est negative apres 30 trades.
- Arret de ligne du Lab inchange a -80 % du compte Labo ; 30 R / 20 pertes de suite inchanges.
