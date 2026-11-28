# Test de M2 sur les marches HIP-3

Specification USINE-SPEC-HIP3 (sha256 062d9a4c6cccfc0ae52c52ba5487d4ef5d63e39a34c3f512baedbb068ec185f8), manifeste 446ec3c22949.

**ESPERANCE NEGATIVE : M2 sur HIP-3 abandonne, sans nouveau reglage**

Evaluation, frais doubles. M2_1h_hip3 decide ; M2_4h_reconstruit est publie pour comparer le regime.

| candidat | trades eval. | trades / mois | esperance (R) | PF | IC 5 % | entrainement (R) | frais x3 (R) | pire serie | acheter et garder | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| M2_1h_hip3 | 95 | 27.4 | -0.321 | 0.679 | -0.727 | -0.606 | -0.490 | 20 | -26.36 % | PAS D'AVANTAGE : PF évaluation ≥ 1.35 ; espérance évaluation > 0 en frais doublés ; IC 5 % de l'espérance (frais doublés) > 0 ; espérance entraînement > 0 (cohérence) |
| M2_4h_reconstruit | 19 | 5.5 | -1.065 | 0.141 | -1.362 | -1.094 | -1.181 | 12 | -26.15 % | NON CONCLUANT (moins de 30 trades en évaluation) |

Marches du jeu : xyz:XYZ100, xyz:SP500, xyz:NVDA, xyz:SKHX, xyz:SOXL, xyz:SILVER, xyz:CL, xyz:GOLD

Frais de base HIP-3 = 2 x bareme validateur ; frais doubles = 4 x.
Correlation journaliere avec M2 1 h sur BTC (evaluation) : -0.174

| marche | volume 24 h | bougies 1 h |
|---|---|---|
| xyz:XYZ100 | 267130692 | 5000 |
| xyz:SP500 | 141567422 | 5000 |
| xyz:NVDA | 123579736 | 5000 |
| xyz:SKHX | 72007188 | 5000 |
| xyz:SOXL | 63333785 | 2599 |
| xyz:ANT | 41438774 | 658 |
| xyz:SILVER | 40975747 | 5000 |
| xyz:CL | 34736383 | 5000 |
| xyz:GOLD | 30089533 | 5000 |
| xyz:MU | 26104276 | – |
| xyz:GOOGL | 22010206 | – |
| xyz:BRENTOIL | 20317329 | – |
| xyz:EWY | 17315804 | – |
| xyz:DRAM | 16715522 | – |
| xyz:AAPL | 16379027 | – |
| xyz:SNDK | 13906491 | – |
| xyz:MSFT | 13141874 | – |
| xyz:SKHY | 13084006 | – |
| xyz:TSLA | 12100707 | – |
| xyz:SMSN | 10697437 | – |
