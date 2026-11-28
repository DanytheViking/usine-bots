# Lab v8 : Tendance 4 h confirmee (Smart Peanut)

Specification USINE-SPEC-LAB8 (sha256 d94ace7131634907aa72a006830efceadf8be706c8ceaf1185d3bbff59a9ecec), manifeste 078e5bffb4ed.

**NON CONCLUANT : 39 trades en evaluation (40 exiges), aucun seuil retouche**

Evaluation, frais doubles, deux positions au plus.

| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T4H_confirmee | 39 | 0.09 | 0.330 | 1.434 | [-0.314 ; 1.095] | 0.164 | -0.246 | 0.311 | 8 | 8.359 | 0.005 | 0.009 | 0.006 | NE PASSE PAS : moins de 40 trades (39) |
| T4H_tendance | 47 | 0.11 | 0.669 | 2.129 | [-0.253 ; 1.959] | 0.617 | -0.204 | 0.652 | 8 | 10.074 | 0.010 | 0.018 | 0.020 | PASSE LA VOIE RAPIDE |
| M2_4h_croisement | 35 | 0.08 | 0.084 | 1.109 | [-0.553 ; 0.809] | 0.107 | -0.514 | 0.068 | 11 | 15.189 | 0.001 | -0.002 | -0.014 | NE PASSE PAS : moins de 40 trades (35) ; esperance < +0.1 R (0.084) |

Actifs du jeu : AVAX, BTC, ETH, HYPE, LIT, NEAR, PUMP, SOL, UNI, XMR, XRP, ZEC, kPEPE
