# Lab v6 : Furie Momentum (Smart Peanut)

Specification USINE-SPEC-LAB6 (sha256 909b1c93cb62d3262f3a6ebb6ed1f5e0adbb3914a2a75b5b424128e7241f135d), manifeste 99f9d0933877.

**NE PASSE PAS LA VOIE RAPIDE : rien en reel, M2T reste en reel**

Evaluation, frais doubles, deux positions au plus.

| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FM_1h_furie | 136 | 1.31 | 0.100 | 1.223 | [-0.197 ; 0.466] | 0.008 | -0.220 | 0.067 | 16 | 25.922 | 0.001 | -0.000 | -0.007 | NE PASSE PAS : esperance < +0.1 R (0.100) |
| FM_1h_pyramide | 138 | 1.32 | 0.098 | 1.214 | [-0.199 ; 0.465] | 0.049 | -0.217 | 0.066 | 12 | 24.522 | 0.001 | -0.000 | -0.007 | NE PASSE PAS : esperance < +0.1 R (0.098) |
| M2T_1h_tendance | 49 | 0.47 | 0.199 | 1.322 | [-0.523 ; 1.073] | -0.353 | -0.545 | 0.163 | 5 | 11.559 | 0.002 | 0.001 | -0.010 | PASSE LA VOIE RAPIDE |

Actifs du jeu : AVAX, BTC, ETH, HYPE, LIT, NEAR, PUMP, SOL, UNI, XMR, XRP, ZEC, kPEPE
