#!/usr/bin/env bash
# T6, le Recolteur de cascades (papier). Sur le VPS, depuis le dossier extrait ou /opt/recolteur :
#   bash installer.sh installer   empreintes, copie dans /opt/recolteur, tests hors ligne, essai reseau, demarrage
#   bash installer.sh etat        statut (phase, univers, lignes, trades) et dernieres lignes du journal Docker
#   bash installer.sh rapport     rapport du journal (cascades, PF net frais x1, x2, x3, verdict)
#   bash installer.sh arreter     arret du Recolteur (donnees conservees)
set -euo pipefail
APP=/opt/recolteur
SRC=$(cd "$(dirname "$0")" && pwd)
IMAGE=recolteur:1.0.1

case "${1:-}" in
  installer)
    echo "== 1. empreintes du paquet"
    (cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"
    echo "== 2. copie dans $APP"
    mkdir -p "$APP/data"
    if [ "$SRC" != "$APP" ]; then
      rm -rf "$APP/recolteur" "$APP/tests" "$APP/docs"
      cp -r "$SRC/recolteur" "$SRC/tests" "$SRC/docs" "$SRC/Dockerfile" "$SRC/docker-compose.yml" "$SRC/requirements.txt" \
            "$SRC/installer.sh" "$SRC/SHA256SUMS" "$APP/"
    fi
    chown -R 10001 "$APP/data"
    get() { grep -h "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'"'" || true; }
    umask 077
    printf 'TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\nCAPITAL_PAPIER=100\n' \
      "$(get TELEGRAM_BOT_TOKEN /opt/moonshot2/.env)" "$(get TELEGRAM_CHAT_ID /opt/moonshot2/.env)" > "$APP/.env"
    chmod 600 "$APP/.env"
    echo "fichier .env ecrit (Telegram seulement, aucune cle d'exchange)"
    echo "== 3. image et tests hors ligne"
    cd "$APP" && docker compose -p recolteur build -q
    docker run --rm --network none --tmpfs /tmp -e DATA_DIR=/tmp "$IMAGE" python3 -B tests/test_recolteur.py 2>/dev/null | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
    echo "== 4. essai reseau (30 s de flux reel, rien n'est enregistre)"
    docker run --rm --tmpfs /tmp "$IMAGE" python3 -m recolteur.essai
    echo "== 5. demarrage"
    docker compose -p recolteur up -d
    sleep 20; docker compose -p recolteur ps
    docker logs --tail 5 recolteur 2>&1
    echo "== 6. surveillance Healthchecks"
    P=/usr/local/bin/usine-ping.sh
    if [ -f "$P" ] && ! grep -q /opt/recolteur/data/status.json "$P"; then
      sed -i 's#/opt/peanut2/data/status.json; do#/opt/peanut2/data/status.json /opt/recolteur/data/status.json; do#' "$P"
    fi
    grep -n "status.json" "$P" 2>/dev/null || echo "script de ping introuvable"
    ;;
  etat)
    docker compose -p recolteur -f "$APP/docker-compose.yml" ps
    python3 - "$APP/data/status.json" <<'PY'
import json, sys, time
try: s = json.load(open(sys.argv[1]))
except Exception as e: sys.exit(f"statut pas encore ecrit ({type(e).__name__}) : attendre 1 minute")
age = time.time() - s["ts"]
print(f"phase {s['phase']} | statut il y a {age:.0f} s | equite papier {s['equite']} USDC | trades {s['trades']} | remplissages {s['remplissages']}")
print(f"univers : {', '.join(s['univers']) or 'pas encore fige (semaine de mesure)'}")
print(f"actifs prets : {len(s['prets'])} | lignes ouvertes : {len(s['lignes'])} | PF net {s['pf_net']} | PF frais x3 {s['pf_stress']}")
PY
    docker logs --tail 5 recolteur 2>&1
    ;;
  rapport)
    docker run --rm --network none --tmpfs /tmp -v "$APP/data":/app/data:ro "$IMAGE" python3 -m recolteur.rapport
    ;;
  arreter)
    docker compose -p recolteur -f "$APP/docker-compose.yml" down
    ;;
  *)
    sed -n '2,6p' "$0"; exit 1
    ;;
esac
