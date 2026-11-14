# Usine : verdicts du verification M2 sur les memecoins (Smart Peanut v2)

Resultats indicatifs sur donnees passees. Aucune optimisation : parametres figes par le pre-enregistrement.

## Empreintes (sha256)
- specification : `6e730be179d1c568ef3b35a1102c6b005ad50bef53aaa9800d74638ed5457247`
- sim.py : `a61ee96493d2605c1e675caa90f34cf13643901500cde1f8544bc9999d6f58b9`
- strategies.py : `bd859fa8f58985b348e0dd6e7296e12291b56191bb876ad212554b86c5b811df`
- verdicts.py : `76db738821471fabf99cae5c30ed99d8d0d0f8b38002d294ef024749f0eba811`
- verif_m2_memes.py : `1368df9cc9e87f82bba43cf005ac87f6badc2f65dd923aec048eaa9d99b48b6d`
- manifeste_v3 : `4b5f27a5a70a2451142699ed0ad7d46a630c3cf3fdb6353263be429e7b27bfa2`

## Verdicts (evaluation, criteres annonces)

- **M2_memes_filtre_volume** : PAS D'AVANTAGE : PF évaluation ≥ 1.20 ; IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-21T20:00Z, fenetre 2024-08-01 au 2026-11-12)
- **M2_memes_sans_filtre** : PAS D'AVANTAGE : PF évaluation ≥ 1.20 ; IC 5 % de l'espérance (frais doublés) > 0 (coupe 2025-09-21T20:00Z, fenetre 2024-08-01 au 2026-11-12)
- **ne_rien_trader** : reference (0 R, aucun frais, aucun risque)

## entrainement : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_memes_filtre_volume | 126 | 0.262 | 1.426 | 0.296 | 37.338 | 13 | 34.743 | -15.602 | 0.962 |
| M2_memes_sans_filtre | 235 | 0.217 | 1.130 | 0.095 | 22.221 | 24 | 64.040 | -26.212 | 1.810 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## entrainement : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_memes_filtre_volume | 126 | 0.262 | 1.412 | 0.289 | 36.376 | 13 | 35.203 | -15.602 | 1.924 |
| M2_memes_sans_filtre | 235 | 0.217 | 1.119 | 0.087 | 20.410 | 24 | 64.980 | -26.212 | 3.621 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais base

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_memes_filtre_volume | 102 | 0.265 | 1.046 | 0.030 | 3.051 | 12 | 15.004 | -5.491 | 0.896 |
| M2_memes_sans_filtre | 250 | 0.284 | 1.160 | 0.105 | 26.227 | 17 | 26.054 | -13.930 | 2.439 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## evaluation : frais doubles

| candidat | trades | taux_reussite | profit_factor | esperance_R | somme_R | pire_serie_pertes | drawdown_max_R | funding_R | frais_R |
|---|---|---|---|---|---|---|---|---|---|
| M2_memes_filtre_volume | 102 | 0.265 | 1.032 | 0.021 | 2.155 | 12 | 15.222 | -5.491 | 1.792 |
| M2_memes_sans_filtre | 250 | 0.284 | 1.143 | 0.095 | 23.788 | 17 | 26.928 | -13.930 | 4.878 |
| ne_rien_trader | 0 | – | – | 0.000 | 0.000 | 0 | 0.000 | 0.000 | 0.000 |

## Comptes par actif (evaluation, frais doubles)

### M2_memes_filtre_volume

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AI16Z | 0 | – | – | 0.000 | 0 |
| BRETT | 1 | 1.000 | 3.519 | 3.519 | -0.046 |
| CHILLGUY | 1 | 0.000 | -0.009 | -0.009 | -0.064 |
| DOGE | 8 | 0.500 | 0.590 | 4.723 | -0.199 |
| FARTCOIN | 12 | 0.083 | -0.496 | -5.949 | -0.279 |
| GRIFFAIN | 1 | 1.000 | 2.472 | 2.472 | 0.158 |
| MELANIA | 1 | 0.000 | -0.382 | -0.382 | 0.034 |
| MEME | 1 | 0.000 | -0.340 | -0.340 | 0.013 |
| MOODENG | 4 | 0.000 | -1.077 | -4.307 | -1.017 |
| PENGU | 12 | 0.250 | -0.125 | -1.499 | -0.319 |
| PUMP | 12 | 0.250 | 0.131 | 1.569 | -0.255 |
| SPX | 8 | 0.375 | 0.165 | 1.321 | -0.153 |
| TRUMP | 11 | 0.364 | 0.531 | 5.842 | -2.878 |
| TURBO | 1 | 0.000 | -0.950 | -0.950 | 0.060 |
| VINE | 1 | 0.000 | -0.948 | -0.948 | 0.067 |
| WIF | 6 | 0.500 | 1.112 | 6.671 | -0.154 |
| kBONK | 5 | 0.000 | -1.047 | -5.235 | -0.129 |
| kFLOKI | 3 | 0.333 | -0.552 | -1.655 | -0.109 |
| kPEPE | 10 | 0.300 | 0.148 | 1.483 | -0.188 |
| kSHIB | 4 | 0.000 | -1.043 | -4.172 | -0.034 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.2812 ; 0.3417] R sur 70 jours ; trades a cheval exclus : 7

### M2_memes_sans_filtre

| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |
|---|---|---|---|---|---|
| AI16Z | 0 | – | – | 0.000 | 0 |
| BOME | 9 | 0.444 | 1.387 | 12.483 | -0.432 |
| BRETT | 8 | 0.500 | 1.158 | 9.261 | -0.244 |
| CHILLGUY | 3 | 0.333 | 0.165 | 0.494 | -0.054 |
| DOGE | 8 | 0.500 | 0.590 | 4.723 | -0.199 |
| FARTCOIN | 12 | 0.083 | -0.496 | -5.949 | -0.279 |
| GOAT | 9 | 0.222 | 0.171 | 1.538 | -0.284 |
| GRIFFAIN | 10 | 0.500 | 1.266 | 12.659 | -1.159 |
| MELANIA | 13 | 0.308 | -0.273 | -3.553 | -0.120 |
| MEME | 14 | 0.143 | -0.438 | -6.131 | -0.582 |
| MEW | 8 | 0.250 | 0.414 | 3.310 | -0.503 |
| MOODENG | 15 | 0.200 | -0.394 | -5.910 | -3.094 |
| PENGU | 16 | 0.188 | -0.353 | -5.650 | -0.319 |
| PNUT | 8 | 0.250 | -0.258 | -2.063 | -0.381 |
| POPCAT | 11 | 0.364 | 0.051 | 0.565 | -0.370 |
| PUMP | 12 | 0.250 | 0.131 | 1.569 | -0.255 |
| SPX | 10 | 0.400 | 0.147 | 1.476 | -0.382 |
| TRUMP | 12 | 0.333 | 0.401 | 4.806 | -2.870 |
| TURBO | 12 | 0.167 | -0.621 | -7.450 | -0.918 |
| VINE | 12 | 0.083 | -0.434 | -5.203 | 0.578 |
| WIF | 10 | 0.300 | 0.265 | 2.647 | -0.047 |
| kBONK | 8 | 0.250 | 0.612 | 4.899 | -0.201 |
| kFLOKI | 7 | 0.429 | 0.160 | 1.116 | -0.329 |
| kNEIRO | 5 | 0.400 | 0.522 | 2.611 | -0.680 |
| kPEPE | 10 | 0.300 | 0.148 | 1.483 | -0.188 |
| kSHIB | 8 | 0.375 | 0.007 | 0.058 | -0.616 |
| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |

IC bootstrap de l'esperance (frais doubles) : [-0.214 ; 0.4131] R sur 125 jours ; trades a cheval exclus : 20

## Decision pre-enregistree (vue filtre volume, evaluation, frais doubles)

**ESPERANCE >= 0 SANS AVANTAGE DEMONTRE : Smart Peanut continue a 1 %, sans augmentation**

## Testeur durci

| vue | trades eval. | esperance frais x3 (R) | PF frais x3 | somme R x 1 % | acheter et garder | actifs dont l'avantage depend |
|---|---|---|---|---|---|---|
| M2_memes_filtre_volume | 102 | 0.012 | 1.019 | 2.15 % | -77.52 % (26 actifs) | – |
| M2_memes_sans_filtre | 250 | 0.085 | 1.127 | 23.79 % | -77.52 % (26 actifs) | – |
