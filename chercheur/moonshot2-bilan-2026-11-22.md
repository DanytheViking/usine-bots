🔬 Democrite, le Chercheur : bilan au 2026-11-22
Trades fermes : 0 ; P&L +0.00 USDC ; +0.00 R (cumule +0.00 R, baisse 0.0 R)
Avis de Thales (depuis le debut) : prendre 0 trades, R moyen None ; eviter 0 trades, R moyen None
Propositions : a pre-enregistrer et a tester avant tout usage.

**1) Marché et régime**

Le bilan ne contient aucune donnée de marché (ni prix, ni volatilité, ni funding), je ne peux donc pas qualifier le régime sans inventer. Seul constat : aucun signal M2 de la semaine et une seule position ouverte (XMR short). C'est normal pour un croisement 50/200 en 4 h, qui est rare, et cela ne dit rien du régime.

**2) Trades et avis de Thales**

Zéro trade fermé, 0 R, et aucun avis de Thales évalué, ni en « prendre » ni en « éviter ». Il n'y a rien à juger, ni en bien ni en mal. Le short XMR n'a ni date, ni prix d'entrée, ni stop, ni avis associé dans les données. Je demande que ces champs soient enregistrés, sinon son résultat ne pourra pas être attribué à Thales.

**3) Propositions**

Les trois sont à backtester avant tout réel ; les seuils sont des points de départ fixes.

**A. Lab : cassure après compression**

- Logique : sur les memecoins, la volatilité se regroupe. Une phase très calme précède souvent un mouvement fort quand les ordres s'accumulent aux bornes.
- Actifs : perps memecoins liquides (DOGE, kPEPE, WIF, kBONK, FARTCOIN).
- Unité : 1 h.
- Condition : largeur des bandes de Bollinger (20 ; 2) au plus bas des 120 dernières bougies.
- Entrée : clôture 1 h hors bande avec volume supérieur à 1,5 fois la moyenne 20 bougies, dans le sens de la cassure.
- Stop : 1,5 ATR(14).
- Sortie : stop suiveur à 2 ATR sous le plus haut atteint (symétrique en short), ou sortie au bout de 48 bougies.
- Risque : 0,5 % du capital Lab par trade.

**B. Lab : plage asiatique, cassure à l'ouverture américaine**

- Logique : la liquidité faible en Asie fixe une plage, puis l'arrivée des flux américains déclenche les stops placés aux bornes.
- Actifs : les mêmes qu'en A.
- Unité : 15 min.
- Plage : plus haut et plus bas entre 00h00 et 08h00 UTC. Pas de trade si elle dépasse 4 % du prix.
- Entrée : première clôture 15 min hors plage entre 13h30 et 16h00 UTC. Un seul trade par actif et par jour.
- Stop : milieu de la plage.
- Sortie : moitié à 2 R avec stop remonté au prix d'entrée, le reste clôturé à 21h00 UTC.
- Risque : 0,5 % par trade.

**C. Moonshot (13 perps) : funding extrême à contre-pied**

- Logique : un funding très élevé signale un levier entassé d'un seul côté. Ce côté paie le portage et devient vulnérable au débouclage ; on encaisse le funding en attendant.
- Unité : 4 h.
- Condition short : funding horaire moyen sur 24 h supérieur à +0,005 %.
- Entrée short : clôture 4 h sous l'EMA 20.
- Version long : symétrique, funding inférieur à -0,005 % et clôture au-dessus de l'EMA 20.
- Stop : 2 ATR(14).
- Sortie : funding moyen 24 h revenu sous 0,00125 % en valeur absolue, ou 5 jours écoulés.
- Risque : 0,5 % par trade, pas de cumul avec une position M2 sur le même actif.

**4) Risques**

- Échantillon nul : aucune conclusion possible sur M2 ni sur Thales à ce stade.
- Surajustement : fixer

## Donnees

```json
{
 "semaine_jusqu_au": "2026-11-22",
 "trades_fermes": 0,
 "pnl_usdc": 0,
 "R_semaine": 0,
 "R_cumule": 0,
 "baisse_R": 0.0,
 "positions_ouvertes": {
  "XMR": "short"
 },
 "signaux": {},
 "fable_depuis_le_debut": {
  "prendre": {
   "trades": 0,
   "R_moyen": null,
   "gagnants": null
  },
  "eviter": {
   "trades": 0,
   "R_moyen": null,
   "gagnants": null
  }
 },
 "trades": []
}
```
