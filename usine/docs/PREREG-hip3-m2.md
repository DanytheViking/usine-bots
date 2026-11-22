# Pre-enregistrement : M2 sur les marches macro de Hyperliquid (HIP-3), 22/11/2026

Ecrit avant toute collecte et tout calcul. Demande de Richard du 22/11/2026 (20 h 17 UTC) : « Il y a t'il pas d'autre vertical a exploiter
comme bot de trading », puis (20 h 19 UTC) : « Ok regarde trouve moi la meilleure solution ». Contexte : les 13 actifs de Moonshot baissent
ensemble, Smart Peanut ne trouve plus de signal. Idee testee : les marches HIP-3 (or, argent, petrole, indices, actions) suivent des tendances
qui ne dependent pas des cryptos. Les parametres de M2 sont figes depuis le catalogue v1 et ne sont pas modifies.
Ce test ne met rien en reel : un passage en reel demande l'accord ecrit de Richard sur le capital et les limites.

## Donnees (jeu hip3, collecte neuve)
- Endpoints publics Hyperliquid, aucune cle : perpDexs, metaAndAssetCtxs de chaque dex HIP-3, candleSnapshot, fundingHistory.
- Fin figee a l'heure pleine du lancement. Bougies 1 h (5000 au plus, environ 208 jours) et funding reel sur la fenetre.
- Coupe au milieu de la fenetre (entrainement, puis evaluation). Trades a cheval exclus.

## Univers (regle fixe, appliquee par le collecteur)
1. Tous les marches de tous les dex HIP-3, hors marches delistes.
2. Exclus : les sous-jacents crypto, c'est a dire les marches dont le nom sans prefixe de dex (et sans k ou 1000 en tete) est aussi un perp validateur.
3. Un seul marche par sous-jacent : celui au plus gros volume notionnel sur 24 h (dayNtlVlm) au moment de la collecte.
4. Classement par volume notionnel 24 h ; bougies 1 h des 20 premiers ; on garde dans l'ordre les 8 premiers qui ont au moins 2000 bougies 1 h.
Reserve assumee : le classement par volume actuel favorise les marches qui ont survecu (leger biais de survie). La liste, les volumes et le
nombre de bougies de chaque marche sont publies dans le manifeste.

## Frais
- La simulation commune paie le bareme validateur (taker 0,045 %, stop avec glissement 0,05 %).
- Les marches HIP-3 peuvent couter plus cher (part du deployeur). Hypothese prudente figee : frais de base HIP-3 = 2 fois le bareme validateur.
  Le scenario « frais doubles » du Testeur vaut donc 4 fois le bareme validateur, le stress « frais x 3 » 6 fois.
- Les champs de frais publies par perpDexs et le meta sont copies dans le manifeste, pour information.

## Candidats (figes)
- M2_1h_hip3 (decisif) : croisement EMA 50 / 200 sur bougies 1 h closes, stop initial 3 x ATR(14) 1 h, sortie et retournement au croisement
  inverse, longs et shorts, entree taker a l'ouverture suivante, funding reel (simulation commune usine.sim). Une position par marche.
- M2_4h_reconstruit (information) : le meme M2 sur des bougies 4 h agregees depuis les memes bougies 1 h.
- Publies : trades par mois, stress frais x 3, acheter et garder, retrait de chaque marche a tour de role, pire serie de pertes,
  correlation des resultats journaliers de M2_1h_hip3 avec ceux de M2 1 h sur BTC du meme jeu (si BTC est collecte : information seulement).

## Criteres (evaluation), ceux du test M2 1 h de Moonshot
- au moins 30 trades ;
- PF >= 1,35 en frais de base et esperance > 0 en frais doubles ;
- borne basse de l'intervalle de confiance a 5 % de l'esperance en frais doubles > 0, blocs de jours, sur au moins 7 jours ;
- esperance d'entrainement > 0 ;
- l'avantage ne depend d'aucun marche seul (retrait de chaque marche a tour de role).

## Regle de decision
- AVANTAGE : adapter le bot aux marches HIP-3 (index d'actif des dex HIP-3, tests), papier deux semaines, puis proposition chiffree a Richard
  (capital, risque, limites). Rien en reel sans son accord ecrit.
- Esperance >= 0 sans avantage demontre : rien en reel sur la foi de ce test ; Richard reste libre d'une exception ecrite.
- Esperance < 0 : M2 sur HIP-3 est abandonne, sans nouveau reglage.
