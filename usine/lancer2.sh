#!/usr/bin/env bash
# Usine, paquet 2 : catalogue v2 (M2_etendu, C1_v2). Aucun ordre, aucune cle.
#   ./lancer2.sh verifier    empreintes du paquet
#   ./lancer2.sh tests       tests hors ligne v1 et v2 (sans reseau)
#   ./lancer2.sh collecte    10 actifs etendus puis baleines v2, en arriere-plan, reprenable
#   ./lancer2.sh etat        avancement de la collecte
#   ./lancer2.sh verdicts    verdicts du catalogue v2 (sans reseau)
set -euo pipefail

USINE=/root/usine
SP=/root/sp-replay
DONNEES=/root/donnees-usine
RAPPORT=/root/rapport-usine-v2
IMAGE=usine-py:1

image() {
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -q -t "$IMAGE" -f "$USINE/Dockerfile" "$USINE" >/dev/null
  fi
}

offline() {
  docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d:ro -v "$RAPPORT":/out \
    -w /app -e PYTHONPATH=/sp:/app -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" "$@"
}

case "${1:-}" in
  verifier)
    cd "$USINE" && sha256sum -c SHA256SUMS
    ;;
  tests)
    image
    for t in tests/test_usine.py tests/test_v2.py; do
      docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -w /app -e PYTHONPATH=/sp:/app \
        -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" python -B "$t" | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
    done
    ;;
  collecte)
    image
    mkdir -p "$DONNEES"
    docker rm -f usine-collecte2 >/dev/null 2>&1 || true
    docker run -d --name usine-collecte2 -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d -w /app \
      -e PYTHONPATH=/sp:/app -e PYTHONUNBUFFERED=1 "$IMAGE" sh -c '
        { [ -f /d/etendu/manifest.json ] || python -B -m usine.collecte_v2 etendu --out /d/etendu; } &&
        { [ -f /d/baleines2/manifest.json ] || python -B -m usine.collecte_v2 baleines2 --out /d/baleines2; } &&
        echo COLLECTE V2 TERMINEE' >/dev/null
    echo "collecte v2 lancee en arriere-plan ; suivi : ./lancer2.sh etat"
    ;;
  etat)
    docker logs --tail 5 usine-collecte2 2>&1 || true
    ls "$DONNEES"/etendu/manifest.json "$DONNEES"/baleines2/manifest.json 2>/dev/null || true
    ;;
  verdicts)
    image
    mkdir -p "$RAPPORT"
    offline python -B -m usine.verdicts_v2 --spec specs/USINE-SPEC-v2.json --out /out \
      --etendu /d/etendu --baleines2 /d/baleines2 --majeurs /d/majeurs
    ;;
  *)
    sed -n '2,7p' "$0"; exit 1
    ;;
esac
