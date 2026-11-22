# Addendum au pre-enregistrement du Lab v5 : plafond de deux positions (22/11/2026)

Ecrit apres le refus d'Aristote du 22/11/2026 (audit de 564f0a3, commit 204c513) et avant tout nouveau calcul.
Motif : le cadre montre a Richard avant son choix du 22/11 (20 h 16 UTC) annoncait « deux positions au plus », mais le test du Lab v5
et le bot 2.7.0 n'avaient pas ce plafond. Ce n'est pas un reglage choisi apres lecture du verdict : c'est une contrainte deja promise, et plus stricte.

## Seul changement par rapport a PREREG-lab5-tendance
- Les deux candidats sont rejoues avec au plus deux positions ouvertes, tous actifs confondus, dans l'ordre des entrees
  (strategies_lab4.capacite, comme au Lab v4). Le bot applique le meme plafond, actifs lus dans l'ordre de COINS a chaque cloture ;
  a heure egale, l'ordre du test (par nom d'actif) peut differer de celui du bot, ecart publie ici.
- Donnees (jeu m2t, manifeste cf9a346e509a), parametres, criteres de la voie rapide et regle de decision inchanges.

## Decision
- Le verdict avec plafond remplace celui du 22/11 21 h 10 UTC pour la mise en reel. S'il ne passe pas, rien en reel sans exception ecrite de Richard.
