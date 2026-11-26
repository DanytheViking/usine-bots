"""Collecteur du Lab v8 « Tendance 4 h confirmee » (endpoints publics Hyperliquid : aucune cle, aucun ordre).
  - meta et contextes ;
  - les 13 actifs de Moonshot presents dans le meta : bougies 4 h (5000 max) et funding sur la fenetre.
Memes garanties que les collecteurs precedents : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_t4h --out /d/t4h [--budget 400]"""
import os, sys, json, time, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K
from .collecte_v3 import perps
from .collecte_m2h1 import MOONSHOT

H4 = K.H4

def collect(F, out, clock):
    end = K._start(F, clock, H4)
    w4 = end - 5000 * H4
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    names = perps(json.load(open(os.path.join(out, "meta_ctx.json"))))
    coins = [c for c in MOONSHOT if c in names]
    for c in coins:
        rel = f"candles/{c}_4h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "4h", w4, end, H4)); print(f"4h {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w4, end)); print(f"funding {c}")
    return K._finish(F, out, {"jeu": "t4h", "coins": coins, "debut_4h_ms": w4})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=400)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    man = collect(F, a.out, clock)
    print("COLLECTE T4H TERMINEE")
    return man

if __name__ == "__main__":
    main()
