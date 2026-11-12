#!/usr/bin/env bash
# Moonshot v2 : passage en REEL (decision de Richard du 12/11 : M2 a 1 % de risque par trade, exception a la regle du 09/11).
# Usage : bash /opt/moonshot2/go_live.sh
set -euo pipefail
APP=/opt/moonshot2; cd "$APP"
C="docker compose -p moonshot2"
[ -f .env ] || { echo "ECHEC : $APP/.env absent, lancez d'abord install.sh"; exit 1; }
[ ! -f data/KILL ] || { echo "ECHEC : un KILL est present (data/KILL). Lisez-le, puis supprimez-le volontairement avant de relancer."; cat data/KILL; exit 1; }

echo "== prevol en lecture seule"
$C run --rm --no-deps -e MODE=reel moon python3 -m moon.bot --preflight

$C stop moon >/dev/null
TS=$(date -u +%Y%m%d-%H%M)
for f in state.json equity.jsonl status.json; do
  if [ -f "data/$f" ]; then mv "data/$f" "data/observation-$TS-$f"; fi
done
echo "etat d'observation archive (data/observation-$TS-*) : le reel repart de zero"

sed -i 's/^MODE=.*/MODE=reel/' .env
$C up -d --force-recreate
sleep 15; $C ps; docker logs --tail 5 moonshot2
echo "Moonshot v2 en REEL : 1 % de risque par trade, arret de ligne a -50 %, arrets de conformite (30 R, 20 pertes d'affilee)."
echo "ARRET D'URGENCE : touch $APP/data/KILL   (plus aucune entree ; les positions gardent leur stop sur Hyperliquid)"
