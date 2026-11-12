# L'equipe de l'usine

Chaque role a une source et une trace ecrite. L'Ingenieur Dev est le seul a modifier le code ; il s'appuie sur les autres.

| role | qui | ce qu'il produit | ou le lire |
|---|---|---|---|
| Ingenieur Dev | agent quotidien (10 h 23, Europe/Madrid) | corrections, mises a jour, nouvelles versions des bots, travaux, messages | commits sur `main` |
| Chercheur | Fable Chercheur (dimanche 18 h) | bilan hebdomadaire : avis de Fable compares aux trades | branche `rapports`, dossier `chercheur/` |
| Visionnaire | avis de Fable sur chaque signal (observation, sans veto) | lecture du regime et des narratifs | `journal-*.jsonl`, etape `fable` |
| Testeur | usine de recherche (verdicts sur l'historique) | verdicts pre-enregistres, Testeur durci | `verdicts/`, `jobs/` |
| Directeur des risques | constitution du Deployeur, Gardien des bots, chiens de garde | refus de commit, KILL, alertes | `etat.json`, `deployeur.log` |
| Traders | Moonshot (M2, 13 actifs), Smart Peanut (M2 memecoins), T6 Recolteur (papier) | trades, journaux | `etat.json`, `journal-*.jsonl` |

## Comment l'Ingenieur Dev decide
1. La sante d'abord : un incident se corrige avant toute amelioration.
2. Une amelioration de strategie suit toujours le meme chemin : idee (Chercheur ou Visionnaire) -> pre-enregistrement ecrit -> verdict du Testeur -> papier ou reel selon le verdict -> suivi.
3. Un avis de Fable seul ne change jamais une regle de trading ; il devient une hypothese a tester.
4. Une mise a jour technique (bug, robustesse, dependance) se deploie quand ses tests passent, hors fenetre de cloture 4 h.
5. Chaque decision prise seul est annoncee a Richard en une ou deux phrases (`messages/`).
