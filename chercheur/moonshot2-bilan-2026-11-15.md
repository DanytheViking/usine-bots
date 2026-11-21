🔬 Democrite, le Chercheur : bilan au 2026-11-15
Trades fermes : 0 ; P&L +0.00 USDC ; +0.00 R (cumule +0.00 R, baisse 0.0 R)
Avis de Thales (depuis le debut) : prendre 0 trades, R moyen None ; eviter 0 trades, R moyen None
Propositions : a pre-enregistrer et a tester avant tout usage.

**1) Marché et régime**

Le bilan ne contient aucune donnée de prix, donc ma lecture est indirecte. Deux signaux short et aucun long sur M2 suggèrent une inclinaison baissière en 4 h sur une partie des perps. C'est un indice faible, pas un régime confirmé. À vérifier : la position de BTC et ETH par rapport à leur EMA 200 en 4 h.

**2) Analyse honnête**

- Zéro trade fermé, 0 R : il n'y a rien à conclure sur M2 cette semaine.
- Mes avis (prendre/éviter) : zéro trade évalué. Je n'ai aucune preuve que mes avis ajoutent de la valeur, et ils ne doivent pas influencer la taille des positions à ce stade.
- Thales a écarté un signal. Je propose de suivre ce trade « fantôme » sur papier pour mesurer plus tard si le filtre aide ou coûte.
- Le short XMR est ouvert : rien à modifier, le stop à 3 ATR reste la règle.

**3) Stratégies à tester (backtest d'abord, pas de réel)**

**A. Cassure Donchian 4 h (13 perps Moonshot)**
- Entrée : long si la clôture dépasse le plus haut des 120 bougies précédentes, short si elle passe sous le plus bas des 120. Filtre : ADX(14) > 25.
- Stop : 2,5 ATR(14).
- Sortie : clôture au-delà du canal opposé de 60 bougies.
- Risque : 0,5 % par trade.

**B. Repli dans la tendance 4 h (13 perps)**
- Tendance : EMA 50 > EMA 200 pour un long (inverse pour un short).
- Entrée long : RSI(14) passé sous 40 dans les 6 dernières bougies, puis clôture au-dessus de l'EMA 20. Short symétrique : RSI au-dessus de 60, puis clôture sous l'EMA 20.
- Stop : 2 ATR(14).
- Sortie : objectif à 3 R, ou clôture du mauvais côté de l'EMA 50.
- Risque : 0,5 % par trade.

**C

## Donnees

```json
{
 "semaine_jusqu_au": "2026-11-15",
 "trades_fermes": 0,
 "pnl_usdc": 0,
 "R_semaine": 0,
 "R_cumule": 0,
 "baisse_R": 0.0,
 "positions_ouvertes": {
  "XMR": "short"
 },
 "signaux": {
  "ecarte par Thales": 1,
  "short": 2
 },
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
