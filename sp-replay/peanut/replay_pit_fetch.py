"""Extension (a) de SP-20261031-04 — téléchargement UNIQUE, en deux phases et REPRENABLE, du jeu « univers point dans le temps ».
Endpoints PUBLICS seulement (POST https://api.hyperliquid.xyz/info), aucune clé, aucun ordre, aucun import du code du bot.
  Phase 1 : méta (« meta » : toutes les perps validateurs, délistées comprises) + bougies 1 h de CHAQUE actif sur la fenêtre
            [fin − 5000 × 15 min − 50 h, fin].
  Phase 2 : univers point dans le temps calculé HORS LIGNE (peanut.replay_pit) sur les données de la phase 1 → union des membres
            sur la fenêtre → bougies 5 min et 15 min (5000 max) et fundingHistory pour cette union seulement.
Reprenable : chaque fichier écrit est inscrit (avec son sha256) dans .partiel.json ; relancer avec la même commande reprend là
où le processus s'est arrêté, sans retélécharger. Le manifeste final n'est écrit qu'à la toute fin. Refuse d'écraser un jeu figé.
Débit : poids estimé par requête (doc Hyperliquid : info = 20, candleSnapshot + 1 par tranche de 60 bougies) et plafond par
minute (300 par défaut, sur une limite de 1200/min/IP PARTAGÉE avec Apex et Moonshot si lancé depuis le VPS).
    python3 -m peanut.replay_pit_fetch --out replay-pit-data [--budget 300]"""
import os, sys, json, time, hashlib, argparse, datetime as dt, collections

URL = "https://api.hyperliquid.xyz/info"
H, M15, M5 = 3_600_000, 900_000, 300_000
WARMUP_H = 50                                              # 48 bougies 1 h pour le premier score + marge

def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

class Pacer:
    """Plafond de poids sur 60 s glissantes (horloge et attente injectables pour les tests)."""
    def __init__(self, budget, clock=time.time, sleep=time.sleep):
        self.budget, self.clock, self.sleep, self.ev = budget, clock, sleep, collections.deque()
    def wait(self, w):
        while True:
            now = self.clock()
            while self.ev and self.ev[0][0] <= now - 60: self.ev.popleft()
            if sum(x for _, x in self.ev) + w <= self.budget: self.ev.append((now, w)); return
            self.sleep(max(0.5, self.ev[0][0] + 60 - now))

class Fetcher:
    def __init__(self, out, budget=300, post=None, clock=time.time, sleep=time.sleep):
        self.out, self.pacer = out, Pacer(budget, clock, sleep)
        self._post = post or self._http
        self.partial_path = os.path.join(out, ".partiel.json")
        self.partial = json.load(open(self.partial_path)) if os.path.exists(self.partial_path) else {"files": {}}
    @staticmethod
    def _http(body):
        import requests                                     # import tardif : seul point réseau du module
        r = requests.post(URL, json=body, timeout=20); r.raise_for_status(); return r.json()
    def post(self, body, w):
        self.pacer.wait(w); return self._post(body)
    def save(self, rel, obj):
        p = os.path.join(self.out, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(obj, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
        self.partial["files"][rel] = sha(p)
        json.dump(self.partial, open(self.partial_path + ".tmp", "w"), indent=1, sort_keys=True); os.replace(self.partial_path + ".tmp", self.partial_path)
    def done(self, rel):
        p = os.path.join(self.out, rel)
        return rel in self.partial["files"] and os.path.exists(p) and sha(p) == self.partial["files"][rel]
    def candles(self, coin, tf, start, end, step):
        n = max(1, (end - start) // step)
        return self.post({"type": "candleSnapshot", "req": {"coin": coin, "interval": tf, "startTime": start, "endTime": end}}, 20 + n // 60)
    def funding(self, coin, start, end):
        out, t = [], start
        while t < end:
            page = self.post({"type": "fundingHistory", "coin": coin, "startTime": t, "endTime": end}, 20)
            if not page: break
            out += page; nt = max(int(x["time"]) for x in page) + 1
            if nt <= t: break
            t = nt
        seen, uniq = set(), []
        for x in sorted(out, key=lambda x: int(x["time"])):
            if int(x["time"]) not in seen: seen.add(int(x["time"])); uniq.append(x)
        return uniq

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=300)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe déjà (jeu figé, jamais écrasé)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 600), post, clock, sleep)
    # ---- fin figée à la PREMIÈRE exécution (reprises : même fin, même fenêtre)
    if "end_ms" not in F.partial:
        F.partial["end_ms"] = int(clock() * 1000) // M15 * M15; F.partial["started_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z"
    end = int(F.partial["end_ms"]); w0 = end - 5000 * M15; h_start = w0 - WARMUP_H * H
    # ---- phase 1 : méta + 1 h pour tout le méta
    if not F.done("meta.json"): F.save("meta.json", F.post({"type": "meta"}, 20))
    meta = json.load(open(os.path.join(a.out, "meta.json")))
    names = [u["name"] for u in meta["universe"] if ":" not in u["name"]]
    for c in names:
        rel = f"candles/{c}_1h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "1h", h_start, end, H)); print(f"1h {c}")
    # ---- phase 2 : univers point dans le temps (hors ligne) → union → 5 m, 15 m, funding
    from . import replay_pit as P
    import pandas as pd                                     # noqa : dépendance de replay_pit
    man_tmp = {"coins_1h": names, "end_ms": end}
    h1 = P.load_h1(a.out, man_tmp)
    us = P.universe_series(h1, names, w0, end)
    union = sorted({c for v in us.values() for c in v})
    for c in union:
        for tf, step in (("5m", M5), ("15m", M15)):
            rel = f"candles/{c}_{tf}.json"
            if not F.done(rel): F.save(rel, F.candles(c, tf, end - 5000 * step, end, step)); print(f"{tf} {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w0 - WARMUP_H * H, end)); print(f"funding {c}")
    files = {rel: F.partial["files"][rel] for rel in sorted(F.partial["files"])}
    man = {"task": "SP-20261031-04 extension (a)", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z",
           "started_utc": F.partial.get("started_utc"), "end_ms": end, "source": URL,
           "endpoints": ["meta", "candleSnapshot", "fundingHistory"], "coins": union, "coins_1h": names, "intervals": ["1h", "5m", "15m"],
           "files": files, "fetch_code_sha256": sha(os.path.abspath(__file__)), "replay_pit_sha256": sha(P.__file__),
           "regle_univers": "peanut.replay_pit (règle v0.1.3 de market.universe, documentée dans SPEC-SP04-ext-ab.md)", "budget_poids_min": F.pacer.budget}
    json.dump(man, open(os.path.join(a.out, "manifest.json"), "w"), indent=1, sort_keys=True)
    os.remove(F.partial_path)
    print(f"manifeste : {sha(os.path.join(a.out, 'manifest.json'))} — {len(names)} actifs 1 h, union jouée {len(union)}")

if __name__ == "__main__":
    main()
