"""Collecteur du Lab v4 « furie » (endpoints publics Hyperliquid : aucune cle, aucun ordre).
  - meta et contextes ;
  - memecoins du Lab presents dans le meta, plus BTC, ETH, SOL, HYPE : bougies 1 h et 15 min (5000 max) et funding sur la fenetre 1 h.
Memes garanties que les collecteurs precedents : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_lab4 --out /d/lab4 [--budget 400]"""
import os, sys, json, time, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K
from .collecte_v3 import MEMES, perps

H, M15 = K.H, 900_000
MAJEURS_LAB = ("BTC", "ETH", "SOL", "HYPE")

def collect(F, out, clock):
    end = K._start(F, clock, H)
    w1, w15 = end - 5000 * H, end - 5000 * M15
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    names = perps(json.load(open(os.path.join(out, "meta_ctx.json"))))
    coins = [c for c in MEMES + MAJEURS_LAB if c in names]
    for c in coins:
        for tf, step, start in (("1h", H, w1), ("15m", M15, w15)):
            rel = f"candles/{c}_{tf}.json"
            if not F.done(rel): F.save(rel, F.candles(c, tf, start, end, step)); print(f"{tf} {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w1, end)); print(f"funding {c}")
    return K._finish(F, out, {"jeu": "lab4", "coins": coins, "debut_1h_ms": w1, "debut_15m_ms": w15})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=400)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    man = collect(F, a.out, clock)
    print("COLLECTE LAB4 TERMINEE")
    return man

if __name__ == "__main__":
    main()
