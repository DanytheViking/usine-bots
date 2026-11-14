# Usine : verdicts du catalogue v2

Resultats indicatifs sur donnees passees. Aucune optimisation : parametres figes par le pre-enregistrement.

## Empreintes (sha256)
- specification : `09297d4b7a07c21fcfb28d388f84294326eaa4ccbfc92588a61ef4631d00957f`
- sim.py : `a61ee96493d2605c1e675caa90f34cf13643901500cde1f8544bc9999d6f58b9`
- strategies.py : `bd859fa8f58985b348e0dd6e7296e12291b56191bb876ad212554b86c5b811df`
- copie.py : `00f46f317e2ab4f7e65e38a040289d84fe849884dc53448a1d8f482b87fa07cf`
- verdicts.py : `76db738821471fabf99cae5c30ed99d8d0d0f8b38002d294ef024749f0eba811`
- verdicts_v2.py : `fb6edd8db29bdc2ad436cc7a5536e8e2a753948f3253675382563091f440ceb4`
- manifeste_etendu : `5586e62a374301850a48443f895af2de61b7350278b9d8c04c7c592f51f99ae2`
- manifeste_baleines2 : `4623c87cfe62e0e4f74ab1113ec582a94cc681cdf9a63936611817f2b6dcc05c`

## Verdicts (evaluation, criteres annonces)

- **M2_etendu** : PAS D'AVANTAGE : IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-21T12:00Z, fenetre 2024-07-31 au 2026-11-12)
- **C1_v2** : PAS D'AVANTAGE : PF évaluation ≥ 1.20 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) (coupe 2026-10-13T07:00Z, fenetre 2026-09-13 au 2026-11-12)
- **M2_13_actifs_information** : INFORMATION SEULEMENT : PAS D'AVANTAGE : IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-20T18:00Z, fenetre 2024-07-30 au 2026-11-12)
- **ne_rien_trader** : reference (0 R, aucun frais, aucun risque)

## entrainement : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_etendu | 65 | 0.185 | 1.937 | 0.744 | 48.346 | 11 | 11.022 | -11.948 | 0.734 |
| C1_v2 | 532 | 0.314 | 0.940 | -0.022 | -11.470 | 22 | 55.389 | -1.730 | 19.162 |
| M2_13_actifs_information | 101 | 0.228 | 1.935 | 0.695 | 70.189 | 21 | 20.639 | -19.444 | 1.398 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## entrainement : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_etendu | 65 | 0.185 | 1.913 | 0.733 | 47.612 | 11 | 11.213 | -11.948 | 1.467 |
| C1_v2 | 532 | 0.293 | 0.851 | -0.058 | -30.632 | 26 | 66.860 | -1.730 | 38.324 |
| M2_13_actifs_information | 101 | 0.228 | 1.905 | 0.681 | 68.790 | 21 | 20.911 | -19.444 | 2.796 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_etendu | 103 | 0.272 | 1.237 | 0.159 | 16.366 | 11 | 16.187 | -3.192 | 1.193 |
| C1_v2 | 616 | 0.242 | 0.358 | -0.253 | -155.650 | 19 | 155.650 | -1.545 | 26.090 |
| M2_13_actifs_information | 143 | 0.280 | 1.372 | 0.254 | 36.372 | 15 | 25.654 | -4.838 | 2.055 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_etendu | 103 | 0.272 | 1.216 | 0.147 | 15.173 | 11 | 16.493 | -3.192 | 2.386 |
| C1_v2 | 616 | 0.217 | 0.312 | -0.295 | -181.740 | 21 | 181.740 | -1.545 | 52.179 |
| M2_13_actifs_information | 143 | 0.280 | 1.345 | 0.240 | 34.317 | 15 | 26.364 | -4.838 | 4.110 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## Comptes par actif (evaluation, frais doubles)

### M2_etendu

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AVAX | 10 | 0.300 | 0.645 | 6.449 | -0.388 |
| HYPE | 9 | 0.222 | 0.242 | 2.179 | -0.198 |
| LIT | 8 | 0.250 | 0.535 | 4.284 | -0.579 |
| NEAR | 11 | 0.273 | -0.062 | -0.680 | -0.080 |
| PUMP | 12 | 0.250 | 0.131 | 1.569 | -0.255 |
| UNI | 15 | 0.267 | -0.037 | -0.563 | -0.149 |
| XMR | 5 | 0.400 | -0.015 | -0.076 | -0.783 |
| XRP | 10 | 0.400 | 0.371 | 3.707 | -0.090 |
| ZEC | 13 | 0.154 | -0.244 | -3.178 | -0.483 |
| kPEPE | 10 | 0.300 | 0.148 | 1.483 | -0.188 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.1959 ; 0.511] R sur 89 jours ; trades a cheval exclus : 6

### C1_v2

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| ARB | 11 | 0.364 | -0.260 | -2.860 | -0.004 |
| AVAX | 3 | 0.333 | -0.102 | -0.306 | -0.000 |
| BTC | 42 | 0.071 | -0.526 | -22.090 | -0.425 |
| CASHCAT | 31 | 0.452 | -0.052 | -1.615 | 0.003 |
| DOGE | 173 | 0.104 | -0.369 | -63.815 | -0.231 |
| ENA | 6 | 0.000 | -0.327 | -1.964 | -0.004 |
| ETH | 29 | 0.172 | -0.599 | -17.372 | -0.020 |
| GRAM | 3 | 0.333 | -0.051 | -0.152 | -0.004 |
| HYPE | 35 | 0.257 | -0.110 | -3.849 | -0.126 |
| INIT | 2 | 0.000 | -0.220 | -0.440 | -0.025 |
| LINK | 21 | 0.191 | -0.447 | -9.380 | -0.065 |
| LIT | 37 | 0.486 | 0.089 | 3.294 | -0.021 |
| NEAR | 26 | 0.192 | -0.289 | -7.508 | -0.057 |
| PUMP | 14 | 0.429 | 0.278 | 3.890 | 0.010 |
| SOL | 22 | 0.136 | -0.556 | -12.230 | 0.011 |
| TAO | 2 | 0.500 | -0.343 | -0.686 | -0.002 |
| UNI | 8 | 0.125 | -0.523 | -4.183 | 0.008 |
| VVV | 31 | 0.387 | -0.086 | -2.667 | 0.008 |
| WLD | 12 | 0.333 | 0.199 | 2.385 | -0.098 |
| XMR | 31 | 0.097 | -0.451 | -13.975 | -0.429 |
| XRP | 2 | 0.000 | -0.686 | -1.372 | 0.001 |
| ZEC | 40 | 0.225 | -0.416 | -16.647 | -0.018 |
| ZRO | 23 | 0.304 | -0.251 | -5.768 | -0.052 |
| kPEPE | 12 | 0.500 | -0.203 | -2.430 | -0.003 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.3453 ; -0.2447] R sur 31 jours ; trades a cheval exclus : 5

### M2_13_actifs_information

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AVAX | 10 | 0.300 | 0.645 | 6.449 | -0.388 |
| BTC | 15 | 0.267 | 0.049 | 0.727 | -0.251 |
| ETH | 10 | 0.400 | 1.329 | 13.289 | -0.535 |
| HYPE | 9 | 0.222 | 0.242 | 2.179 | -0.198 |
| LIT | 8 | 0.250 | 0.535 | 4.284 | -0.579 |
| NEAR | 11 | 0.273 | -0.062 | -0.680 | -0.080 |
| PUMP | 12 | 0.250 | 0.131 | 1.569 | -0.255 |
| SOL | 15 | 0.267 | 0.342 | 5.128 | -0.860 |
| UNI | 15 | 0.267 | -0.037 | -0.563 | -0.149 |
| XMR | 5 | 0.400 | -0.015 | -0.076 | -0.783 |
| XRP | 10 | 0.400 | 0.371 | 3.707 | -0.090 |
| ZEC | 13 | 0.154 | -0.244 | -3.178 | -0.483 |
| kPEPE | 10 | 0.300 | 0.148 | 1.483 | -0.188 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.0696 ; 0.5934] R sur 111 jours ; trades a cheval exclus : 9

## Copieur : selection des wallets (avant la coupe)
- telecharges : 150 ; retenus : 22
- exclus (aucun fill) : 20
- exclus (historique insuffisant) : 17
- exclus (pas assez de semaines gagnantes) : 63
- exclus (teneur de marche) : 13
- exclus (trop peu de trades) : 15

Actifs de M2_etendu (regle du pre-enregistrement v2) : ZEC, HYPE, NEAR, kPEPE, XRP, PUMP, XMR, LIT, UNI, AVAX
