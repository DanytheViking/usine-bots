#!/usr/bin/env bash
# Smart Peanut v2 : strategie M2 sur les memecoins, compte Labo. Installation en OBSERVATION (aucun ordre).
# Usage sur le VPS, depuis le dossier extrait : bash install_peanut.sh
# Reprend sans les afficher la cle d'agent du Labo (/opt/smart-peanut/.env.lab), Telegram et Fable (/opt/moonshot2/.env).
# Moonshot n'est pas touche.
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
APP=/opt/peanut2
USINE=/root/usine
C="docker compose -p peanut2 -f docker-compose.peanut.yml"
MEMES="kPEPE,kBONK,kSHIB,kFLOKI,kNEIRO,kDOGS,DOGE,WIF,POPCAT,FARTCOIN,TRUMP,MELANIA,PUMP,PENGU,MOODENG,GOAT,PNUT,SPX,MEW,BRETT,TURBO,CHILLGUY,USELESS,MEME,BOME,MYRO,GRIFFAIN,AI16Z,VINE,HPOS"

echo "== 1. empreintes du paquet"
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"

echo "== 2. copie dans $APP"
mkdir -p "$APP/data"
rm -rf "$APP/moon" "$APP/tests"
cp -r "$SRC/moon" "$SRC/tests" "$APP/"
cp "$SRC/Dockerfile" "$SRC/docker-compose.peanut.yml" "$SRC/requirements.txt" "$SRC/go_live_peanut.sh" "$SRC/SHA256SUMS" "$APP/"
chown 10001 "$APP/data"

get() { grep -h "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'"'" || true; }
if [ ! -f "$APP/.env" ]; then
  echo "== 3. fichier .env (cles reprises sans affichage)"
  ACC=$(get HL_ACCOUNT /opt/smart-peanut/.env.lab); KEY=$(get HL_AGENT_KEY /opt/smart-peanut/.env.lab)
  MOON=$(get HL_ACCOUNT /opt/moonshot2/.env); APEX=$(get HL_ACCOUNT /opt/apex-bot/.env)
  TOK=$(get TELEGRAM_BOT_TOKEN /opt/moonshot2/.env); CHAT=$(get TELEGRAM_CHAT_ID /opt/moonshot2/.env)
  ANT=$(get ANTHROPIC_API_KEY /opt/moonshot2/.env); FAB=$(get FABLE_MODEL /opt/moonshot2/.env)
  [ -n "$ACC" ] && [ -n "$KEY" ] || { echo "ECHEC : HL_ACCOUNT ou HL_AGENT_KEY introuvable dans /opt/smart-peanut/.env.lab"; exit 1; }
  [ "${ACC,,}" != "${MOON,,}" ] || { echo "ECHEC : le compte du Labo est celui de Moonshot"; exit 1; }
  umask 077
  cat > "$APP/.env" <<ENV
MODE=observation
BOT_NAME=smartpeanut2
BOT_PREFIX=🥜 Smart Peanut v2 (memecoins)
HL_ACCOUNT=$ACC
HL_AGENT_KEY=$KEY
FORBIDDEN_ACCOUNTS=$MOON,$APEX
TELEGRAM_BOT_TOKEN=$TOK
TELEGRAM_CHAT_ID=$CHAT
ANTHROPIC_API_KEY=$ANT
FABLE_MODEL=${FAB:-claude-fable-5-2}
COINS=$MEMES
MIN_DAY_VOLUME_USD=2000000
BARS=800
SIGNAL_DELAY_S=90
FETCH_PAUSE_S=2
ENV
  chmod 600 "$APP/.env"
  echo "compte Labo : ${ACC:0:6}...${ACC: -4} ; cle d'agent : presente ; Telegram : $([ -n "$TOK" ] && echo present || echo absent) ; Fable : $([ -n "$ANT" ] && echo present || echo absent)"
else
  echo "== 3. .env deja present : conserve"
fi

echo "== 4. image Docker"
cd "$APP" && $C build -q

echo "== 5. tests hors ligne (sans reseau)"
for t in tests/test_moon.py tests/test_garde_chercheur.py; do
  docker run --rm --network none -v "$USINE":/usine:ro -v /opt/moonshot2/docker-compose.yml:/app/docker-compose.yml:ro -e USINE_DIR=/usine \
    -e PYTHONPATH=/app -e DATA_DIR=/tmp/t --tmpfs /tmp moonshot2:2.2.0 python3 -B "$t" | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
done

echo "== 6. prevol en lecture seule, en mode reel (aucun ordre)"
$C run --rm --no-deps -e MODE=reel moon python3 -m moon.bot --preflight

echo "== 7. demarrage en OBSERVATION"
$C up -d
sleep 10; $C ps
echo "Smart Peanut v2 tourne en OBSERVATION. Passage en reel : bash $APP/go_live_peanut.sh"
echo "ARRET D'URGENCE : touch $APP/data/KILL"
