# Usine : verdicts du catalogue v1

Resultats indicatifs sur donnees passees. Aucune optimisation : parametres figes par le pre-enregistrement.

## Empreintes (sha256)
- specification : `98c19120076ae50a86b19c44dd4d90d6fea6ff068f304b99f88763da5536a445`
- sim.py : `a61ee96493d2605c1e675caa90f34cf13643901500cde1f8544bc9999d6f58b9`
- strategies.py : `bd859fa8f58985b348e0dd6e7296e12291b56191bb876ad212554b86c5b811df`
- copie.py : `00f46f317e2ab4f7e65e38a040289d84fe849884dc53448a1d8f482b87fa07cf`
- verdicts.py : `76db738821471fabf99cae5c30ed99d8d0d0f8b38002d294ef024749f0eba811`
- manifeste_majeurs : `db69c5e4a3ea38f97a160b083f55b403675675cdaed0ccb9620a8ac4ad0ea86b`
- manifeste_pit : `1d3c1d2f5dfcedda977c56a3bda0a8997c8bc3bce878618cb0d8d02d0dea19fd`
- manifeste_baleines : `663d4e387477dc46883513703b692eaf49aab173e7242b3f0ef75b06a5dbe4a6`

## Verdicts (evaluation, criteres annonces)

- **M1_cassure_donchian_4h** : PAS D'AVANTAGE : IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) (coupe 2025-09-20T00:00Z, fenetre 2024-07-30 au 2026-11-10)
- **M2_croisement_ema_4h** : PAS D'AVANTAGE : IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-20T00:00Z, fenetre 2024-07-30 au 2026-11-10)
- **P1_cassure_volume_1h** : PAS D'AVANTAGE : PF évaluation ≥ 1.20 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) (coupe 2026-10-05T19:30Z, fenetre 2026-09-09 au 2026-10-31)
- **P2_rotation_momentum_4h** : PAS D'AVANTAGE : PF évaluation ≥ 1.20 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 (coupe 2026-10-05T19:30Z, fenetre 2026-09-09 au 2026-10-31)
- **C1_copie_baleines** : NON CONCLUANT (moins de 30 trades en évaluation) (coupe 2026-10-05T19:30Z, fenetre 2026-09-09 au 2026-10-31)
- **ne_rien_trader** : reference (0 R, aucun frais, aucun risque)

## entrainement : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M1_cassure_donchian_4h | 229 | 0.323 | 0.884 | -0.068 | -15.490 | 13 | 42.168 | -4.495 | 6.368 |
| M2_croisement_ema_4h | 36 | 0.306 | 1.933 | 0.607 | 21.843 | 10 | 9.643 | -7.496 | 0.664 |
| P1_cassure_volume_1h | 255 | 0.349 | 0.882 | -0.075 | -19.091 | 9 | 42.719 | -0.845 | 10.831 |
| P2_rotation_momentum_4h | 298 | 0.483 | 1.044 | 0.010 | 3.091 | 16 | 12.603 | -0.270 | 4.265 |
| C1_copie_baleines | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## entrainement : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M1_cassure_donchian_4h | 229 | 0.310 | 0.842 | -0.095 | -21.857 | 23 | 45.868 | -4.495 | 12.735 |
| M2_croisement_ema_4h | 36 | 0.306 | 1.887 | 0.588 | 21.178 | 10 | 9.834 | -7.496 | 1.329 |
| P1_cassure_volume_1h | 255 | 0.349 | 0.822 | -0.117 | -29.921 | 9 | 49.340 | -0.845 | 21.661 |
| P2_rotation_momentum_4h | 298 | 0.470 | 0.984 | -0.004 | -1.174 | 16 | 13.710 | -0.270 | 8.529 |
| C1_copie_baleines | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M1_cassure_donchian_4h | 239 | 0.255 | 1.269 | 0.172 | 41.158 | 24 | 46.019 | -1.674 | 8.118 |
| M2_croisement_ema_4h | 40 | 0.300 | 1.698 | 0.500 | 20.006 | 11 | 12.429 | -1.646 | 0.862 |
| P1_cassure_volume_1h | 273 | 0.293 | 0.688 | -0.228 | -62.359 | 14 | 73.180 | 0.081 | 11.550 |
| P2_rotation_momentum_4h | 272 | 0.412 | 0.670 | -0.085 | -23.081 | 14 | 26.008 | 0.242 | 4.523 |
| C1_copie_baleines | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M1_cassure_donchian_4h | 239 | 0.251 | 1.208 | 0.138 | 33.040 | 24 | 48.077 | -1.674 | 16.237 |
| M2_croisement_ema_4h | 40 | 0.300 | 1.653 | 0.479 | 19.144 | 11 | 12.898 | -1.646 | 1.724 |
| P1_cassure_volume_1h | 273 | 0.293 | 0.645 | -0.271 | -73.909 | 14 | 83.219 | 0.081 | 23.100 |
| P2_rotation_momentum_4h | 272 | 0.393 | 0.620 | -0.102 | -27.604 | 14 | 30.347 | 0.242 | 9.045 |
| C1_copie_baleines | 0 | – | – | – | 0.000 | 0 | 0.000 | 0 | 0 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## Comptes par actif (evaluation, frais doubles)

### M1_cassure_donchian_4h

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| BTC | 82 | 0.268 | 0.066 | 5.429 | -0.073 |
| ETH | 77 | 0.221 | 0.209 | 16.096 | -0.576 |
| SOL | 80 | 0.263 | 0.144 | 11.515 | -1.026 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.3146 ; 0.7259] R sur 132 jours ; trades a cheval exclus : 1

### M2_croisement_ema_4h

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| BTC | 15 | 0.267 | 0.049 | 0.727 | -0.251 |
| ETH | 10 | 0.400 | 1.329 | 13.289 | -0.535 |
| SOL | 15 | 0.267 | 0.342 | 5.128 | -0.860 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.2881 ; 1.3113] R sur 36 jours ; trades a cheval exclus : 3

### P1_cassure_volume_1h

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AERO | 3 | 0.333 | -0.086 | -0.258 | 0.005 |
| ALGO | 1 | 0.000 | -1.098 | -1.098 | -0.004 |
| APT | 1 | 0.000 | -1.074 | -1.074 | -0.003 |
| ARB | 5 | 0.200 | -0.331 | -1.653 | -0.014 |
| BTC | 21 | 0.286 | -0.537 | -11.280 | 0.066 |
| CASHCAT | 13 | 0.308 | -0.290 | -3.774 | 0.015 |
| CHIP | 8 | 0.375 | -0.105 | -0.843 | -0.012 |
| COMP | 1 | 0.000 | -1.050 | -1.050 | -0.000 |
| CRV | 2 | 0.000 | -1.087 | -2.173 | 0.006 |
| DOT | 1 | 0.000 | -1.089 | -1.089 | -0.003 |
| ENA | 12 | 0.333 | -0.280 | -3.354 | -0.014 |
| ETH | 18 | 0.333 | -0.250 | -4.496 | 0.025 |
| ETHFI | 2 | 0.000 | -1.070 | -2.140 | -0.000 |
| FARTCOIN | 4 | 0.500 | -0.005 | -0.018 | 0.007 |
| FIL | 1 | 0.000 | -1.067 | -1.067 | -0.001 |
| GRAM | 1 | 0.000 | -1.120 | -1.120 | -0.014 |
| GRASS | 4 | 0.500 | 0.454 | 1.815 | 0.002 |
| GRIFFAIN | 1 | 0.000 | -0.578 | -0.578 | 0.002 |
| HYPE | 2 | 1.000 | 1.916 | 3.831 | -0.005 |
| ICP | 1 | 1.000 | 1.916 | 1.916 | 0.007 |
| INIT | 1 | 1.000 | 1.972 | 1.972 | 0.002 |
| INJ | 8 | 0.250 | -0.263 | -2.104 | -0.012 |
| JUP | 2 | 0.500 | 0.434 | 0.869 | -0.001 |
| LIT | 9 | 0.333 | -0.084 | -0.753 | -0.017 |
| MET | 2 | 0.500 | 0.536 | 1.073 | 0.127 |
| MINA | 1 | 1.000 | 1.838 | 1.838 | -0.077 |
| MON | 3 | 0.667 | 0.722 | 2.165 | 0.018 |
| NEAR | 14 | 0.143 | -0.650 | -9.094 | -0.029 |
| NIL | 2 | 0.000 | -1.014 | -2.028 | 0.044 |
| ONDO | 1 | 0.000 | -1.056 | -1.056 | 0.001 |
| OP | 1 | 0.000 | -1.060 | -1.060 | 0.004 |
| PONS | 16 | 0.500 | 0.301 | 4.810 | 0.058 |
| PUMP | 15 | 0.400 | 0.047 | 0.699 | -0.005 |
| PURR | 1 | 0.000 | -1.038 | -1.038 | -0.000 |
| PYTH | 2 | 0.500 | 0.462 | 0.923 | 0.002 |
| S | 1 | 0.000 | -1.034 | -1.034 | 0.001 |
| SAND | 2 | 0.000 | -1.090 | -2.180 | -0.054 |
| SOL | 19 | 0.263 | -0.394 | -7.493 | 0.016 |
| STRK | 15 | 0.467 | 0.261 | 3.909 | 0.018 |
| TIA | 5 | 0.400 | 0.149 | 0.746 | -0.005 |
| USELESS | 1 | 0.000 | -1.017 | -1.017 | 0.010 |
| VVV | 9 | 0.000 | -0.980 | -8.819 | -0.024 |
| W | 2 | 0.000 | -1.040 | -2.081 | -0.019 |
| WLD | 7 | 0.143 | -0.659 | -4.611 | -0.015 |
| XMR | 2 | 0.000 | -1.091 | -2.182 | 0.004 |
| XPL | 3 | 0.667 | 0.920 | 2.761 | -0.010 |
| ZEC | 6 | 0.167 | -0.532 | -3.192 | -0.015 |
| ZRO | 15 | 0.133 | -0.663 | -9.946 | 0.003 |
| kPEPE | 6 | 0.000 | -1.081 | -6.485 | -0.010 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.451 ; -0.0785] R sur 26 jours ; trades a cheval exclus : 7

### P2_rotation_momentum_4h

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AERO | 2 | 0.500 | -0.342 | -0.684 | -0.003 |
| ALT | 3 | 0.333 | -0.483 | -1.449 | 0.001 |
| APT | 1 | 0.000 | -0.217 | -0.217 | -0.001 |
| ATOM | 1 | 0.000 | -0.720 | -0.720 | 0.002 |
| BTC | 2 | 0.000 | -1.063 | -2.127 | -0.002 |
| CASHCAT | 15 | 0.333 | -0.082 | -1.230 | -0.019 |
| CFX | 1 | 0.000 | -0.485 | -0.485 | -0.001 |
| CHIP | 12 | 0.667 | 0.084 | 1.012 | -0.010 |
| COMP | 4 | 0.250 | -0.128 | -0.513 | -0.003 |
| CRV | 3 | 0.667 | 0.220 | 0.659 | -0.005 |
| DOT | 1 | 0.000 | -0.504 | -0.504 | -0.001 |
| ENA | 11 | 0.545 | 0.138 | 1.516 | -0.014 |
| ETHFI | 2 | 0.000 | -0.373 | -0.746 | -0.002 |
| FARTCOIN | 2 | 0.500 | 0.142 | 0.284 | -0.004 |
| GRASS | 3 | 0.667 | -0.108 | -0.325 | -0.003 |
| HYPE | 4 | 0.250 | 0.227 | 0.906 | -0.015 |
| INIT | 10 | 0.700 | 0.011 | 0.114 | 0.024 |
| INJ | 6 | 0.667 | 0.190 | 1.137 | -0.006 |
| JUP | 3 | 0.667 | 0.070 | 0.209 | -0.003 |
| LIT | 9 | 0.111 | -0.186 | -1.678 | 0.008 |
| MET | 6 | 0.667 | 0.063 | 0.381 | 0.110 |
| NEAR | 5 | 0.600 | 0.197 | 0.984 | -0.012 |
| NIL | 9 | 0.222 | -0.323 | -2.909 | 0.031 |
| ONDO | 2 | 0.500 | -0.163 | -0.326 | -0.002 |
| OP | 1 | 0.000 | -0.621 | -0.621 | -0.001 |
| PONS | 15 | 0.200 | -0.233 | -3.492 | -0.013 |
| PUMP | 4 | 0.000 | -0.574 | -2.296 | -0.004 |
| PURR | 6 | 0.333 | -0.291 | -1.746 | -0.003 |
| PYTH | 5 | 0.200 | -0.128 | -0.640 | -0.003 |
| RSR | 3 | 0.333 | -0.243 | -0.730 | 0.147 |
| S | 5 | 0.200 | -0.315 | -1.573 | -0.002 |
| SAND | 7 | 0.286 | -0.192 | -1.347 | 0.211 |
| STBL | 2 | 0.000 | -0.271 | -0.541 | -0.001 |
| STRK | 23 | 0.696 | 0.162 | 3.729 | -0.021 |
| STX | 5 | 0.400 | -0.082 | -0.410 | -0.001 |
| TIA | 10 | 0.400 | -0.046 | -0.464 | -0.004 |
| UNI | 1 | 0.000 | -0.200 | -0.200 | -0.006 |
| VVV | 11 | 0.091 | -0.360 | -3.961 | -0.015 |
| W | 5 | 0.400 | 0.230 | 1.150 | -0.016 |
| WLD | 9 | 0.667 | 0.257 | 2.314 | -0.011 |
| XPL | 6 | 0.667 | 0.010 | 0.060 | -0.039 |
| ZEC | 6 | 0.500 | -0.155 | -0.927 | -0.011 |
| ZK | 3 | 0.333 | 0.028 | 0.083 | -0.002 |
| ZRO | 18 | 0.278 | -0.322 | -5.797 | -0.023 |
| kPEPE | 10 | 0.100 | -0.348 | -3.483 | -0.011 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.1703 ; -0.0373] R sur 27 jours ; trades a cheval exclus : 2

### C1_copie_baleines

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

## Copieur : selection des wallets (avant la coupe)
- telecharges : 100 ; retenus : 0
- exclus (aucun fill) : 14
- exclus (historique insuffisant) : 81
- exclus (teneur de marche) : 1
- exclus (trop peu de trades) : 4
