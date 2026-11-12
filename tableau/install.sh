#!/usr/bin/env bash
# Tableau de bord de l'usine : installation. Usage sur le VPS, depuis le dossier extrait : bash install.sh
# Lecture seule : aucune cle, seulement les adresses PUBLIQUES des comptes. Publie sur 127.0.0.1:8090 (tunnel SSH).
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
APP=/opt/tableau
echo "== 1. empreintes du paquet"
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"
echo "== 2. copie dans $APP"
mkdir -p "$APP" /root/rapport-usine-v1 /root/rapport-usine-v2 /opt/peanut2/data
rm -rf "$APP/tableau" "$APP/tests"
cp -r "$SRC/tableau" "$SRC/tests" "$SRC/Dockerfile" "$SRC/docker-compose.yml" "$SRC/docker-compose.telecommande.yml" "$SRC/SHA256SUMS" "$APP/"
get() { grep -h "^$1=" "$2" 2>/dev/null | head -1 | cut -d= -f2- | tr -d ' "'"'" || true; }
MOON=$(get HL_ACCOUNT /opt/moonshot2/.env); LABO=$(get HL_ACCOUNT /opt/smart-peanut/.env.lab)
TOK=$(get TELEGRAM_BOT_TOKEN /opt/moonshot2/.env); CHAT=$(get TELEGRAM_CHAT_ID /opt/moonshot2/.env)
umask 077
printf 'MOON_ACCOUNT=%s\nLABO_ACCOUNT=%s\nTELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n' "$MOON" "$LABO" "$TOK" "$CHAT" > "$APP/.env"
chmod 600 "$APP/.env"
echo "comptes suivis : Moonshot ${MOON:0:6}...${MOON: -4} ; Smart Peanut ${LABO:0:6}...${LABO: -4}"
echo "== 3. image et tests hors ligne"
cd "$APP" && docker compose -p tableau build -q
docker run --rm --network none -e PYTHONPATH=/app --tmpfs /tmp usine-tableau:1.2.0 python3 -B tests/test_tableau.py | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
echo "== 4. demarrage"
docker compose -p tableau up -d
docker compose -p telecommande -f docker-compose.telecommande.yml up -d
sleep 5; docker compose -p tableau ps; docker compose -p telecommande -f docker-compose.telecommande.yml ps
curl -s -o /dev/null -w "reponse locale : %{http_code}\n" http://127.0.0.1:8090/
echo "Telecommande : envoie /aide au bot Telegram."
echo "Depuis le Mac : ssh -N -L 8090:127.0.0.1:8090 root@<IP du VPS>   puis ouvrir http://localhost:8090"
