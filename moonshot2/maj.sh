#!/usr/bin/env bash
# Moonshot v2.2.1 : mise a jour sur place (bot, chien de garde, Fable Chercheur, essai d'execution). Usage sur le VPS, depuis le dossier extrait :
#   bash maj.sh
# Conserve .env (cles) et data/ (etat, journal, positions). Le mode (reel) ne change pas.
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd)
APP=/opt/moonshot2
USINE=/root/usine
C="docker compose -p moonshot2"

echo "== 1. empreintes du paquet"
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) && echo "OK"
[ -f "$APP/.env" ] || { echo "ECHEC : $APP/.env absent"; exit 1; }

echo "== 2. sauvegarde puis copie (cles et donnees conservees)"
TS=$(date -u +%Y%m%d-%H%M)
mkdir -p /root/archives && tar czf "/root/archives/moonshot2-avant-maj-$TS.tgz" --exclude=moonshot2/.env -C /opt moonshot2 || true
rm -rf "$APP/moon" "$APP/tests"
cp -r "$SRC/moon" "$SRC/tests" "$APP/"
cp "$SRC/Dockerfile" "$SRC/docker-compose.yml" "$SRC/requirements.txt" "$SRC/go_live.sh" "$SRC/cle_fable.sh" "$SRC/maj.sh" "$SRC/SHA256SUMS" "$APP/"
mkdir -p "$APP/data/chercheur" && chown 10001 "$APP/data/chercheur"

echo "== 3. image Docker"
cd "$APP" && $C build -q

echo "== 4. tests hors ligne (sans reseau)"
for t in tests/test_moon.py tests/test_garde_chercheur.py tests/test_essai.py; do
  docker run --rm --network none -v "$USINE":/usine:ro -v "$APP/docker-compose.yml":/app/docker-compose.yml:ro -e USINE_DIR=/usine -e PYTHONPATH=/app -e DATA_DIR=/tmp/t --tmpfs /tmp \
    moonshot2:2.2.1 python3 -B "$t" | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
done

echo "== 5. redemarrage : bot, chien de garde, chercheur"
$C up -d --remove-orphans
sleep 15; $C ps
docker logs --tail 3 moonshot2

echo "== 6. premier bilan de Fable Chercheur (un appel, envoye sur Telegram)"
$C run --rm --no-deps chercheur python3 -m moon.chercheur --maintenant
echo "Fait. Bilan automatique chaque dimanche a 18:00 (heure d'Espagne). Chien de garde actif."
