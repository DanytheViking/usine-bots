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
  FAIT dans le code (Gardien 2.4.0, commit 2dd6214, attend Aristote) : marge depassee -> taille reduite (code MARGIN), stop inchange ;
  reserve de liquidation gardee a 2 fois le stop (plus stricte que les 70 %) ; risque ouvert total <= 40 % (MAX_OPEN_RISK, code RISK_LIMIT :
  reduction puis refus) ; risque vise, risque reel avec frais, distances stop et liquidation, marge et plafonds journalises a chaque ordre.
  Mesure (tests, 74,41 USDC, 20 %, levier 5 au plus) : stop 5 % -> 297 $ et 59 $ de marge ; stop 3 % -> 334 $ au lieu de 496 (marge) ;
  avec une position pleine deja ouverte, la seconde est reduite a environ 37 $ : deux pleines positions a 20 % ne tiennent jamais dans 90 % de marge
  (l'estimation « stops a plus de 9 % » des revues externes etait fausse a ce levier). Une seule pleine position a la fois, en pratique.
- Voie rapide du Lab (durcie apres revues externes) : un challenger passe en reel sur le Lab des que (1) son pre-enregistrement est ecrit avant
  les donnees, (2) sur le holdout, en frais doubles, avec au moins 40 trades : esperance >= +0,10 R ET croissance composee positive au palier
  en cours (moyenne de ln(1 + f x R) > 0, f = risque par trade), (3) resultat encore positif sans ses 3 meilleurs trades ou publie si non,
  (4) les tests d'execution P0b passent. Pas de PF 1,35 ni de deux semaines de papier exigees au Lab.
  Abandon fixe a l'avance : -6 R cumules sur la strategie, ou esperance negative apres 30 trades reels (signal de suivi, verdict ecrit par Pyrrhon).
- Plusieurs strategies dans le meme Lab : un seul processus, une position par actif (le premier signal prend l'actif), risque ouvert total <= 40 % (deux positions au plus).
- Premieres experiences du Lab (revues externes) : (1) cassure apres compression (plage passee, filtre de liquidite executable, invalidation
  claire, peu de parametres), testable tout de suite sur les bougies ; (2) en parallele, etendre la collecte de T6 aux memecoins du Lab
  pour preparer les cascades de liquidations (donnees fines, test des que l'echantillon suffit) ; (3) reentree en tendance.
  (1 bis) idee de Richard du 15/11 : les deux grands poles, Asie et Etats-Unis. Pre-enregistrer, en variante de la cassure (1) et non en plus :
  plage de la seance asiatique (00 h a 08 h UTC), cassure pendant la seance americaine (ouverture 14 h 30 UTC en hiver, 13 h 30 UTC en ete),
  sortie avant la fin de seance ou au stop. En bougies 1 h ou 15 min, frais doubles, memes criteres de la voie rapide.
  Et dans le rapport P1a et le carnet du Lab : resultat de M2 et du Lab par seance (Asie, Europe, Etats-Unis) et volume par seance des memecoins.
  Funding et open interest d'abord comme variables de contexte. Repousses : nouveaux listings, retard BTC vers memecoins.
- Univers Lab : tous les memecoins Hyperliquid qui passent un controle de liquidite (spread et profondeur a notre taille), au lieu du seul volume de 2 M$.
  Bougies 1 h permises au Lab. Un actif sorti de l'univers reste suivi tant qu'une position ou un ordre existe.
- Cycle hebdomadaire du Lab : Democrite propose deux hypotheses, Pyrrhon les juge, Socrate deploie la meilleure, Diogene publie le bilan
  (signaux, trades, R, couts) ; Thales propose des hypotheses et son veto reste mesure (P1b).
- Lab v4 « furie » (demande ecrite de Richard du 16/11/2026, 16 h 55 UTC : « je veux que ce soit des tetes brulees du trading et qu'il trade sans peur,
  trouver une autre verticale si necessaire, Smart Peanut doit trader en fury » ; choix du 16/11, 16 h 57 : cassure + top movers) :
  pre-enregistrement usine/docs/PREREG-lab4-furie.md, spec USINE-SPEC-LAB4 ; quatre candidats (compression 1 h et 15 min, plage Asie / seance US 15 min,
  top movers 1 h), BTC, ETH, SOL, HYPE ajoutes aux memecoins. Travaux jobs/lab4-collecte-2026-11-16 (reseau) et lab4-verdicts-2026-11-16
  (attend le manifeste). Le candidat qui passe la voie rapide avec la meilleure croissance a 10 % est branche dans le bot (strategie par variable,
  avec tests), audite par Aristote, puis mis en reel au Lab. Si aucun ne passe : publier a Richard, rien en reel sans sa decision.
  16/11 18 h 10 UTC, verdict (manifeste 1c74e19ae816, rapport jobs/lab4-verdicts-2026-11-16) : AUCUN CANDIDAT NE PASSE. Evaluation, frais doubles,
  deux positions : compression 1 h -0,22 R (186 trades, 1,8 / jour), compression 15 min -0,19 R (180, 6,9 / jour), Asie / US -0,21 R (61, 2,3 / jour),
  top movers 1 h -0,14 R (354, 3,4 / jour) ; IC 95 % sous zero pour les deux compressions ; meme en frais de base, tous negatifs. Aucun parametre
  retouche. Rien en reel ; publie a Richard. Lecon : plus de frequence sur ces actifs = plus de pertes (confirme v1 P1 et les essais du 26/10).
- Etape 2 du Lab confirmee par Richard le 16/11/2026, 17 h 02 UTC, dans le fil du projet, mot pour mot :
  « Je confirme l'étape 2 du Lab : RISK_PER_TRADE 0.10, LINE_STOP 0.80, MAX_RISK_MIN_ORDER 0.20 pour smartpeanut2 ». Commit dedie, attend Aristote.
- Lab v5 (demande ecrite de Richard du 22/11/2026, 20 h 13 UTC : « passons sur strategie reel plus agressive » ; choix du 22/11, 20 h 16 :
  « Entree en tendance, 2 % », reel si le test n'est pas negatif, 74,41 USDC, arret a -80 %, apres audit) : constat, 2.6.0 sans trade depuis le 18/11
  (13 actifs en tendance baissiere, aucun croisement). Pre-enregistrement usine/docs/PREREG-lab5-tendance.md, spec USINE-SPEC-LAB5, jeu neuf m2t
  (travaux lab5-collecte-2026-11-22 et lab5-verdicts-2026-11-22).
  22/11 21 h 10 UTC, verdict (manifeste cf9a346e509a) : PASSE LA VOIE RAPIDE. Evaluation, frais doubles : 283 trades, 2,7 par jour, +0,42 R,
  PF 1,68 ; reserves : entrainement -0,19 R, IC [-0,15 ; +1,09], +0,02 R sans les 3 meilleurs trades, pire serie 23 pertes, baisse max 42 R
  (environ -57 % a 2 %), croissance composee negative a 10 %. Smart Peanut 2.7.0 (entree en tendance, 2 %) poussee, attend Aristote.
  Abandon fixe a l'avance : -6 R cumules ou esperance negative apres 30 trades reels.
  22/11 : 564f0a3 refuse par Aristote (204c513) : plafond de deux positions annonce a Richard mais absent du code et du test. Correction :
  MAX_POSITIONS = 2 pour smartpeanut2 (croisement et tendance, ordre de COINS), addendum PREREG-lab5b-plafond, spec USINE-SPEC-LAB5B,
  travail lab5b-verdicts-2026-11-22 sur le meme jeu m2t ; le verdict avec plafond decide de la mise en reel.
  22/11 22 h 20 UTC, verdict avec plafond (USINE-SPEC-LAB5B) : PASSE LA VOIE RAPIDE, 50 trades, 0,48 par jour, +0,20 R, PF 1,34 ;
  reserves : sans les 3 meilleurs -0,53 R (publie), entrainement -0,07 R, IC [-0,48 ; +1,05]. 00f4f4c approuve par Aristote, 2.7.0 deployee le 22/11 a 22 h 26 UTC.
  Premiers trades reels le 22/11 a 23 h 01 UTC : BTC short (stop 62712) et ETH short (stop 1761), 1,48 USDC de risque chacun. Abandon : -6 R ou esperance < 0 apres 30 trades.
- Nouvelle verticale HIP-3 (demande ecrite de Richard du 22/11/2026, 20 h 17 et 20 h 19 UTC : « Il y a t'il pas d'autre vertical a exploiter »,
  « trouve moi la meilleure solution ») : M2 inchange sur les 8 marches macro HIP-3 les plus liquides (or, indices, actions, hors crypto),
  frais de base HIP-3 = 2 x bareme validateur. Pre-enregistrement usine/docs/PREREG-hip3-m2.md, spec USINE-SPEC-HIP3, jeu neuf hip3
  (travaux hip3-collecte-2026-11-22 et hip3-verdicts-2026-11-22, relances en hip3b-collecte-2026-11-23 et hip3b-verdicts-2026-11-23 :
  la premiere copie de l'usine avait ete refusee pour une ligne de fin de test mal formee, les travaux avaient tourne sur l'ancien code). Recherche seulement : rien en reel sans accord ecrit de Richard sur le capital et les limites.
  23/11, verdict (hip3b-verdicts-2026-11-23) : ESPERANCE NEGATIVE. M2 1 h sur 8 marches HIP-3 : 95 trades, -0,32 R, PF 0,68 en frais doubles ;
  M2 4 h reconstruit : 19 trades, non concluant. M2 sur HIP-3 abandonne, sans nouveau reglage.
- Toujours interdit, meme au Lab : martingale, renforcement pour rattraper une perte, risque au-dela de 20 % par trade,
  code qui deplace des fonds.

## 0. Smart Peanut devient la « tete brulee » (demande ecrite de Richard du 14/11/2026, 23 h 43 : « Plus de trades et 3 % »)
- Etape 1 (commit du 14/11) : la constitution accepte 3 % de risque par trade pour Smart Peanut seulement (BOT_NAME smartpeanut2) ; Moonshot reste a 1 %.
- Etape 1 bis (commit du 15/11) : la constitution accepte aussi 2 % pour Moonshot (demande ecrite de Richard du 15/11/2026, 00 h 12 :
  « je te donne 100 % mon accord pour tester et monter le plafond si il le faut, je prends les responsabilites »).
- Etape 2 : Socrate la fait seulement quand la constitution qui tourne sur le VPS accepte les formes du Lab, sinon le commit serait refuse et
  bloquerait tout le depot jusqu'au commit suivant. Preuve attendue (depuis le commit b7be22b) : dans etat.json de la branche rapports, le champ
  « deployeur » cite l'empreinte de bornes.py ; elle doit valoir celle de deployeur/bornes.py sur main (sha256, 12 premiers caracteres :
  d2d5fcc4bd01 pour la version du 15/11 ; recalculer avec sha256sum apres tout nouveau commit de deployeur/). Avant b7be22b, le journal
  ne citait que l'empreinte de deployeur.py (7bc715ad904a, inchangee depuis le 13/11), donc les lignes du 14/11 23 h 30 et 23 h 40 ne prouvent rien.
  16/11 : preuve obtenue (etat.json du 16/11 09 h 10 : « deployeur.py 7bef2881a727, bornes.py d2d5fcc4bd01 »). Le passage automatique de Socrate n'a
  pas pu ecrire le relevement du risque (controle de securite de la session : relever un plafond de risque sur de l'argent reel demande une main humaine).
  Richard tranche : soit il confirme l'etape 2 dans une session en direct avec Socrate, soit il la commet lui-meme (trois lignes de config.py ci-dessus,
  deploy/env/peanut2.json avec RISK_PER_TRADE 0.10, LINE_STOP 0.80, MAX_RISK_MIN_ORDER 0.20, VERSION et images 2.5.0, test des trois plafonds), puis Aristote audite.
  Ancienne formulation (seulement APRES que deployeur.log montre « Deployeur mis a jour par le depot » pour le commit de l'etape 1 bis) :
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
- Moonshot, M2 en 1 h (demande de Richard du 16/11/2026, 17 h 02 : « Moonshot ne trade pas assez » ; choix du 16/11, 17 h 09 : test 1 h
  et reprise d'un candidat du Lab v4 en parallele) : pre-enregistrement usine/docs/PREREG-moonshot-m2-1h.md, spec USINE-SPEC-M2H1, 13 actifs
  de Moonshot en 1 h, PF >= 1,35, leave-one-asset-out ; M2 4 h reconstruit publie pour comparer. Travaux jobs/m2h1-collecte-2026-11-16 et
  m2h1-verdicts-2026-11-16. Si AVANTAGE : papier deux semaines puis sous-compte (4c). Aucun risque releve par ce test.
  Si un candidat du Lab v4 passe, le pre-enregistrer separement pour Moonshot (actifs de Moonshot, criteres de Moonshot, pas la voie rapide du Lab).
- Plusieurs frequences en meme temps (demande de Richard du 14/11) : Hyperliquid n'a qu'une position par actif et par compte, donc
  chaque frequence validee tourne comme une instance separee du meme code (frequence et compte par variables), sur son propre
  sous-compte. Le versement vers le sous-compte est fait par Richard (le code ne deplace jamais de fonds). Risque : 1 % par trade
  et par sous-compte ; Epictete surveille l'exposition cumulee quand deux frequences prennent le meme actif dans le meme sens.

## 2. Thales (le decideur)
Mesurer chaque signal pris contre chaque signal ecarte des qu'il y en a ; verifier que la lecture de la reponse de Thales fonctionne en reel (aucun « reponse illisible »).
16/11 : lecture verifiee en reel (kPEPE short du 15/11 12 h, Fable, « eviter » a 62 et 63 %, les deux bots ; aucun « illisible » depuis la 2.4.0).
Manque : les signaux ecartes ne sont pas suivis (Democrite n'apparie que les trades fermes). A ecrire : suivi papier des signaux ecartes
(entree au prix de reference, stop 3 ATR, sortie au croisement inverse ou au stop, sur les bougies) pour comparer pris et ecartes a nombre egal.
Remarques d'Aristote (audit 9253975) a traiter : Democrite mesure separement les avis de Fable et ceux du secours (champ modele) ;
un signal peut couter deux appels payants alors que le plafond journalier n'en compte qu'un (compter les deux).

23/11 : Thales sans avis sur ETH short (22/11, 23 h 02) : reponse 200 de Fable 5.2 sans texte, la reflexion avait pris les 1000 jetons, et le secours
n'etait pas essaye. 2.7.1 (9b08cdc, attend Aristote) : 8000 jetons, une reponse sans avis lisible passe au secours, cause journalisee (champ fin) ; meme chose pour Democrite.

## 3. T6 Recolteur
Phase papier a partir du 19/11 : suivre l'univers fige, les premiers trades papier et le verdict automatique apres 60 trades.
16/11 : phase mesure, 5 cascades vues (toutes refusees « phase mesure »), 23 actifs prets, 0 trade papier.
23/11 : phase papier, 23 trades, PF net 0,69, PF stress 0,44, equite papier 99,48. Verdict automatique a 60 trades (abandon si PF frais x3 < 1,2) : la tendance est a l'abandon.

## Incidents traites
- 16/11 : controle du lundi de Diogene (controle-2026-s47) en echec : l'image Docker usine-py:1 manquait sur le VPS (jamais construite par le
  Deployeur, ou effacee). Deployeur : l'image est construite depuis /root/usine quand elle manque, avant chaque travail usine et chaque controle ;
  un controle en echec est rejoue au passage suivant (trois essais) ; un echec de construction est journalise. Attend Aristote.
- 16/11 : bilan de Democrite du 15/11 coupe au milieu de la troisieme proposition (1500 jetons) : 2500 jetons, 600 mots, deux hypotheses Lab exigees.

## P0 (15/11/2026, apres revue externe) : avant tout relevement de Moonshot a 2 % et avant l'entree maker
Smart Peanut passe a 3 % comme prevu (etape 2) ; la ligne Moonshot de l'etape 2 reste a 0.01 dans deploy/env/moonshot2.json tant que P0a et P0b ne sont pas termines et audites.
17/11/2026 : Moonshot a 5 % (confirmation ecrite de Richard du 16/11, 23 h 08 UTC ; constitution 4bd6da2 approuvee, etape 2 Moonshot 2.5.1).
  P0b fait pour le coeur du risque (stop seul a la taille reelle apres remplissage partiel ou stop rejete, deux essais, sinon sortie sure) ;
  garde-fou de 10 R automatique et verrouille (retour a 1 %, message, levee seulement sur decision ecrite de Richard).
- P0a. Parcours des signaux : chaque cloture et chaque actif suivi produit une ligne de journal avec un code stable
  (NO_SIGNAL, STALE_DATA, VOLUME_FILTER, MIN_ORDER, RISK_LIMIT, AI_VETO, ORDER_REJECTED, NOT_FILLED, EXECUTED) et les valeurs utilisees
  (EMA 50, EMA 200, ATR, volume 24 h, taille avant et apres arrondi, marge requise). Bilan hebdomadaire « X signaux, Y exclusions, Z ordres, N executions »
  publie par Diogene. Reconstituer aussi le passe de Smart Peanut depuis le 12/11 a partir des bougies (memes regles), pour prouver ou refuter « le silence est normal ».
  Un actif sorti du filtre de volume reste suivi tant qu'une position ou un ordre existe (verifier et tester).
  FAIT dans le code (2.4.0, commit 2dd6214) : codes stables dans data/parcours.jsonl (fichier simple, le journal chaine garde les decisions),
  valeurs EMA 50 / 200, ATR, volume 24 h, taille brute et arrondie, marge ; moon.journal.bilan_parcours() donne les comptes ; le Deployeur publie
  les 400 dernieres lignes (rapports : parcours-<bot>.jsonl). Un actif sorti du filtre est suivi jusqu'a sa sortie, sans retournement (teste).
  RESTE : bilan hebdomadaire publie par Diogene (lire parcours.jsonl dans le travail controle) ; reconstitution du passe de Smart Peanut depuis le 12/11
  (travail usine a ecrire : memes regles sur les bougies, resultat par actif et par cloture).
- P0b. FAIT pour le coeur (Moonshot 2.5.1) : apres le lot, si le stop manque (remplissage partiel, stop rejete), stop reduce-only seul a la taille
  reelle au meme prix, confirme au carnet, deux essais, sinon sortie sure ; risque et taille enregistres au prorata du remplissage. Tests : entree
  complete, partielle, stop rejete, stop seul refuse, reponse perdue (KILL). RESTE pour l'entree maker : Alo vers IOC apres 60 s avec fills
  pendant l'annulation, reliquats sous 10 $, reponse inconnue sans doublon, limites d'API partagees, retournement partiel.
- P0b. Remplissage partiel : la documentation Hyperliquid dit que si un ordre parent partiellement rempli est annule, ses TP/SL enfants sont annules aussi,
  et que les enfants ont la taille du parent. Un IOC partiel annule son reliquat : aujourd'hui le broker detecte l'absence de stop et ferme la position
  (sur, mais le trade est perdu). Corriger : apres le lot, lire la position reelle ; si un stop manque, poser un stop reduce-only seul a la taille reelle,
  verifier sa presence, et ne fermer qu'en cas d'echec. Tests des scenarios : entree complete, partielle, stop rejete, reponse perdue apres remplissage,
  redemarrage avec position, retournement partiel, ancien stop present ; plus (revues externes) : Alo vers IOC apres 60 s en reconciliant les fills
  survenus pendant l'annulation (n'envoyer que le reliquat reel), petits reliquats sous le minimum de 10 $, reponse inconnue sans doublon,
  limites de l'API partagees par les deux bots et les agents sur l'IP du VPS (garder de la capacite pour les stops), effet du funding horaire
  sur la marge isolee. Verifier chaque statut reel de l'API, sans generaliser. Les stops se declenchent sur le mark price : le verifier dans le simulateur.
- P0c. Configuration effective : chaque decision d'ordre journalise le risque cible, le risque reel apres arrondi (frais d'entree et de sortie inclus) et les plafonds actifs.
  FAIT (2.4.0, commit 2dd6214) : etape « risque » du journal avant chaque ordre, avec risk_target, risk, risk_frais, dist_stop, dist_liq, marge et plafonds.

## P1 et P2 (15/11/2026, retenus des deux revues externes ; ordre fixe)
- P1a. Reference M2 figee : rapport recalculable depuis les donnees et le commit : nombre de trades et duree, esperance nette en R et en $,
  PF avec definition des couts, drawdown et duree de recuperation, resultat par actif, par sens, par periode et par regime,
  part des gains venant des 5 meilleurs trades, resultat sans le meilleur actif et sans les meilleurs gagnants. Dire si les 13 actifs
  ont ete choisis avant les tests (lire l'historique des pre-enregistrements). Verifier que les stops du simulateur suivent le mark price.
- P1b. Mesure de Thales : archiver pour chaque signal modele, prompt, donnees, reponse, latence, score de confiance et decision ; suivre
  en parallele la strategie mecanique seule et un filtre deterministe simple avec les memes donnees. Bilan apres 30 signaux ;
  le veto de Thales sur Smart Peanut est garde seulement s'il ameliore le resultat net ou le drawdown.
- P1c. Tableau de bord des couts : resultat brut, net de trading, funding, frais d'execution, et couts fixes (VPS, appels de Thales et Democrite au modele) separes.
- P1d. Eratosthene, le Collecteur de sources (demande de Richard du 15/11/2026, 00 h 55 : « connecte-le sur l'ouverture asiatique et americaine,
  sur toutes les sources possibles »). Nouveau conteneur sans cle ni IA, qui ne trade pas : il collecte et publie un fichier de contexte
  (/opt/collecteur/data/contexte.json, mis a jour toutes les 5 minutes) et un historique quotidien pour la recherche. APIs publiques seulement,
  dans le respect de leurs conditions d'usage, aucune donnee privee. Sources, dans cet ordre :
  1. Horloge des seances : Asie (Tokyo 00 h UTC, Hong Kong et Singapour 01 h 30 UTC), Europe (08 h UTC), Etats-Unis (14 h 30 UTC en hiver,
     13 h 30 en ete, jours feries de la bourse de New York), avec la seance en cours et le temps avant la prochaine ouverture.
  2. Prime Coinbase (prix BTC et ETH sur Coinbase contre Binance) : demande americaine ; prime coreenne (Upbit contre Binance) : demande asiatique,
     aussi par memecoin quand il est cote en Coree.
  3. Funding, open interest et liquidations sur Binance, Bybit et OKX pour nos actifs (en plus d'Hyperliquid).
  4. Indices actions et risque : contrats a terme S&P 500 et Nasdaq, Nikkei, Hang Seng, VIX, dollar (DXY), si une source gratuite et stable existe.
  5. Calendrier macro (decisions de la Fed, inflation americaine, emploi) : heure et importance.
  6. Memecoins sur les DEX (volume et liquidite des memecoins sur Solana et Base) comme indicateur de la mode du moment.
  Regles : chaque source a un controle de fraicheur ; une source en panne ne bloque jamais un bot (le champ est marque absent).
  Usage : d'abord comme contexte pour Thales (avis plus informe) et comme donnees pour Democrite ; une source devient un filtre ou un signal
  de trading seulement apres un verdict pre-enregistre (pas plus de sources que de preuves). Constitution : ajouter /opt/collecteur aux
  destinations dans un commit de deployeur/ AVANT le code (audit d'Aristote). Tableau de bord : onglet « Monde » (seance en cours, primes, funding, macro).
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
- 4b. Contexte de Thales : ajouter au message envoye a Thales la tendance de BTC (EMA 50/200 4 h), le funding et sa moyenne 7 jours,
  le volume 24 h contre sa moyenne 30 jours, et le resultat des 5 derniers trades du bot. Aucune autre decision ne lui est donnee
  (sorties, taille et stop restent mecaniques). Garder le plafond de 40 appels par jour.
- 4c. Frequences en parallele : seulement apres le verdict de la priorite 1. Une frequence validee demande un sous-compte que Richard
  cree et alimente lui-meme ; Socrate lui ecrit alors les etapes exactes.
- 4d. Diversification : T6 ou toute nouvelle strategie seulement apres un verdict pre-enregistre positif (aucune exception).
- 4e. Suivi du risque releve : si Moonshot atteint 10 R de baisse depuis son plus haut a 2 %, Socrate revient a 1 % et previent Richard.
