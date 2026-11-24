# Pre-enregistrement : Lab v6 « Furie Momentum » pour Smart Peanut (24/11/2026)

Ecrit avant la collecte et tout calcul sur ces regles. Demandes ecrites de Richard du 24/11/2026 (03 h 30 a 03 h 33 UTC) :
« fais moi une strategie furi Motion », « tu envoies la strategie Furi Motion », « si il est perdu il est perdu mais on va faire en sorte
qu'il grossisse ». Enveloppe : le seul compte Labo, perte totale acceptee.
Les parametres ci-dessous sont figes et ne seront pas retouches apres lecture d'un resultat.

## Ce qui a deja echoue et ce qu'on en garde
- Echecs (frais doubles, evaluation) : compression 1 h et 15 min, Asie / US, top movers 1 h (Lab v4, -0,14 a -0,22 R) ; cassure de volume 1 h
  (P1, -0,27 R) ; rotation momentum 4 h (P2, -0,10 R) ; Tortues memecoins (T1, -0,08 R) ; M2 sur HIP-3 (-0,32 R).
  Lecon : une cassure sans tendance de fond, sur ces actifs, perd ses frais.
- Seul signal positif en evaluation sur les 13 actifs : la tendance EMA 50 / 200 en 1 h (Lab v5, +0,42 R sans plafond, +0,20 R avec deux positions),
  mais l'avantage vient de quelques gros trades (-0,53 R sans les 3 meilleurs) et l'entrainement est negatif. Entrer a toute heure dans la tendance
  paie beaucoup de petites pertes en range.
- Idee de Furie Momentum : garder la tendance de fond qui marche, mais n'entrer que quand le momentum explose dans son sens (nouveau plus haut
  ou plus bas de 24 h), et sortir vite quand il s'eteint (cloture de l'autre cote de l'EMA 50). Moins d'entrees en range, sorties plus rapides,
  et une relance a chaque nouvelle cassure tant que la tendance dure.

## Donnees (jeu fm, collecte neuve avec usine.collecte_m2h1)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a l'heure pleine du lancement.
- Les 13 actifs de Moonshot presents dans le meta ; bougies 1 h (5000 au plus, environ 208 jours) et funding reel.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.
- Limite assumee : la fenetre recouvre presque celle du jeu m2t du Lab v5, dont le resultat de M2T est connu. Les regles de Furie Momentum
  n'ont jamais ete calculees sur ces donnees ; le temoin M2T est rejoue pour comparer sur le meme jeu.

## Candidat decisif (un seul, fige) : FM_1h_furie
- Bougies 1 h closes. Tendance = signe de EMA 50 moins EMA 200 (memes EMA que M2).
- Long : tendance haussiere ET cloture > plus haut des 24 bougies precedentes. Short : tendance baissiere ET cloture < plus bas des 24 precedentes.
- Entree a l'ouverture suivante (taker), stop initial 3 x ATR(14) 1 h, jamais deplace.
- Sortie : cloture de l'autre cote de l'EMA 50 (sous l'EMA 50 pour un long, au-dessus pour un short), a l'ouverture suivante ; ou au stop.
- Apres une sortie, nouvelle entree seulement sur une nouvelle cassure qui respecte les memes conditions. Une position par actif.
- Filtre de volume du bot reel : volume des 24 h closes >= 2 M$ a l'entree.
- Au plus deux positions ouvertes tous actifs confondus, dans l'ordre des entrees (strategies_lab4.capacite).
- Simulation commune (usine.sim) : stop teste en premier, glissement de stop 0,05 %, funding reel.

## Information (non decisive)
- FM_1h_pyramide : FM_1h_furie, plus au plus un ajout par position, de meme risque, a l'ouverture qui suit la premiere cloture ou la position
  gagne au moins +1 R ET fait un nouveau plus haut (plus bas) de 24 h ; stop propre de l'ajout 3 x ATR(14), meme sortie que la position.
  L'ajout compte comme une position pour le plafond de deux. Jamais d'ajout sur une position perdante.
- M2T_1h_tendance (temoin, regles du Lab v5 inchangees) : ce que Smart Peanut 2.7 fait en reel.
- Publies : trades par jour, frais x 3, intervalle de confiance par blocs de jours, sans les 3 meilleurs, entrainement, pire serie,
  baisse maximale en R, croissance composee a 2 %, 5 % et 10 %, resultat par actif.

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles, deux positions au plus
- au moins 40 trades ; esperance >= +0,10 R ; croissance composee positive a 2 % (moyenne de ln(1 + 0,02 x R) > 0).

## Regle de decision (fixee avant les donnees)
- Niveau « furie » : passe la voie rapide ET entrainement > 0 ET esperance sans les 3 meilleurs > 0 ET croissance composee a 5 % > 0
  ET esperance d'evaluation >= celle du temoin M2T : propose a Richard pour remplacer M2T au Lab a 5 % par trade.
- Niveau « Lab » : passe la voie rapide ET esperance d'evaluation >= celle du temoin M2T, sans le reste : propose pour remplacer M2T a 2 %.
- Passe la voie rapide mais fait moins bien que M2T : publie, M2T reste en reel.
- Ne passe pas : rien en reel, M2T reste. Esperance < 0 : abandon sans nouveau reglage.
- Toute mise en reel : confirmation ecrite de Richard du palier, tests d'execution, audit d'Aristote.

## Regle d'arret en reel (fixee avant les donnees)
- Abandon de Furie Momentum a -6 R cumules, ou si l'esperance reelle est negative apres 30 trades (verdict ecrit par Pyrrhon) : retour a M2T.
- Arret de ligne du Lab inchange a -80 % du compte Labo ; 30 R / 20 pertes de suite inchanges.
- Montee de 5 % vers 10 % seulement selon les paliers du Lab (15 trades propres) et un nouveau verdict ; jamais pour se refaire.
