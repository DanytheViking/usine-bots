# Priorites de l'equipe (fixees le 14/11/2026, mises a jour le 15/11/2026)

Socrate lit ce fichier a chaque passage et le met a jour quand une priorite est traitee.

## 0. Smart Peanut devient la « tete brulee » (demande ecrite de Richard du 14/11/2026, 23 h 43 : « Plus de trades et 3 % »)
- Etape 1 (commit du 14/11) : la constitution accepte 3 % de risque par trade pour Smart Peanut seulement (BOT_NAME smartpeanut2) ; Moonshot reste a 1 %.
- Etape 1 bis (commit du 15/11) : la constitution accepte aussi 2 % pour Moonshot (demande ecrite de Richard du 15/11/2026, 00 h 12 :
  « je te donne 100 % mon accord pour tester et monter le plafond si il le faut, je prends les responsabilites »).
- Etape 2 (Socrate, seulement APRES que deployeur.log montre « Deployeur mis a jour par le depot » pour le commit de l'etape 1 bis, sinon le commit serait refuse) :
  dans moonshot2/moon/config.py remplacer exactement la ligne RISK_PER_TRADE par
  RISK_PER_TRADE = min(_f("RISK_PER_TRADE", "0.01"), 0.03 if NAME == "smartpeanut2" else 0.02)
  et ajouter deploy/env/peanut2.json avec {"RISK_PER_TRADE": "0.03"} et deploy/env/moonshot2.json avec {"RISK_PER_TRADE": "0.02"}
  (garder les variables deja presentes si ces fichiers existent), avec un test qui verifie 3 % pour smartpeanut2, 2 % pour moonshot2
  et le plafond quand la variable demande plus. Aristote audite. La position XMR ouverte garde sa taille : le 2 % vaut pour les nouveaux trades.
- Etape 3 (apres la recherche de la priorite 1) : Smart Peanut passe a la frequence plus rapide (1 h) et/ou au filtre de volume 1 M$ si l'esperance
  de la variante est au moins nulle en frais doubles (exception de Richard : sans attendre tous les criteres) ; sinon il reste en 4 h a 3 %.
  Si le code ne gere pas encore la frequence par variable, l'ajouter (intervalle des bougies, delai de signal, MAX_SIGNAL_AGE), avec tests.
- Annoncer chaque etape a Richard.

## 1. Smart Peanut : frequence et avantage (recherche du dimanche 15/11)
Constat : aucun signal depuis le 12/11. Attendu : environ 1 a 2 trades par mois, car seuls 4 memecoins (DOGE, FARTCOIN, TRUMP, PUMP)
passent le filtre de volume de 2 M$, et kPEPE est ecarte par l'ordre minimum. Ce n'est pas une panne.
- Ne pas changer la strategie en reel sans verdict pre-enregistre.
- Pre-enregistrer avant toute lecture (catalogue v4, ligne memecoins), puis faire juger par Pyrrhon :
  - M2 en 1 h sur les memecoins (EMA 50/200, stop 3 x ATR(14), memes regles d'execution) ;
  - M2 4 h avec un filtre de volume abaisse a 1 M$ ;
  - criteres du lot : PF >= 1,35, esperance > 0 en frais doubles et en stress x 3, IC, leave-one-asset-out, et frequence attendue par mois publiee.
- Un candidat qui passe va d'abord en papier deux semaines (suivi par Diogene), puis en reel s'il reste conforme.
- Plusieurs frequences en meme temps (demande de Richard du 14/11) : Hyperliquid n'a qu'une position par actif et par compte, donc
  chaque frequence validee tourne comme une instance separee du meme code (frequence et compte par variables), sur son propre
  sous-compte. Le versement vers le sous-compte est fait par Richard (le code ne deplace jamais de fonds). Risque : 1 % par trade
  et par sous-compte ; Epictete surveille l'exposition cumulee quand deux frequences prennent le meme actif dans le meme sens.

## 2. Thales (Fable decideur)
Mesurer chaque signal pris contre chaque signal ecarte des qu'il y en a ; verifier que la lecture de la reponse de Fable fonctionne en reel (aucun « reponse illisible »).

## 3. T6 Recolteur
Phase papier a partir du 19/11 : suivre l'univers fige, les premiers trades papier et le verdict automatique apres 60 trades.

## 4. Optimisations (ACTIVEES, demande ecrite de Richard du 15/11/2026, 00 h 12 : « Let's go je te donne mon accord »)
Chaque point : code propre, tests, audit d'Aristote, annonce a Richard. Jamais de retouche des parametres de M2 pour coller au passe.
- 4a. Entree maker (priorite 1 apres l'etape 2) : le parent du lot normalTpsl devient un ordre limite Alo (post only) au meilleur prix
  de son cote (achat au bid, vente a l'ask), le stop reste dans le meme lot. Sans remplissage complet apres ENTRY_WAIT_S (defaut 60 s),
  annuler le reste et envoyer l'ordre IOC actuel pour le reliquat (stop ajuste a la taille totale). Si l'Alo est rejete (croise), IOC direct.
  Le signal ne doit jamais etre perdu. Variable ENTRY_MODE (maker ou taker, defaut taker) ajoutee a ENV_PERMIS par une modification de
  la constitution poussee AVANT le code. Valider d'abord par moon/essai.py sur Smart Peanut, puis activer maker sur les deux bots.
  Mesure : Diogene compare frais et glissement des entrees maker et taker dans son rapport du lundi.
- 4b. Contexte de Thales : ajouter au message envoye a Fable la tendance de BTC (EMA 50/200 4 h), le funding et sa moyenne 7 jours,
  le volume 24 h contre sa moyenne 30 jours, et le resultat des 5 derniers trades du bot. Aucune autre decision ne lui est donnee
  (sorties, taille et stop restent mecaniques). Garder le plafond de 40 appels par jour.
- 4c. Frequences en parallele : seulement apres le verdict de la priorite 1. Une frequence validee demande un sous-compte que Richard
  cree et alimente lui-meme ; Socrate lui ecrit alors les etapes exactes.
- 4d. Diversification : T6 ou toute nouvelle strategie seulement apres un verdict pre-enregistre positif (aucune exception).
- 4e. Suivi du risque releve : si Moonshot atteint 10 R de baisse depuis son plus haut a 2 %, Socrate revient a 1 % et previent Richard.
