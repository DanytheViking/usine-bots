#!/usr/bin/env bash
# Usine, paquet 4 : catalogue v3, Team Chasseur (T1 a T5) et Testeur durci. Aucun ordre, aucune cle.
#   ./lancer3.sh verifier    empreintes du paquet
#   ./lancer3.sh tests       tests hors ligne v1, v2 et v3 (sans reseau)
#   ./lancer3.sh collecte    memecoins, BTC journalier et listings, en arriere-plan, reprenable
#   ./lancer3.sh etat        avancement de la collecte
#   ./lancer3.sh verdicts    verdicts du catalogue v3 (sans reseau)
#   ./lancer3.sh m2memes     verification de M2 sur les memecoins (Smart Peanut v2), sans reseau
#   ./lancer3.sh tableau     affiche les verdicts v3 et M2 memecoins dans le tableau de bord
set -euo pipefail

USINE=/root/usine
SP=/root/sp-replay
DONNEES=/root/donnees-usine
RAPPORT=/root/rapport-usine-v3
IMAGE=usine-py:1

image() {
  if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    docker build -q -t "$IMAGE" -f "$USINE/Dockerfile" "$USINE" >/dev/null
  fi
}

case "${1:-}" in
  verifier)
    cd "$USINE" && sha256sum -c SHA256SUMS
    ;;
  tests)
    image
    for t in tests/test_usine.py tests/test_v2.py tests/test_v3.py tests/test_m2memes.py; do
      docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -w /app -e PYTHONPATH=/sp:/app \
        -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" python -B "$t" | grep -E '^(ECHEC|[0-9]+/[0-9]+)'
    done
    ;;
  collecte)
    image
    mkdir -p "$DONNEES"
    docker rm -f usine-collecte3 >/dev/null 2>&1 || true
    docker run -d --name usine-collecte3 -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d -w /app \
      -e PYTHONPATH=/sp:/app -e PYTHONUNBUFFERED=1 "$IMAGE" sh -c '
        { [ -f /d/v3/manifest.json ] || python -B -m usine.collecte_v3 --out /d/v3; } && echo COLLECTE V3 TERMINEE' >/dev/null
    echo "collecte v3 lancee en arriere-plan ; suivi : ./lancer3.sh etat"
    ;;
  etat)
    docker logs --tail 5 usine-collecte3 2>&1 || true
    ls "$DONNEES"/v3/manifest.json 2>/dev/null || echo "manifeste v3 pas encore ecrit"
    ;;
  verdicts)
    [ -f "$DONNEES/v3/manifest.json" ] || { echo "refus : collecte v3 pas terminee (attendre COLLECTE V3 TERMINEE)"; exit 1; }
    image
    mkdir -p "$RAPPORT"
    docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d:ro -v "$RAPPORT":/out \
      -w /app -e PYTHONPATH=/sp:/app -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" \
      python -B -m usine.verdicts_v3 --spec specs/USINE-SPEC-v3.json --data /d/v3 --out /out
    ;;
  m2memes)
    [ -f "$DONNEES/v3/manifest.json" ] || { echo "refus : collecte v3 absente"; exit 1; }
    image
    mkdir -p /root/rapport-usine-m2memes
    docker run --rm --network none -v "$USINE":/app:ro -v "$SP":/sp:ro -v "$DONNEES":/d:ro -v /root/rapport-usine-m2memes:/out \
      -w /app -e PYTHONPATH=/sp:/app -e PYTHONDONTWRITEBYTECODE=1 "$IMAGE" \
      python -B -m usine.verif_m2_memes --spec specs/USINE-SPEC-M2MEMES.json --data /d/v3 --out /out
    ;;
  tableau)
    C=/opt/tableau/docker-compose.yml
    mkdir -p "$RAPPORT" /root/rapport-usine-m2memes
    if ! grep -q usine-v3 "$C"; then
      sed -i '\#/root/rapport-usine-v2:/d/usine-v2:ro#a\      - /root/rapport-usine-v3:/d/usine-v3:ro' "$C"
    fi
    if ! grep -q usine-m2memes "$C"; then
      sed -i '\#/root/rapport-usine-v3:/d/usine-v3:ro#a\      - /root/rapport-usine-m2memes:/d/usine-m2memes:ro' "$C"
    fi
    grep -n "usine-" "$C"
    cd /opt/tableau && docker compose -p tableau up -d
    ;;
  *)
    sed -n '2,9p' "$0"; exit 1
    ;;
esac
