"""SP-20261031-04 — Téléchargement UNIQUE des données publiques Hyperliquid pour le replay (lecture seule).
Aucune clé, aucun ordre, aucun import du code du bot. Seul fichier du module qui touche le réseau.
Endpoint public : POST https://api.hyperliquid.xyz/info
  - candleSnapshot : {"type":"candleSnapshot","req":{"coin","interval","startTime","endTime"}} — 5000 bougies les plus récentes au plus
  - fundingHistory : {"type":"fundingHistory","coin","startTime","endTime"} — réponse paginée (≤ 500 lignes), on avance par l'heure
Usage (sur une machine qui atteint l'API, ex. le VPS ou l'ordinateur de Socrate) :
    python3 -m peanut.replay_fetch --out replay-data --coins BTC,ETH,SOL,...        (ou --status /opt/smart-peanut/data/status.json)
Produit replay-data/{candles,funding}/*.json et replay-data/manifest.json (sha256 de chaque fichier). Refuse d'écraser un jeu existant."""
import os, sys, json, time, hashlib, argparse, datetime as dt
import requests

URL = "https://api.hyperliquid.xyz/info"
TF_MS = {"5m": 300_000, "15m": 900_000}
MAX_CANDLES = 5000
PAUSE_S = 1.0                      # ≈ 60 requêtes/min au plus → ≤ 1 200 de poids/min même à 20 par requête… on reste bien en dessous

def post(body):
    r = requests.post(URL, json=body, timeout=20); r.raise_for_status(); time.sleep(PAUSE_S); return r.json()

def candles(coin, tf, end_ms):
    start = end_ms - MAX_CANDLES * TF_MS[tf]
    return post({"type": "candleSnapshot", "req": {"coin": coin, "interval": tf, "startTime": start, "endTime": end_ms}})

def funding(coin, start_ms, end_ms):
    out, t = [], start_ms
    while t < end_ms:
        page = post({"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": end_ms})
        if not page: break
        out += page; nt = max(int(x["time"]) for x in page) + 1
        if nt <= t: break
        t = nt
    seen, uniq = set(), []
    for x in sorted(out, key=lambda x: int(x["time"])):
        if int(x["time"]) not in seen: seen.add(int(x["time"])); uniq.append(x)
    return uniq

def sha(path): return hashlib.sha256(open(path, "rb").read()).hexdigest()

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--coins"); ap.add_argument("--status")
    a = ap.parse_args(argv)
    coins = [c.strip() for c in (a.coins or "").split(",") if c.strip()]
    if a.status: coins = json.load(open(a.status)).get("universe", [])
    coins = [c for c in dict.fromkeys(coins) if ":" not in c]           # HIP-3 exclu, dédoublonné
    if not coins: sys.exit("aucun actif : --coins ou --status")
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe déjà (jeu figé, jamais écrasé)")
    os.makedirs(os.path.join(a.out, "candles"), exist_ok=True); os.makedirs(os.path.join(a.out, "funding"), exist_ok=True)
    end = int(time.time() * 1000) // TF_MS["15m"] * TF_MS["15m"]        # fin alignée sur une clôture 15 min
    files = {}
    for coin in coins:
        span = []
        for tf in ("5m", "15m"):
            rows = candles(coin, tf, end)
            p = os.path.join("candles", f"{coin}_{tf}.json"); json.dump(rows, open(os.path.join(a.out, p), "w"))
            files[p] = sha(os.path.join(a.out, p)); span += [int(r["t"]) for r in rows]
            print(f"{coin} {tf} : {len(rows)} bougies")
        start = min(span) if span else end - MAX_CANDLES * TF_MS["15m"]
        fr = funding(coin, start, end)
        p = os.path.join("funding", f"{coin}.json"); json.dump(fr, open(os.path.join(a.out, p), "w"))
        files[p] = sha(os.path.join(a.out, p)); print(f"{coin} funding : {len(fr)} lignes")
    man = {"task": "SP-20261031-04", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "end_ms": end,
           "source": URL, "endpoints": ["candleSnapshot", "fundingHistory"], "coins": coins, "intervals": ["5m", "15m"], "files": files,
           "fetch_code_sha256": sha(os.path.abspath(__file__))}
    json.dump(man, open(os.path.join(a.out, "manifest.json"), "w"), indent=1, sort_keys=True)
    print(f"manifeste : {sha(os.path.join(a.out, 'manifest.json'))}")

if __name__ == "__main__":
    main()
