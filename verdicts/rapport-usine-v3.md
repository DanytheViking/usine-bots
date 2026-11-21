# Usine : verdicts du catalogue v3 (Team Chasseur)

Resultats indicatifs sur donnees passees. Aucune optimisation : parametres figes par le pre-enregistrement.

## Empreintes (sha256)
- specification : `9dbec2db41927418d41ee6fc2046145a998e16800b958f17e1b9d5a47f99ed87`
- sim.py : `a61ee96493d2605c1e675caa90f34cf13643901500cde1f8544bc9999d6f58b9`
- strategies.py : `bd859fa8f58985b348e0dd6e7296e12291b56191bb876ad212554b86c5b811df`
- strategies_v3.py : `b51655455011970d38c2dc08137bde7745d040a300a0f8f2c2c3a98b5dc4b1f7`
- verdicts.py : `76db738821471fabf99cae5c30ed99d8d0d0f8b38002d294ef024749f0eba811`
- verdicts_v3.py : `bc2f1222a3319a08dec5b849219a3d3f8276fcc09864e4684637572fe888eb1f`
- manifeste_v3 : `4b5f27a5a70a2451142699ed0ad7d46a630c3cf3fdb6353263be429e7b27bfa2`

## Verdicts (evaluation, criteres annonces)

- **T1_tortue** : PAS D'AVANTAGE : PF évaluation ≥ 1.35 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) (coupe 2025-09-21T20:00Z, fenetre 2024-08-01 au 2026-11-12)
- **T2_tortue_disciplinee** : PAS D'AVANTAGE : PF évaluation ≥ 1.35 ; IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) (coupe 2025-09-21T20:00Z, fenetre 2024-08-01 au 2026-11-12)
- **T3_druckenmiller** : PAS D'AVANTAGE : PF évaluation ≥ 1.35 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-21T20:00Z, fenetre 2024-08-01 au 2026-11-12)
- **T4_contrarien** : NON CONCLUANT (moins de 30 trades en évaluation) (coupe 2026-07-31T08:00Z, fenetre 2026-04-18 au 2026-11-12)
- **T5_listings** : NON CONCLUANT (moins de 30 trades en évaluation) (coupe 2026-07-31T08:00Z, fenetre 2026-04-18 au 2026-11-12)
- **ne_rien_trader** : reference (0 R, aucun frais, aucun risque)

## entrainement : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| T1_tortue | 909 | 0.278 | 0.972 | -0.018 | -16.546 | 51 | 110.223 | -22.318 | 11.136 |
| T2_tortue_disciplinee | 480 | 0.215 | 0.952 | -0.036 | -17.438 | 52 | 137.984 | -22.481 | 6.375 |
| T3_druckenmiller | 48 | 0.438 | 1.556 | 0.262 | 12.579 | 3 | 5.341 | -1.103 | 0.454 |
| T4_contrarien | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| T5_listings | 3 | 0.333 | 0.824 | -0.118 | -0.355 | 1 | 1.013 | -0.086 | 0.042 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## entrainement : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| T1_tortue | 909 | 0.274 | 0.955 | -0.030 | -27.683 | 51 | 115.735 | -22.318 | 22.272 |
| T2_tortue_disciplinee | 480 | 0.210 | 0.936 | -0.050 | -23.813 | 52 | 140.965 | -22.481 | 12.750 |
| T3_druckenmiller | 48 | 0.438 | 1.528 | 0.253 | 12.125 | 3 | 5.393 | -1.103 | 0.908 |
| T4_contrarien | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| T5_listings | 3 | 0.333 | 0.804 | -0.132 | -0.397 | 1 | 1.017 | -0.086 | 0.083 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| T1_tortue | 972 | 0.275 | 0.909 | -0.063 | -60.869 | 41 | 263.516 | -17.585 | 16.527 |
| T2_tortue_disciplinee | 511 | 0.301 | 1.031 | 0.021 | 10.570 | 36 | 115.367 | -13.013 | 8.678 |
| T3_druckenmiller | 46 | 0.348 | 0.586 | -0.235 | -10.812 | 7 | 10.812 | -0.023 | 0.349 |
| T4_contrarien | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| T5_listings | 3 | 1.000 | ∞ | 1.742 | 5.226 | 0 | 0.000 | -0.020 | 0.022 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| T1_tortue | 972 | 0.275 | 0.886 | -0.080 | -77.396 | 41 | 275.364 | -17.585 | 33.054 |
| T2_tortue_disciplinee | 511 | 0.301 | 1.006 | 0.004 | 1.892 | 36 | 120.152 | -13.013 | 17.357 |
| T3_druckenmiller | 46 | 0.348 | 0.576 | -0.243 | -11.160 | 7 | 11.160 | -0.023 | 0.698 |
| T4_contrarien | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| T5_listings | 3 | 1.000 | ∞ | 1.735 | 5.204 | 0 | 0.000 | -0.020 | 0.043 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## Comptes par actif (evaluation, frais doubles)

### T1_tortue

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AI16Z | 5 | 0.400 | -0.086 | -0.428 | -0.018 |
| BOME | 39 | 0.333 | 0.591 | 23.050 | -0.184 |
| BRETT | 36 | 0.333 | 0.160 | 5.745 | -0.244 |
| CHILLGUY | 24 | 0.375 | 0.174 | 4.170 | -0.221 |
| DOGE | 37 | 0.297 | -0.024 | -0.891 | -0.587 |
| FARTCOIN | 37 | 0.270 | -0.065 | -2.397 | -0.804 |
| GOAT | 39 | 0.231 | -0.312 | -12.174 | -1.420 |
| GRIFFAIN | 37 | 0.270 | -0.139 | -5.152 | -0.434 |
| MELANIA | 41 | 0.171 | -0.345 | -14.128 | -0.068 |
| MEME | 45 | 0.178 | -0.513 | -23.084 | -0.757 |
| MEW | 23 | 0.348 | 0.021 | 0.488 | -0.965 |
| MOODENG | 42 | 0.214 | -0.515 | -21.632 | -1.773 |
| PENGU | 41 | 0.342 | 0.057 | 2.352 | -0.874 |
| PNUT | 42 | 0.238 | -0.204 | -8.578 | -0.520 |
| POPCAT | 43 | 0.279 | -0.165 | -7.097 | -0.833 |
| PUMP | 42 | 0.381 | -0.074 | -3.100 | -0.311 |
| SPX | 41 | 0.293 | 0.070 | 2.880 | -0.403 |
| TRUMP | 39 | 0.282 | 0.156 | 6.099 | -2.819 |
| TURBO | 45 | 0.133 | -0.527 | -23.719 | -0.006 |
| USELESS | 4 | 0.250 | -0.215 | -0.860 | 0.042 |
| VINE | 28 | 0.321 | -0.127 | -3.561 | -0.163 |
| WIF | 39 | 0.231 | -0.025 | -0.987 | -0.156 |
| kBONK | 41 | 0.293 | 0.198 | 8.100 | -0.851 |
| kFLOKI | 46 | 0.261 | -0.143 | -6.581 | -1.001 |
| kNEIRO | 44 | 0.227 | -0.289 | -12.697 | -0.570 |
| kPEPE | 35 | 0.371 | 0.479 | 16.770 | -0.802 |
| kSHIB | 37 | 0.324 | 0.000 | 0.015 | -0.840 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.3048 ; 0.1467] R sur 236 jours ; trades a cheval exclus : 6

### T2_tortue_disciplinee

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AI16Z | 3 | 0.000 | -1.034 | -3.101 | -0.020 |
| BOME | 19 | 0.263 | -0.463 | -8.791 | 0.081 |
| BRETT | 20 | 0.400 | 0.308 | 6.167 | -0.196 |
| CHILLGUY | 13 | 0.308 | -0.022 | -0.288 | 0.105 |
| DOGE | 21 | 0.286 | 0.065 | 1.369 | -0.428 |
| FARTCOIN | 21 | 0.238 | -0.130 | -2.732 | -0.232 |
| GOAT | 22 | 0.227 | -0.322 | -7.081 | -1.259 |
| GRIFFAIN | 22 | 0.182 | -0.399 | -8.780 | 0.432 |
| MELANIA | 25 | 0.120 | -0.455 | -11.369 | -0.155 |
| MEME | 27 | 0.185 | -0.524 | -14.137 | -0.810 |
| MEW | 11 | 0.364 | 0.075 | 0.827 | -0.615 |
| MOODENG | 23 | 0.217 | -0.502 | -11.541 | -1.590 |
| PENGU | 21 | 0.381 | 0.129 | 2.709 | -0.549 |
| PNUT | 19 | 0.316 | 0.006 | 0.107 | -0.472 |
| POPCAT | 23 | 0.261 | -0.013 | -0.294 | -0.678 |
| PUMP | 17 | 0.588 | 0.386 | 6.557 | -0.081 |
| SPX | 22 | 0.318 | 0.253 | 5.568 | -0.346 |
| TRUMP | 20 | 0.450 | 0.831 | 16.614 | -2.658 |
| TURBO | 22 | 0.136 | -0.479 | -10.540 | -0.565 |
| USELESS | 2 | 0.000 | -1.036 | -2.073 | -0.037 |
| VINE | 17 | 0.412 | 0.264 | 4.495 | 0.469 |
| WIF | 18 | 0.333 | 0.471 | 8.483 | -0.317 |
| kBONK | 20 | 0.400 | 0.549 | 10.978 | -0.552 |
| kFLOKI | 25 | 0.360 | 0.093 | 2.329 | -0.692 |
| kNEIRO | 23 | 0.217 | -0.295 | -6.792 | -0.702 |
| kPEPE | 17 | 0.471 | 0.962 | 16.358 | -0.443 |
| kSHIB | 18 | 0.444 | 0.381 | 6.851 | -0.704 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.2835 ; 0.343] R sur 130 jours ; trades a cheval exclus : 3

### T3_druckenmiller

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| BOME | 4 | 0.500 | 0.663 | 2.653 | -0.049 |
| BRETT | 1 | 0.000 | -1.023 | -1.023 | -0.006 |
| CHILLGUY | 3 | 0.333 | -0.472 | -1.415 | -0.012 |
| FARTCOIN | 2 | 0.000 | -0.652 | -1.303 | -0.020 |
| GRIFFAIN | 5 | 0.600 | -0.067 | -0.336 | -0.142 |
| MELANIA | 3 | 1.000 | 1.339 | 4.018 | 0.057 |
| MEME | 3 | 0.000 | -1.018 | -3.052 | 0.001 |
| MOODENG | 1 | 0.000 | -0.110 | -0.110 | 0.076 |
| PENGU | 2 | 0.500 | 0.033 | 0.065 | -0.015 |
| POPCAT | 2 | 0.500 | 0.115 | 0.230 | -0.028 |
| PUMP | 5 | 0.200 | -0.386 | -1.930 | -0.077 |
| SPX | 3 | 0.333 | -0.307 | -0.920 | -0.037 |
| TRUMP | 3 | 0.000 | -0.810 | -2.429 | 0.131 |
| TURBO | 1 | 0.000 | -0.883 | -0.883 | 0.134 |
| USELESS | 1 | 0.000 | -1.019 | -1.019 | -0.008 |
| VINE | 1 | 0.000 | -1.045 | -1.045 | -0.017 |
| kBONK | 1 | 0.000 | -1.023 | -1.023 | -0.006 |
| kNEIRO | 1 | 1.000 | 0.007 | 0.007 | 0.043 |
| kPEPE | 4 | 0.500 | -0.411 | -1.644 | -0.048 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.4992 ; 0.0168] R sur 46 jours ; trades a cheval exclus : 1

### T4_contrarien

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

### T5_listings

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| PONS | 1 | 1.000 | 3.308 | 3.308 | -0.016 |
| USELESS | 1 | 1.000 | 0.928 | 0.928 | 0.005 |
| XTEN | 1 | 1.000 | 0.968 | 0.968 | -0.010 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [0.9413 ; 2.5282] R sur 3 jours ; trades a cheval exclus : 0

## Testeur durci

| candidat | trades eval. | esperance frais x3 (R) | PF frais x3 | strategie a 1 % (somme R x 1 %) | acheter et garder | actifs dont l'avantage depend |
|---|---|---|---|---|---|---|
| T1_tortue | 972 | -0.097 | 0.864 | -77.4 % | -77.52 % (26 actifs) | – |
| T2_tortue_disciplinee | 511 | -0.013 | 0.981 | 1.89 % | -77.52 % (26 actifs) | – |
| T3_druckenmiller | 46 | -0.250 | 0.566 | -11.16 % | -77.52 % (26 actifs) | – |
| T4_contrarien | 0 | – | – | 0.0 % | -1.88 % (23 actifs) | – |
| T5_listings | 3 | 1.728 | ∞ | 5.2 % | 9.94 % (3 actifs) | – |

Memecoins du jeu : kPEPE, kBONK, kSHIB, kFLOKI, kNEIRO, kDOGS, DOGE, WIF, POPCAT, FARTCOIN, TRUMP, MELANIA, PUMP, PENGU, MOODENG, GOAT, PNUT, SPX, MEW, BRETT, TURBO, CHILLGUY, USELESS, MEME, BOME, MYRO, GRIFFAIN, AI16Z, VINE, HPOS
Listings de la fenetre 1 h : CHIP, GRAM, CASHCAT, PONS, USELESS, XTEN
