#!/usr/bin/env bash
# Usine, paquet 1 : verification, tests, collecte des donnees et verdicts du catalogue v1.
# Aucun ordre, aucune cle. Seule l'etape "collecte" utilise le reseau (endpoints publics Hyperliquid).
#   ./lancer.sh verifier    empreintes du paquet
#   ./lancer.sh tests       tests hors ligne (sans reseau)
#   ./lancer.sh collecte    donnees 4 h BTC/ETH/SOL puis baleines, en arriere-plan, reprenable
#   ./lancer.sh etat        avancement de la collecte
#   ./lancer.sh verdicts    verdicts des 5 candidats (sans reseau)
set -euo pipefail

USINE=/root/usine
SP=/root/sp-replay
PIT=/root/replay-pit-data
DONNEES=/root/donnees-usine
RAPPORT=/root/rapport-usine-v1
IMAGE=usine-py:1

image() {
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -q -t "$IMAGE" -f "$USINE/Dockerfile" "$USINE" >/dev/null
  fi
}

run_offline() {
  docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$PIT":/pit:ro -v "$DONNEES":/d:ro \
    -v "$RAPPORT":/out -w /app -e PYTHONPATH=/sp:/app -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" "$@"
}

case "${1:-}" in
  verifier)
    cd "$USINE" && sha256sum -c SHA256SUMS
    ;;
  tests)
    image
    docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -w /app -e PYTHONPATH=/sp:/app \
      -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" python -B tests/test_usine.py | grep -E '^(ok|ECHEC|[0-9]+/[0-9]+)'
    ;;
  collecte)
    image
    mkdir -p "$DONNEES"
    docker rm -f usine-collecte >/dev/null 2>&1 || true
    docker run -d --name usine-collecte -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d -w /app \
      -e PYTHONPATH=/sp:/app -e PYTHONUNBUFFERED=1 "$IMAGE" sh -c '
        { [ -f /d/majeurs/manifest.json ] || python -B -m usine.collecte majeurs --out /d/majeurs; } &&
        { [ -f /d/baleines/manifest.json ] || python -B -m usine.collecte baleines --out /d/baleines; } &&
        echo COLLECTE TERMINEE' >/dev/null
    echo "collecte lancee en arriere-plan ; suivi : ./lancer.sh etat"
    ;;
  etat)
    docker logs --tail 5 usine-collecte 2>&1 || true
    ls "$DONNEES"/majeurs/manifest.json "$DONNEES"/baleines/manifest.json 2>/dev/null || true
    ;;
  verdicts)
    image
    mkdir -p "$RAPPORT"
    run_offline python -B -m usine.verdicts --spec specs/USINE-SPEC-v1.json --out /out \
      --pit /pit --majeurs /d/majeurs --baleines /d/baleines
    ;;
  *)
    sed -n '2,8p' "$0"; exit 1
    ;;
esac
