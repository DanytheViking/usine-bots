#!/usr/bin/env bash
# Ajoute la cle API Anthropic de Fable dans /opt/moonshot2/.env sans l'afficher, puis redemarre le bot.
# Usage : bash /opt/moonshot2/cle_fable.sh   (la saisie est masquee ; collez la cle puis Entree)
set -euo pipefail
APP=/opt/moonshot2; cd "$APP"
read -r -s -p "Cle API Anthropic (masquee) : " K; echo
case "$K" in sk-ant-*) ;; *) echo "ECHEC : une cle Anthropic commence par sk-ant-"; exit 1;; esac
if grep -q '^ANTHROPIC_API_KEY=' .env; then
  python3 - "$K" <<'PY'
import sys, re
p = "/opt/moonshot2/.env"; s = open(p).read()
s = re.sub(r"(?m)^ANTHROPIC_API_KEY=.*$", "ANTHROPIC_API_KEY=" + sys.argv[1], s)
open(p, "w").write(s)
PY
else
  printf 'ANTHROPIC_API_KEY=%s\n' "$K" >> .env
fi
chmod 600 .env; unset K
docker compose -p moonshot2 up -d --force-recreate >/dev/null
echo "Cle enregistree (non affichee) et bot redemarre. Fable donnera son avis sur chaque signal, sans toucher aux ordres."
