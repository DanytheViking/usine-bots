"""Collecteur du catalogue v3, ligne Chasseur (endpoints publics Hyperliquid : aucune cle, aucun ordre).
  - meta et contextes (liste de tous les perps, delistes compris) ;
  - memecoins de la liste pre-enregistree presents dans le meta : bougies 4 h et 1 h (5000 max) et funding ;
  - BTC : bougies journalieres (filtre de regime de T2) ;
  - nouveaux listings (T5) : bougies journalieres de tous les perps pour dater leur premiere bougie, puis bougies 1 h et funding
    de ceux dont la premiere bougie tombe dans la fenetre 1 h.
Memes garanties que les collecteurs precedents : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_v3 --out donnees-v3 [--budget 600]"""
import os, sys, json, time, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K

H, H4, D = K.H, K.H4, 24 * K.H
MEMES = ("kPEPE", "kBONK", "kSHIB", "kFLOKI", "kNEIRO", "kDOGS", "DOGE", "WIF", "POPCAT", "FARTCOIN", "TRUMP", "MELANIA", "PUMP",
         "PENGU", "MOODENG", "GOAT", "PNUT", "SPX", "MEW", "BRETT", "TURBO", "CHILLGUY", "USELESS", "MEME", "BOME", "MYRO",
         "GRIFFAIN", "AI16Z", "VINE", "HPOS")

def perps(meta_ctx):
    """Tous les perps validateurs (hors HIP-3), delistes compris (addendum v3, point A)."""
    meta, _ = meta_ctx
    return [u["name"] for u in meta["universe"] if ":" not in u["name"]]

def collect(F, out, clock):
    end = K._start(F, clock, H4)
    w4, w1, wd = end - 5000 * H4, end - 5000 * H, end - 5000 * D
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    names = perps(json.load(open(os.path.join(out, "meta_ctx.json"))))
    memes = [c for c in MEMES if c in names]
    for c in memes:
        for tf, step, start in (("4h", H4, w4), ("1h", H, w1)):
            rel = f"candles/{c}_{tf}.json"
            if not F.done(rel): F.save(rel, F.candles(c, tf, start, end, step)); print(f"{tf} {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w4, end)); print(f"funding {c}")
    if not F.done("candles/BTC_1d.json"): F.save("candles/BTC_1d.json", F.candles("BTC", "1d", wd, end, D)); print("1d BTC")
    listes = []
    for c in names:
        rel = f"candles_1d/{c}_1d.json"
        if not F.done(rel): F.save(rel, F.candles(c, "1d", wd, end, D))
        bars = json.load(open(os.path.join(out, rel)))
        if bars and int(bars[0]["t"]) > w1 + D: listes.append(c)
    F.save("listings.json", {"regle": "premiere bougie journaliere apres le debut de la fenetre 1 h + 1 jour", "coins": listes})
    for c in listes:
        rel = f"candles/{c}_1h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "1h", w1, end, H)); print(f"1h listing {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, w1, end)); print(f"funding listing {c}")
    return K._finish(F, out, {"jeu": "chasseur_v3", "memes": memes, "listings": listes, "debut_4h_ms": w4, "debut_1h_ms": w1})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=600)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    return collect(F, a.out, clock)

if __name__ == "__main__":
    main()
