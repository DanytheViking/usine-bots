# Priorites de l'equipe (fixees le 14/11/2026, mises a jour le 15/11/2026)

Socrate lit ce fichier a chaque passage et le met a jour quand une priorite est traitee.

## LAB : mandat de Smart Peanut (demande ecrite de Richard du 15/11/2026, 00 h 31)
« Smart Peanut est un projet Lab ; si on perd le capital de 74 $ ce n'est pas grave ; je veux un bot ultra intelligent et producteur qui prend des risques,
avec l'equipe en mode tete brulee, juste pour Smart Peanut. »
- Enveloppe : le seul compte Labo (0x69Dc...7180, 74,41 USDC). Aucun versement automatique, aucun effet sur Moonshot (compte et cle separes).
  Perdre l'enveloppe est accepte. Moonshot garde toutes les regles prudentes.
- Bornes Lab (constitution du 15/11) : 20 % par trade (choix ecrit de Richard du 15/11, 00 h 32 : « rock'n'roll and all in », « 20 % par trade »),
  20 % au plus aussi quand l'ordre minimum l'impose, arret de ligne a -80 % (environ 7 pertes de suite), 30 R / 20 pertes inchanges.
  Etape 2 : dans config.py, RISK_PER_TRADE = min(_f("RISK_PER_TRADE", "0.01"), 0.20 if NAME == "smartpeanut2" else 0.02), LINE_STOP = min(_f("LINE_STOP", "0.50"), 0.80 if NAME == "smartpeanut2" else 0.50) et
  MAX_RISK_MIN_ORDER = min(_f("MAX_RISK_MIN_ORDER", "0.015"), 0.20 if NAME == "smartpeanut2" else 0.015) ;
  deploy/env/peanut2.json : RISK_PER_TRADE 0.10, LINE_STOP 0.80, MAX_RISK_MIN_ORDER 0.20 (palier 1, voir ci-dessous). Cette etape remplace la ligne a 3 % de l'etape 2 ci-dessous.
  Avec 20 %, la taille reste limitee par le levier 5 isole et la marge 90 % : si le stop est trop proche, la taille est reduite (jamais le stop deplace). Tests et audit.
- Paliers (choix ecrit de Richard du 15/11/2026, 00 h 40, apres deux revues externes) : plafond 20 %, mais
  palier 1 = 10 % par trade pour les 15 premiers trades reels du Lab ; palier 2 = 15 % ; palier 3 = 20 %. On monte d'un palier seulement si,
  sur le palier en cours : chaque trade a eu son stop confirme, aucun ecart d'execution non explique (taille, prix, stop), glissement moyen
  mesure et publie. Jamais de montee pour se refaire apres une perte. Socrate change la valeur dans deploy/env/peanut2.json, Aristote audite.
- Risque reellement executable (revue externe) : avant chaque ordre du Lab, le bot calcule le notionnel = risque / distance au stop, la marge
  au levier choisi, et refuse ou reduit si (a) la marge totale depasserait 90 % du capital, ou (b) le prix de liquidation est plus proche que
  le stop avec une reserve (stop a moins de 70 % de la distance de liquidation). En cas de (b) : baisser le levier si la marge le permet,
  sinon reduire la taille ; le stop ne bouge jamais. Journaliser risque vise, risque reel et distance stop / liquidation (code RISK_LIMIT ou LIQ_GUARD).
  Deux positions a 20 % ne sont possibles que si les stops sont a plus d'environ 9 % : sinon une seule position a la fois. Tests chiffres.
- Voie rapide du Lab (durcie apres revues externes) : un challenger passe en reel sur le Lab des que (1) son pre-enregistrement est ecrit avant
  les donnees, (2) sur le holdout, en frais doubles, avec au moins 40 trades : esperance >= +0,10 R ET croissance composee positive au palier
  en cours (moyenne de ln(1 + f x R) > 0, f = risque par trade), (3) resultat encore positif sans ses 3 meilleurs trades ou publie si non,
  (4) les tests d'execution P0b passent. Pas de PF 1,35 ni de deux semaines de papier exigees au Lab.
  Abandon fixe a l'avance : -6 R cumules sur la strategie, ou esperance negative apres 30 trades reels (signal de suivi, verdict ecrit par Pyrrhon).
- Plusieurs strategies dans le meme Lab : un seul processus, une position par actif (le premier signal prend l'actif), risque ouvert total <= 40 % (deux positions au plus).
- Premieres experiences du Lab (revues externes) : (1) cassure apres compression (plage passee, filtre de liquidite executable, invalidation
  claire, peu de parametres), testable tout de suite sur les bougies ; (2) en parallele, etendre la collecte de T6 aux memecoins du Lab
  pour preparer les cascades de liquidations (donnees fines, test des que l'echantillon suffit) ; (3) reentree en tendance.
  Funding et open interest d'abord comme variables de contexte. Repousses : nouveaux listings, effets horaires, retard BTC vers memecoins.
- Univers Lab : tous les memecoins Hyperliquid qui passent un controle de liquidite (spread et profondeur a notre taille), au lieu du seul volume de 2 M$.
  Bougies 1 h permises au Lab. Un actif sorti de l'univers reste suivi tant qu'une position ou un ordre existe.
- Cycle hebdomadaire du Lab : Democrite propose deux hypotheses, Pyrrhon les juge, Socrate deploie la meilleure, Diogene publie le bilan
  (signaux, trades, R, couts) ; Thales propose des hypotheses et son veto reste mesure (P1b).
- Toujours interdit, meme au Lab : martingale, renforcement pour rattraper une perte, risque au-dela de 20 % par trade,
  code qui deplace des fonds.

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

## P0 (15/11/2026, apres revue externe) : avant tout relevement de Moonshot a 2 % et avant l'entree maker
Smart Peanut passe a 3 % comme prevu (etape 2) ; la ligne Moonshot de l'etape 2 reste a 0.01 dans deploy/env/moonshot2.json tant que P0a et P0b ne sont pas termines et audites.
- P0a. Parcours des signaux : chaque cloture et chaque actif suivi produit une ligne de journal avec un code stable
  (NO_SIGNAL, STALE_DATA, VOLUME_FILTER, MIN_ORDER, RISK_LIMIT, AI_VETO, ORDER_REJECTED, NOT_FILLED, EXECUTED) et les valeurs utilisees
  (EMA 50, EMA 200, ATR, volume 24 h, taille avant et apres arrondi, marge requise). Bilan hebdomadaire « X signaux, Y exclusions, Z ordres, N executions »
  publie par Diogene. Reconstituer aussi le passe de Smart Peanut depuis le 12/11 a partir des bougies (memes regles), pour prouver ou refuter « le silence est normal ».
  Un actif sorti du filtre de volume reste suivi tant qu'une position ou un ordre existe (verifier et tester).
- P0b. Remplissage partiel : la documentation Hyperliquid dit que si un ordre parent partiellement rempli est annule, ses TP/SL enfants sont annules aussi,
  et que les enfants ont la taille du parent. Un IOC partiel annule son reliquat : aujourd'hui le broker detecte l'absence de stop et ferme la position
  (sur, mais le trade est perdu). Corriger : apres le lot, lire la position reelle ; si un stop manque, poser un stop reduce-only seul a la taille reelle,
  verifier sa presence, et ne fermer qu'en cas d'echec. Tests des scenarios : entree complete, partielle, stop rejete, reponse perdue apres remplissage,
  redemarrage avec position, retournement partiel, ancien stop present ; plus (revues externes) : Alo vers IOC apres 60 s en reconciliant les fills
  survenus pendant l'annulation (n'envoyer que le reliquat reel), petits reliquats sous le minimum de 10 $, reponse inconnue sans doublon,
  limites de l'API partagees par les deux bots et les agents sur l'IP du VPS (garder de la capacite pour les stops), effet du funding horaire
  sur la marge isolee. Verifier chaque statut reel de l'API, sans generaliser. Les stops se declenchent sur le mark price : le verifier dans le simulateur.
- P0c. Configuration effective : chaque decision d'ordre journalise le risque cible, le risque reel apres arrondi (frais d'entree et de sortie inclus) et les plafonds actifs.

## P1 et P2 (15/11/2026, retenus des deux revues externes ; ordre fixe)
- P1a. Reference M2 figee : rapport recalculable depuis les donnees et le commit : nombre de trades et duree, esperance nette en R et en $,
  PF avec definition des couts, drawdown et duree de recuperation, resultat par actif, par sens, par periode et par regime,
  part des gains venant des 5 meilleurs trades, resultat sans le meilleur actif et sans les meilleurs gagnants. Dire si les 13 actifs
  ont ete choisis avant les tests (lire l'historique des pre-enregistrements). Verifier que les stops du simulateur suivent le mark price.
- P1b. Mesure de Thales : archiver pour chaque signal modele, prompt, donnees, reponse, latence, score de confiance et decision ; suivre
  en parallele la strategie mecanique seule et un filtre deterministe simple avec les memes donnees. Bilan apres 30 signaux ;
  le veto de Thales sur Smart Peanut est garde seulement s'il ameliore le resultat net ou le drawdown.
- P1c. Tableau de bord des couts : resultat brut, net de trading, funding, frais d'execution, et couts fixes (VPS, appels a Fable) separes.
- P2a. Trois challengers Smart Peanut, pre-enregistres AVANT les donnees, peu de parametres, testes separement, frais doubles :
  tendance avec reentree bornee, cassure apres consolidation (avec liquidite minimale), continuation de momentum (duree maximale).
  Chacun passe d'abord en observation parallele (sans capital), puis en reel limite seulement s'il remplit ses criteres.
- P2b. Sorties : comparer sur la reference M2 croisement inverse, stop suiveur ATR, sortie temporelle, prise partielle. Aucune adoption sans verdict.
- P2c. Enveloppe Smart Peanut : profils de risque (1, 2, 3 %) simules sur le portefeuille complet (pertes correlees, stops depasses, couts x 2),
  probabilites presentees comme des estimations du modele.
- Refuse : scale-in, martingale, assouplissement des arrets (pertes de suite, R de baisse), risque au-dela des plafonds actuels,
  parametres de sortie choisis sans test.

## 4. Optimisations (ACTIVEES, demande ecrite de Richard du 15/11/2026, 00 h 12 : « Let's go je te donne mon accord »)
Chaque point : code propre, tests, audit d'Aristote, annonce a Richard. Jamais de retouche des parametres de M2 pour coller au passe.
- 4a. Entree maker (priorite 1 apres l'etape 2) : le parent du lot normalTpsl devient un ordre limite Alo (post only) au meilleur prix
  de son cote (achat au bid, vente a l'ask), le stop reste dans le meme lot. Sans remplissage complet apres ENTRY_WAIT_S (defaut 60 s),
  annuler le reste (ce qui annule aussi les enfants TP/SL : poser alors un stop seul a la taille reelle, comme en P0b) et envoyer un IOC pour le reliquat.
  Prerequis : P0b termine. Le gain de l'entree maker est mesure en reel (ordres non remplis compris), jamais suppose. Si l'Alo est rejete (croise), IOC direct.
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
