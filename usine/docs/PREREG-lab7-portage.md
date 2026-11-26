# Pre-enregistrement : Lab v7 « Portage » pour Smart Peanut (26/11/2026)

Ecrit avant la collecte et tout calcul sur ces regles. Demande ecrite de Richard du 25/11/2026 (23 h 59 UTC) : « pour smart peanut trouve moi
la vertical [...] a explorer ». Recherche seulement : rien ne change en reel par ce test.
Les parametres ci-dessous sont figes et ne seront pas retouches apres lecture d'un resultat.

## Ce qui a deja echoue et ce qu'on en garde
- Toutes les familles lues sur le prix seul ont echoue ou restent sans avantage prouve sur ces actifs : cassures, compressions, top movers,
  plage Asie / US, Tortues, rotation, copie de wallets, M2 sur HIP-3 ; M2T (en reel au Lab) a un entrainement negatif et, en reel, ses six
  premieres entrees (deux prises, quatre ecartees par Thales et suivies en papier) ont toutes touche le stop.
- T6 (achat des cascades en maker) : PF net 0,67 sur 42 trades papier. Le remplissage maker arrive surtout quand la baisse continue.
- Lecon : sur ces actifs, le prix seul ne suffit pas, et plus de frequence donne plus de pertes.
- Jamais teste ici : le funding comme signal de positionnement. Essais voisins : funding_contre en 15 min (01/11, echec, seuils bas),
  T4 Contrarien (seuil 0,05 % par heure trois heures de suite et +30 % en 72 h : aucun trade, conditions jamais reunies).

## Hypothese
Sur un perpetuel, le funding dit quel cote est entasse et paie pour l'etre. Quand le funding moyen de 24 h est tres au-dessus du taux de base
(0,00125 % par heure), les acheteurs a levier sont nombreux et paient les vendeurs chaque heure. Tant que le prix monte, vendre est dangereux.
Quand le prix repasse sous sa moyenne, ces acheteurs entasses doivent sortir : on vend a ce moment, on est paye pour attendre, et on sort
quand le funding est revenu a la normale. Symetrique a l'achat quand les vendeurs sont entasses (funding tres negatif).
C'est une prime de portage connue sur les marches a terme, pas un defaut de la plateforme.

## Donnees (jeu portage, collecte neuve avec usine.collecte_portage)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a l'heure pleine du lancement.
- Actifs : les 30 memecoins de la liste v3 et les 13 actifs de Moonshot presents dans le meta (41 noms au plus) ; bougies 1 h (5000 au plus,
  environ 208 jours) et funding reel horaire sur la meme fenetre.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.
- Limite assumee : la fenetre recouvre celles des jeux lab4, m2t et fm. Aucune regle utilisant le funding comme signal n'a ete calculee sur ces donnees.

## Candidat decisif (un seul, fige) : PORTAGE_1h
- Bougies 1 h closes. F24 = moyenne des taux de funding horaires des 24 heures qui precedent la cloture (au moins 20 taux, sinon pas de signal).
- Short : F24 >= +0,005 % par heure (quatre fois le taux de base) ET cloture < EMA 50 (1 h).
- Long : F24 <= -0,005 % par heure ET cloture > EMA 50 (1 h).
- Entree a l'ouverture suivante (taker), stop initial 3 x ATR(14) 1 h, jamais deplace.
- Sortie, premiere condition atteinte : stop ; F24 revenu sous +0,00125 % par heure pour un short (au-dessus de -0,00125 % pour un long),
  a l'ouverture suivante ; 120 bougies (5 jours).
- Apres une sortie, nouvelle entree seulement si les conditions sont de nouveau reunies. Une position par actif.
- Filtre de volume du bot reel : volume des 24 h closes >= 2 M$ a l'entree.
- Au plus deux positions ouvertes tous actifs confondus, dans l'ordre des entrees (strategies_lab4.capacite).
- Simulation commune (usine.sim) : stop teste en premier, glissement de stop 0,05 %, funding reel compte (recu et paye).

## Information (non decisive)
- PORTAGE_1h_sans_ema : memes regles sans la condition sur l'EMA 50 (portage pur), pour mesurer ce que la condition de prix apporte.
- Publies : trades par jour, frais x 3, intervalle de confiance par blocs de jours, sans les 3 meilleurs, entrainement, pire serie,
  baisse maximale en R, croissance composee a 2 %, 5 % et 10 %, resultat par actif, part du funding dans le resultat (funding_R moyen).

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles, deux positions au plus
- au moins 40 trades ; esperance >= +0,10 R ; croissance composee positive a 2 % (moyenne de ln(1 + 0,02 x R) > 0).

## Regle de decision (fixee avant les donnees)
- Niveau « reel » : passe la voie rapide ET entrainement > 0 ET esperance sans les 3 meilleurs > 0 : propose a Richard pour le reel au Lab
  a 2 % par trade, apres sa confirmation ecrite, les tests d'execution et l'audit d'Aristote.
- Niveau « papier » : passe la voie rapide sans le reste : deux semaines en observation (aucun ordre) avant toute proposition de reel.
  Raison : M2T avait passe la voie rapide avec un entrainement negatif, et ses premieres entrees reelles ont toutes perdu.
- Moins de 40 trades en evaluation : NON CONCLUANT, publie, aucun seuil retouche.
- Ne passe pas : rien en reel. Esperance < 0 : abandon sans nouveau reglage, et application de la regle d'arret de l'addendum v3
  (M2 seul, fin de l'empilement de strategies) sauf demande ecrite contraire de Richard.

## Regle d'arret en reel (fixee avant les donnees)
- Abandon de Portage a -6 R cumules, ou si l'esperance reelle est negative apres 30 trades.
- Arret de ligne du Lab inchange a -80 % du compte Labo ; 30 R / 20 pertes de suite inchanges.
