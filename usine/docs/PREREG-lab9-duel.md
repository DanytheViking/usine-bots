# Pre-enregistrement : Lab v9 « Duel » pour Smart Peanut (26/11/2026)

Ecrit avant la collecte et tout calcul sur ces regles. Demande ecrite de Richard du 26/11/2026 (20 h 30 UTC) : « sur Smart Peanut trouve une
nouvelle strategy optimal ». Recherche seulement : rien ne change en reel par ce test.
Les parametres ci-dessous sont figes et ne seront pas retouches apres lecture d'un resultat.

## Ce qui a deja echoue et ce qu'on en garde
- Tout ce qui a ete teste jusqu'ici prend une position seule sur un actif : cassures, compressions, top movers, plage Asie / US, Tortues,
  rotation, copie de wallets, cascades (T6), M2 sur HIP-3, Furie Momentum, Portage. Aucun ne passe.
- La seule ligne positive sur l'entrainement ET l'evaluation est M2 en 4 h (croisement EMA 50 / 200, stop 3 ATR), deja en reel sur Moonshot.
  En 1 h (M2T, en reel au Lab), l'entrainement est negatif.
- Constat du reel (23/11) : les deux shorts du Lab (BTC et ETH) ont ete stoppes ensemble par le meme rebond du marche. Les 13 actifs
  montent et baissent avec BTC : deux positions « differentes » sont en pratique un seul pari sur le marche, le meme que Moonshot.
- En cours le meme jour, verdict inconnu a l'heure ou ceci est ecrit : Lab v8 « Tendance 4 h confirmee » (position seule, dans le sens
  de la tendance 4 h). Le Duel est une autre piste et ne s'appuie pas sur son resultat.
- Jamais teste ici : une position a deux jambes, neutre au marche, qui parie sur la force d'un actif CONTRE BTC et non sur la direction du marche.

## Hypothese
La force relative d'un actif face a BTC (le rapport de leurs prix) suit des tendances longues : les memecoins et les altcoins perdent
du terrain face a BTC pendant des mois, puis en regagnent par vagues. Ces tendances viennent de flux lents (rotation des capitaux, dilution,
mode du moment) et ne dependent pas du sens du marche. En achetant l'actif et en vendant BTC pour le meme montant (ou l'inverse), on garde
la tendance relative et on retire le mouvement commun : un rebond general du marche ne stoppe plus la position.
C'est une strategie de paire classique, sans IA dans la decision, sans defaut de plateforme exploite.
Les reglages sont ceux de M2, repris tels quels (EMA 50 / 200, 4 h, stop equivalent a 3 ATR) : aucun parametre n'est choisi pour ce test.

## Donnees (jeu duel, collecte neuve avec usine.collecte_duel)
- Endpoints publics Hyperliquid, aucune cle. Fin figee a la cloture 4 h qui precede le lancement.
- Actifs : les 30 memecoins de la liste v3 et les 13 actifs de Moonshot presents dans le meta (42 noms au plus, BTC compris) ; bougies 4 h
  (5000 au plus, environ 833 jours) et funding reel sur la meme fenetre.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.
- Limite assumee : la fenetre recouvre celles des jeux v1, v2, v3 (M2 en 4 h y a ete calcule sur les prix). Aucune regle sur le rapport
  d'un actif a BTC n'a ete calculee sur ces donnees.

## Candidat decisif (un seul, fige) : DUEL_4h
- Pour chaque actif X autre que BTC, sur les bougies 4 h closes communes a X et a BTC : rapport q = cloture de X / cloture de BTC.
- Signal : EMA 50 du rapport qui croise l'EMA 200 du rapport. Croisement vers le haut : duel acheteur (achat de X, vente de BTC).
  Croisement vers le bas : duel vendeur (vente de X, achat de BTC).
- Entree a l'ouverture 4 h suivante, les deux jambes au meme montant en dollars, au taux taker. q d'entree = ouverture de X / ouverture de BTC.
- Volatilite du rapport : A = moyenne sur 14 bougies de la variation absolue du rapport d'une cloture a la suivante.
  Stop : distance de 6 x A sur le rapport, fixee a l'entree, jamais deplacee. Raison du 6 : le rapport n'a pas de plus haut ni de plus bas
  fiables, et pour une marche au hasard l'ecart moyen d'une bougie vaut environ deux fois sa variation de cloture a cloture ; 6 x A est donc
  l'equivalent du stop a 3 ATR de M2. Ce chiffre est fixe ici, avant les donnees.
- Le stop est lu a la cloture de chaque bougie 4 h (comme le bot le lira) : si le rapport cloture au-dela du stop, les deux jambes sortent
  a l'ouverture suivante, avec un glissement de 0,05 % sur chaque jambe. La perte peut donc depasser 1 R : elle est comptee telle quelle.
- Sortie sur signal : croisement inverse, a l'ouverture suivante ; le duel inverse est alors ouvert (comme M2).
- 1 R = le montant d'une jambe multiplie par (distance du stop / q d'entree).
- Filtre de volume du bot reel sur X : volume des 24 h closes >= 2 M$ au signal.
- Au plus deux duels ouverts en meme temps, dans l'ordre des entrees (strategies_lab4.capacite).
- Couts comptes : quatre ordres taker par duel (deux entrees, deux sorties), funding reel paye et recu sur chaque jambe.

## Information (non decisive)
- M2_4h_temoin : M2 inchange sur les prix des memes actifs (BTC compris), sans filtre de volume, deux positions au plus, pour comparer.
- Correlation des resultats journaliers (en R, evaluation) entre DUEL_4h et M2_4h_temoin : dit si le Duel apporte autre chose que Moonshot.
- Publies : trades par jour, frais x 3, intervalle de confiance par blocs de jours, sans les 3 meilleurs, entrainement, pire serie,
  baisse maximale en R, croissance composee a 2 %, 5 % et 10 %, resultat par actif, funding moyen par trade, plus grosse perte en R.

## Voie rapide du Lab (PRIORITES.md, section LAB), evaluation, frais doubles, deux duels au plus
- au moins 40 trades ; esperance >= +0,10 R ; croissance composee positive a 2 % (moyenne de ln(1 + 0,02 x R) > 0).

## Regle de decision (fixee avant les donnees)
- Niveau « reel » : passe la voie rapide ET entrainement > 0 ET esperance sans les 3 meilleurs > 0 : propose a Richard pour le Lab a 2 %
  par duel. Le bot ne sait pas encore tenir deux jambes : le reel demande d'abord ce code (entree et sortie des deux jambes, stop de secours
  de chaque jambe pose chez Hyperliquid, tests), la confirmation ecrite de Richard et l'audit d'Aristote. En attendant, observation sans ordre.
- Niveau « papier » : passe la voie rapide sans le reste : deux semaines en observation (aucun ordre) avant toute proposition de reel.
- Moins de 40 trades en evaluation : NON CONCLUANT, publie, aucun seuil retouche.
- Ne passe pas : rien en reel. Esperance < 0 : abandon sans nouveau reglage.
- Dans tous les cas, aucune variante (autre reference que BTC, autre duree, autre stop) n'est retenue sur la foi de ce jeu de donnees.

## Regle d'arret en reel (fixee avant les donnees)
- Abandon du Duel a -6 R cumules, ou si l'esperance reelle est negative apres 30 duels.
- Arret de ligne du Lab inchange a -80 % du compte Labo ; 30 R / 20 pertes de suite inchanges.
