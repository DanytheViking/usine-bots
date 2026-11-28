# Lab v9 : Duel (Smart Peanut)

Specification USINE-SPEC-LAB9 (sha256 9ad942b250854880d645442493992297fb9c225c2e4e2ff1886875e9a461a0a9), manifeste fa992428db51.

**NON CONCLUANT : 36 trades en evaluation (40 exiges), aucun seuil retouche**

Evaluation, frais doubles, deux positions au plus.

| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | funding moyen (R) | pire trade (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DUEL_4h | 36 | 0.09 | -0.393 | 0.581 | [-0.882 ; 0.194] | -0.387 | -0.911 | -0.424 | -0.021 | -1.991 | 14 | 24.490 | -0.009 | -0.024 | -0.056 | NE PASSE PAS : moins de 40 trades (36) ; esperance < +0.1 R (-0.393) ; croissance composee a 2 % non positive |
| M2_4h_temoin | 41 | 0.1 | -0.572 | 0.298 | [-0.821 ; -0.273] | 0.142 | -0.841 | -0.584 | -0.056 | -1.232 | 12 | 24.890 | -0.012 | -0.030 | -0.065 | NE PASSE PAS : esperance < +0.1 R (-0.572) ; croissance composee a 2 % non positive |

Correlation journaliere des resultats entre le Duel et M2 (evaluation) : -0.086

Actifs du jeu : AI16Z, AVAX, BOME, BRETT, BTC, CHILLGUY, DOGE, ETH, FARTCOIN, GOAT, GRIFFAIN, HPOS, HYPE, LIT, MELANIA, MEME, MEW, MOODENG, MYRO, NEAR, PENGU, PNUT, POPCAT, PUMP, SOL, SPX, TRUMP, TURBO, UNI, USELESS, VINE, WIF, XMR, XRP, ZEC, kBONK, kDOGS, kFLOKI, kNEIRO, kPEPE, kSHIB
