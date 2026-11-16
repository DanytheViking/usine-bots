# Pre-enregistrement : Lab v4 « furie », strategies actives pour Smart Peanut (16/11/2026)

Ecrit avant toute collecte et tout calcul. Demande ecrite de Richard du 16/11/2026 (16 h 55 UTC) : « Changer de strategie, je veux que
ce soit des tetes brulees du trading et qu'il trade sans peur. Trouver une autre verticale si necessaire. Smart Peanut doit trader en fury. »
Choix de Richard du 16/11/2026 (16 h 57 UTC, carte de decision) : tester ensemble la cassure apres compression et la chasse aux top movers,
la meilleure qui passe la voie rapide du Lab va en reel au palier en cours. Les parametres ci-dessous sont figes et ne seront pas retouches
apres lecture d'un resultat.

## Donnees (jeu lab4, collecte neuve)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a l'heure pleine du lancement.
- Actifs : les memecoins de la liste du Lab (collecte_v3.MEMES) presents dans le meta, plus BTC, ETH, SOL et HYPE.
- Bougies 1 h (5000 au plus, environ 208 jours) et 15 min (5000 au plus, environ 52 jours), funding reel sur la fenetre 1 h.
- Coupe au milieu de chaque fenetre (entrainement, puis evaluation). Trades a cheval exclus.

## Regles communes
- Simulation commune de l'usine (usine.sim) : signal sur bougie close, entree taker a l'ouverture suivante, stop teste avant la cible,
  glissement de stop 0,05 %, funding reel. Une position par actif.
- Liquidite : une entree n'est prise que si le volume des 24 h closes (somme volume x cloture) atteint 1 M$ (filtre du Lab, a defaut
  de pouvoir rejouer le carnet d'ordres).
- Capacite du compte : deux positions ouvertes au plus, tous actifs confondus, dans l'ordre des entrees (regle du Lab). C'est la serie
  decisive ; la serie sans plafond est publiee pour information.

## Candidats (quatre, figes)
1. L1_compression_1h et 2. L1_compression_15m (meme regle sur les deux unites de temps) :
   boite = plus haut et plus bas des 12 bougies precedentes ; compression si la largeur de la boite (en % de la cloture precedente) est au plus
   le quantile 20 % des 200 largeurs precedentes ; long si la cloture casse le haut de la boite, short si elle casse le bas ;
   stop = autre cote de la boite, au moins 1 ATR(14) ; cible 2 R ; sortie au plus tard apres 24 bougies.
3. L1b_asie_us_15m (variante des deux poles, idee de Richard du 15/11) : plage = plus haut et plus bas des bougies 15 min de 00 h a 08 h UTC ;
   pendant la seance americaine (ouverture 14 h 30 UTC en hiver, 13 h 30 UTC pendant l'heure d'ete americaine), premiere cloture 15 min hors
   de la plage, jusqu'a une heure avant la fin de seance (21 h UTC en hiver, 20 h UTC en ete) ; un trade par actif et par jour ;
   stop = milieu de la plage, au moins 1 ATR(14, 15 min) ; sortie a la fin de seance ou au stop.
4. L2_top_movers_1h : la cloture depasse le plus haut (ou passe sous le plus bas) des 24 bougies precedentes ET le volume de la bougie
   vaut au moins 3 fois la moyenne des 24 precedentes ; stop 1,5 ATR(14) ; sortie au plus tard apres 6 bougies.

Note honnete : P1 (cassure 1 h avec pic de volume, catalogue v1) etait proche de L2 et a perdu (-0,27 R en evaluation). Les essais haute
frequence du 26/10 sur les memecoins ont aussi echoue. L2 differe par le seuil de volume (3 x au lieu de 2 x), l'absence de cible et la
sortie a 6 bougies. L'a priori est faible ; le test tranche.

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles, serie plafonnee a deux positions
Un candidat passe si :
- au moins 40 trades en evaluation ;
- esperance >= +0,10 R ;
- croissance composee positive au palier en cours : moyenne de ln(1 + 0,10 x R) > 0 (publiee aussi a 15 % et 20 %) ;
- durcissement, quatre candidats testes ensemble : esperance d'entrainement > 0 en frais doubles.
Publies sans etre bloquants : resultat sans les 3 meilleurs trades, stress frais x 3, intervalle de confiance par blocs de jours,
retrait de chaque actif a tour de role, frequence mesuree (trades par jour), pire serie de pertes.

## Regle de decision
- Si un ou plusieurs candidats passent : celui qui a la plus forte croissance composee a 10 % est propose pour le reel au Lab, apres les
  tests d'execution P0b et l'audit d'Aristote, au palier en cours.
- Si aucun ne passe : rien ne va en reel sur la foi de ce test ; le resultat est publie a Richard, qui reste libre de decider une exception.
- Abandon fixe a l'avance en reel : -6 R cumules ou esperance negative apres 30 trades reels.
