#!/usr/bin/env bash
# Deployeur de l'usine. Sur le VPS, depuis le dossier extrait :
#   bash installer.sh cle         cree la cle de deploiement et l'affiche (a ajouter dans GitHub)
#   bash installer.sh installer   tests, copie dans /opt/deployeur, clone du depot, adoption de l'etat actuel, cron toutes les 10 min
#   bash installer.sh maj         met a jour le Deployeur lui-meme (tests, copie), sans adoption ni deploiement
#   bash installer.sh etat        dernier etat et dernieres lignes du journal
#   bash installer.sh pause       suspend les deploiements automatiques (cron retire)
#   bash installer.sh reprendre   reactive le cron
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
APP=/opt/deployeur
CLE=$APP/cle_depot
DEPOT=git@github-usine:DanytheViking/usine-bots.git
GITHUB_ED25519="SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU"
CRON=/etc/cron.d/usine-deployeur

case "${1:-}" in
  cle)
    mkdir -p "$APP" /root/.ssh && chmod 700 "$APP" /root/.ssh
    [ -f "$CLE" ] || ssh-keygen -q -t ed25519 -N "" -C "deployeur-usine" -f "$CLE"
    if ! grep -q "Host github-usine" /root/.ssh/config 2>/dev/null; then
      printf 'Host github-usine\n  HostName github.com\n  User git\n  IdentityFile %s\n  IdentitiesOnly yes\n' "$CLE" >> /root/.ssh/config
      chmod 600 /root/.ssh/config
    fi
    ssh-keyscan -t ed25519 github.com 2>/dev/null > /tmp/gh.key
    FP=$(ssh-keygen -lf /tmp/gh.key | awk '{print $2}')
    [ "$FP" = "$GITHUB_ED25519" ] || { echo "ECHEC : empreinte GitHub inattendue ($FP)"; exit 1; }
    grep -qF "$(cut -d' ' -f2- /tmp/gh.key)" /root/.ssh/known_hosts 2>/dev/null || cat /tmp/gh.key >> /root/.ssh/known_hosts
    echo "empreinte GitHub verifiee"
    echo "== cle publique a coller dans GitHub (Deploy keys, Allow write access) :"
    cat "$CLE.pub"
    ;;
  installer)
    echo "== 1. empreintes et tests du Deployeur"
    (cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"
    command -v git >/dev/null || apt-get install -y -q git
    [ -f "$CLE" ] || { echo "ECHEC : lance d'abord : bash installer.sh cle"; exit 1; }
    echo "== 2. acces au depot"
    OUT=$(ssh -o BatchMode=yes -T git@github-usine 2>&1 || true)
    echo "$OUT" | grep -q "successfully authenticated" || { echo "ECHEC : cle pas encore acceptee par GitHub ($OUT)"; exit 1; }
    echo "acces GitHub OK"
    echo "== 3. copie dans $APP"
    cp "$SRC/deployeur.py" "$SRC/bornes.py" "$SRC/installer.sh" "$SRC/lanceur.sh" "$APP/"
    rm -rf "$APP/tests" && cp -r "$SRC/tests" "$APP/" && chmod 700 "$APP"
    [ -d "$APP/depot/.git" ] || git clone -q "$DEPOT" "$APP/depot"
    git -C "$APP/depot" fetch -q origin main
    echo "== 4. tests (faux Docker, vrai git, aucun deploiement)"
    DEPOT_SRC="$APP/depot" python3 -B "$APP/tests/test_deployeur.py" | tail -1
    echo "== 5. constitution sur le depot actuel"
    python3 -c "import sys; sys.path.insert(0, '$APP'); import bornes, subprocess, tempfile, os
d = tempfile.mkdtemp(); subprocess.run(f'git -C $APP/depot archive origin/main | tar -x -C {d}', shell=True, check=True)
v = bornes.verifier(d); print('constitution respectee' if not v else 'VIOLATIONS : ' + '; '.join(v)); sys.exit(1 if v else 0)"
    echo "== 6. adoption de l'etat actuel (aucun redeploiement) et premier rapport"
    DEPLOYEUR_REMOTE="$DEPOT" python3 "$APP/deployeur.py" --adopter
    tail -3 "$APP/deployeur.log"
    echo "== 7. cron toutes les 10 minutes"
    echo "*/10 * * * * root DEPLOYEUR_REMOTE=$DEPOT /bin/bash $APP/lanceur.sh >> $APP/cron.log 2>&1" > "$CRON"
    chmod 644 "$CRON"; cat "$CRON"
    echo "Deployeur actif."
    ;;
  maj)
    (cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "empreintes OK"
    T=$(mktemp -d); cp -r "$SRC/tests" "$SRC/deployeur.py" "$SRC/bornes.py" "$T/"
    DEPOT_SRC="$APP/depot" python3 -B "$T/tests/test_deployeur.py" | tail -1
    DEPOT_SRC="$APP/depot" python3 -B "$T/tests/test_deployeur.py" >/dev/null || { echo "ECHEC : tests, rien n'est change"; exit 1; }
    exec 9>"$APP/.verrou"; flock 9
    cp "$SRC/deployeur.py" "$SRC/bornes.py" "$SRC/installer.sh" "$SRC/lanceur.sh" "$APP/"
    rm -rf "$APP/tests" && cp -r "$SRC/tests" "$APP/"
    echo "*/10 * * * * root DEPLOYEUR_REMOTE=$DEPOT /bin/bash $APP/lanceur.sh >> $APP/cron.log 2>&1" > "$CRON"; chmod 644 "$CRON"
    echo "Deployeur mis a jour : $(sha256sum $APP/deployeur.py | cut -c1-16)"; cat "$CRON"
    ;;
  etat)
    python3 -c "import json; s = json.load(open('$APP/etat.json')); print('deploye :', (s.get('deploye') or '')[:8], '| refuse :', (s.get('refuse') or '-')[:8]); print('cibles :', {k: v[:8] for k, v in s.get('par_cible', {}).items()}); print('echecs :', {k: v[:8] for k, v in s.get('echecs', {}).items()} or '-'); print('travaux :', {k: v['etat'] for k, v in s.get('jobs', {}).items()} or '-')"
    tail -8 "$APP/deployeur.log"
    [ -f "$CRON" ] && echo "cron : actif" || echo "cron : EN PAUSE"
    ;;
  pause)
    rm -f "$CRON"; echo "deploiements automatiques suspendus (reprise : bash $APP/installer.sh reprendre)"
    ;;
  reprendre)
    echo "*/10 * * * * root DEPLOYEUR_REMOTE=$DEPOT /bin/bash $APP/lanceur.sh >> $APP/cron.log 2>&1" > "$CRON"
    chmod 644 "$CRON"; echo "deploiements automatiques actifs"
    ;;
  *)
    sed -n '2,8p' "$0"; exit 1
    ;;
esac
