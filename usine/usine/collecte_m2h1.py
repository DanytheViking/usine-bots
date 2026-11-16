"""Collecteur du test M2 1 h de Moonshot (endpoints publics Hyperliquid : aucune cle, aucun ordre).
  - meta et contextes ;
  - les 13 actifs de Moonshot presents dans le meta : bougies 1 h (5000 max) et funding sur la fenetre.
Memes garanties que les collecteurs precedents : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_m2h1 --out /d/m2h1 [--budget 400]"""
import os, sys, json, time, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K
from .collecte_v3 import perps

H = K.H
MOONSHOT = ("BTC", "ETH", "SOL", "ZEC", "HYPE", "NEAR", "kPEPE", "XRP", "PUMP", "XMR", "LIT", "UNI", "AVAX")

def collect(F, out, clock):
    end = K._start(F, clock, H)
    w1 = end - 5000 * H
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    names = perps(json.load(open(os.path.join(out, "meta_ctx.json"))))
    coins = [c for c in MOONSHOT if c in names]
    for c in coins:
        rel = f"candles/{c}_1h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "1h", w1, end, H)); print(f"1h {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w1, end)); print(f"funding {c}")
    return K._finish(F, out, {"jeu": "m2h1", "coins": coins, "debut_1h_ms": w1})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=400)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    man = collect(F, a.out, clock)
    print("COLLECTE M2H1 TERMINEE")
    return man

if __name__ == "__main__":
    main()
