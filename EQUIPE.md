# L'equipe de l'usine : les philosophes

Tous les agents portent le nom d'un philosophe grec. Socrate dirige l'equipe et rapporte a Richard.

Une equipe de specialistes de la tech, maniaques du code propre et fonctionnel, qui s'entraident en permanence pour rendre
les bots plus precis. Chaque role a une source et une trace ecrite ; chacun nourrit les autres.

| role | qui | ce qu'il produit | ou le lire |
|---|---|---|---|
| Socrate, l'architecte | agent quotidien (10 h 23, Europe/Madrid), rapporte a Richard | strategie, architecture, corrections, ameliorations, nouvelles versions, travaux, messages | commits sur `main` |
| Aristote, l'Auditeur | agent independant (11 h 47 et 19 h 47) | approbation ou refus de chaque commit qui touche l'argent reel ou le Deployeur | `audits/<sha>.json` |
| Thales, le decideur | Moonshot : Opus 5.5 (secours Sonnet 5.5) ; Smart Peanut : Fable 5.2 (secours Opus 5.5 puis Sonnet 5.5, Richard 24/11) ; sur chaque signal M2 | decision prendre ou ecarter, avec la raison ; signaux ecartes journalises | `journal-*.jsonl`, etapes `fable` et `signal` |
| Democrite, le Chercheur | bilan du dimanche 18 h (Opus 5.5, secours Sonnet 5.5) | bilan hebdomadaire : decisions de Thales comparees aux resultats | `rapports` : `chercheur/` |
| Pyrrhon, le Testeur | usine de recherche | verdicts pre-enregistres, Testeur durci | `rapports` : `verdicts/`, `jobs/` |
| Diogene, le Controleur | VPS, chaque lundi (et travail `controle`) | reel contre simule : ecart d'entree, frais, funding | tableau de bord, `/opt/usine-public/controle.json` |
| Heraclite, la Sentinelle | VPS, toutes les 15 min | alertes plateforme : delisting, levier, funding extreme, stop absent, cle d'agent, API | Telegram, tableau de bord |
| Epictete, le Directeur des risques | constitution, Gardien, chiens de garde | refus de commit, KILL, alertes | `etat.json`, `deployeur.log` |
| Deployeur | Archimede, sur le VPS toutes les 10 min | tests, deploiement, retour arriere, rapports | `deployeur.log`, `rapports` |
| Traders | Moonshot (M2, 13 actifs), Smart Peanut (M2 memecoins), T6 Recolteur (papier) | trades, journaux | `etat.json`, `journal-*.jsonl` |

## Comment ils s'entraident
- Heraclite et Diogene signalent ; Socrate corrige ; Aristote verifie ; Archimede installe ; Epictete borne le tout.
- Thales decide sur chaque signal ; Democrite mesure si ses decisions ameliorent les resultats (signaux pris contre signaux ecartes) ; Socrate en tire des hypotheses pour le Testeur.
- Toute amelioration de strategie suit le meme chemin : idee -> pre-enregistrement ecrit -> verdict du Testeur -> papier ou reel selon le verdict -> suivi par le Controleur.

## Comment Socrate decide
1. La sante d'abord : un incident (Sentinelle, Controleur, chien de garde, refus de l'Auditeur) se traite avant toute amelioration.
2. Un avis seul ne change jamais une regle de trading : il devient une hypothese a tester.
3. Une mise a jour technique se deploie quand ses tests passent et que l'Auditeur l'a approuvee (bots et Deployeur), hors fenetre de cloture 4 h.
4. Chaque decision prise seul est annoncee a Richard en une ou deux phrases (`messages/`).

## Nouveau membre (15/11/2026)
Eratosthene, le Collecteur de sources : seances Asie, Europe et Etats-Unis, primes Coinbase et coreenne, funding, open interest et
liquidations des grandes plateformes, indices, calendrier macro, memecoins des DEX. Il ne trade pas et n'utilise pas d'IA ; il nourrit Thales et Democrite.

## Modeles (demande de Richard du 15/11/2026)
Pour les decisions et la strategie, le meilleur modele pour le raisonnement : Fable, toujours de preference ; Opus seulement si Fable n'est pas disponible.
Thales et Democrite le font seuls dans le code (secours automatique, aussi sur reponse vide depuis la 2.7.1).
Depuis la 2.7.2 (23/11/2026), leur modele principal est Opus 5.5 et le secours Sonnet 5.5 ; depuis la 2.7.3 (24/11), Thales de Smart Peanut est sur Fable 5.2, puis Opus 5.5, puis Sonnet 5.5. Quand un modele atteint sa limite, on passe au modele en dessous.
Depuis le 22/11/2026 (Richard n'a plus de forfait Fable), Socrate et Aristote tournent sur Opus 5.5.
