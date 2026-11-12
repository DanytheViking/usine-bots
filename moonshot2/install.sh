#!/usr/bin/env bash
# Moonshot v2 : installation en mode OBSERVATION (aucun ordre). Usage sur le VPS, depuis le dossier extrait :
#   bash install.sh
# Reprend sans les afficher la cle d'agent et l'adresse du compte Moonshot (/opt/apex-moon/.env.moon) et le bot
# Telegram (/opt/apex-bot/.env). Aucune cle ne s'affiche. Les anciens bots restent arretes et ne sont pas modifies.
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
APP=/opt/moonshot2
USINE=/root/usine

echo "== 1. empreintes du paquet"
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"

echo "== 2. copie dans $APP"
mkdir -p "$APP/data"
cp -r "$SRC/moon" "$SRC/tests" "$SRC/Dockerfile" "$SRC/docker-compose.yml" "$SRC/requirements.txt" "$SRC/go_live.sh" "$SRC/cle_fable.sh" "$SRC/SHA256SUMS" "$APP/"
chown 10001 "$APP/data"

get() { grep -h "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'"'" || true; }
if [ ! -f "$APP/.env" ]; then
  echo "== 3. fichier .env (cles reprises sans affichage)"
  ACC=$(get HL_ACCOUNT /opt/apex-moon/.env.moon); KEY=$(get HL_PRIVATE_KEY /opt/apex-moon/.env.moon)
  TOK=$(get TELEGRAM_BOT_TOKEN /opt/apex-bot/.env); CHAT=$(get TELEGRAM_CHAT_ID /opt/apex-bot/.env)
  APEXACC=$(get HL_ACCOUNT /opt/apex-bot/.env); LABO=$(get HL_ACCOUNT /opt/smart-peanut/.env.lab)
  [ -n "$ACC" ] && [ -n "$KEY" ] || { echo "ECHEC : HL_ACCOUNT ou HL_PRIVATE_KEY introuvable dans /opt/apex-moon/.env.moon"; exit 1; }
  umask 077
  cat > "$APP/.env" <<EOF
MODE=observation
HL_ACCOUNT=$ACC
HL_AGENT_KEY=$KEY
FORBIDDEN_ACCOUNTS=$APEXACC,$LABO
TELEGRAM_BOT_TOKEN=$TOK
TELEGRAM_CHAT_ID=$CHAT
ANTHROPIC_API_KEY=
FABLE_MODEL=claude-fable-5-1
EOF
  chmod 600 "$APP/.env"
  echo "compte Moonshot : ${ACC:0:6}...${ACC: -4} ; cle d'agent : presente ; Telegram : $([ -n "$TOK" ] && echo present || echo absent)"
else
  echo "== 3. .env deja present : conserve"
fi

echo "== 4. image Docker"
cd "$APP" && docker compose -p moonshot2 build -q

echo "== 5. tests hors ligne (sans reseau)"
docker run --rm --network none -v "$USINE":/usine:ro -e USINE_DIR=/usine -e PYTHONPATH=/app -e DATA_DIR=/tmp/t --tmpfs /tmp \
  moonshot2:2.2.0 python3 -B tests/test_moon.py | grep -E '^(ECHEC|[0-9]+/[0-9]+)'

echo "== 6. prevol en lecture seule (aucun ordre)"
docker compose -p moonshot2 run --rm --no-deps moon python3 -m moon.bot --preflight

echo "== 7. demarrage en OBSERVATION"
docker compose -p moonshot2 up -d
sleep 15; docker compose -p moonshot2 ps; docker logs --tail 3 moonshot2
echo "Moonshot v2 tourne en OBSERVATION (aucun ordre). Passage en reel : bash $APP/go_live.sh"
echo "ARRET D'URGENCE : touch $APP/data/KILL"
