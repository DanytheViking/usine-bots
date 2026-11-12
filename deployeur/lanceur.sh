#!/usr/bin/env bash
# Lance un passage du Deployeur. Apres trois echecs de suite, restaure la version precedente (dossier precedent/).
APP=/opt/deployeur
N=$APP/.echecs
if /usr/bin/python3 "$APP/deployeur.py"; then
  echo 0 > "$N"
else
  C=$(( $(cat "$N" 2>/dev/null || echo 0) + 1 )); echo "$C" > "$N"
  if [ "$C" -ge 3 ] && [ -f "$APP/precedent/deployeur.py" ]; then
    cp "$APP"/precedent/*.py "$APP"/precedent/*.sh "$APP/" 2>/dev/null
    [ -d "$APP/precedent/tests" ] && rm -rf "$APP/tests" && cp -r "$APP/precedent/tests" "$APP/"
    echo 0 > "$N"
    TOK=$(grep -h '^TELEGRAM_BOT_TOKEN=' /opt/moonshot2/.env | cut -d= -f2-); CHAT=$(grep -h '^TELEGRAM_CHAT_ID=' /opt/moonshot2/.env | cut -d= -f2-)
    curl -s -m 10 "https://api.telegram.org/bot$TOK/sendMessage" -d chat_id="$CHAT" \
      --data-urlencode text="🏭 Usine : le Deployeur a echoue 3 fois de suite, version precedente restauree" >/dev/null || true
    echo "$(date -u +%FT%TZ) version precedente restauree apres 3 echecs" >> "$APP/deployeur.log"
  fi
fi
