# Lab v7 : Portage (Smart Peanut)

Specification USINE-SPEC-LAB7 (sha256 3ffbeed616f4e3d6f5f188ef7108ecc96d1dbc4b8541391c81627f20d736011a), manifeste 6767ec7f169e.

**NON CONCLUANT : 33 trades en evaluation (40 exiges), aucun seuil retouche**

Evaluation, frais doubles, deux positions au plus.

| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | funding moyen (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PORTAGE_1h | 33 | 0.32 | -0.002 | 0.997 | [-0.445 ; 0.531] | -0.448 | -0.465 | -0.018 | 0.053 | 4 | 9.742 | -0.001 | -0.003 | -0.012 | NE PASSE PAS : moins de 40 trades (33) ; esperance < +0.1 R (-0.002) ; croissance composee a 2 % non positive |
| PORTAGE_1h_sans_ema | 40 | 0.38 | 0.181 | 1.403 | [-0.158 ; 0.553] | -0.250 | -0.078 | 0.165 | 0.057 | 4 | 3.973 | 0.003 | 0.007 | 0.010 | PASSE LA VOIE RAPIDE |

Actifs du jeu : AVAX, BOME, BRETT, BTC, CHILLGUY, DOGE, ETH, FARTCOIN, GOAT, GRIFFAIN, HYPE, LIT, MELANIA, MEME, MEW, MOODENG, NEAR, PENGU, PNUT, POPCAT, PUMP, SOL, SPX, TRUMP, TURBO, UNI, USELESS, VINE, WIF, XMR, XRP, ZEC, kBONK, kFLOKI, kNEIRO, kPEPE, kSHIB
