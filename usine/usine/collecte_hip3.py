"""Collecteur du test M2 sur les marches HIP-3 (endpoints publics Hyperliquid : aucune cle, aucun ordre).
  - liste des dex HIP-3 (perpDexs), meta et contextes de chacun, meta et contextes des perps validateurs ;
  - univers selon PREREG-hip3-m2 : hors delistes, hors sous-jacents crypto, un marche par sous-jacent, classement par volume 24 h,
    bougies 1 h des 20 premiers, 8 premiers avec au moins 2000 bougies ; funding de ces 8 ;
  - BTC 1 h (information : correlation avec M2 sur BTC).
Memes garanties que les collecteurs precedents : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_hip3 --out /d/hip3 [--budget 400]"""
import os, sys, json, time, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K

H = K.H
CANDIDATS_MAX, RETENUS, BOUGIES_MIN = 20, 8, 2000

def fichier(coin):
    """Nom de fichier sur pour un marche HIP-3 (le deux-points du prefixe de dex devient un souligne)."""
    return coin.replace(":", "_")

def base(coin):
    """Sous-jacent sans prefixe de dex ni k ou 1000 en tete."""
    b = coin.split(":", 1)[-1]
    for p in ("1000", "k"):
        if b.startswith(p) and len(b) > len(p) and b[len(p)].isupper(): b = b[len(p):]
    return b.upper()

def dex_names(perp_dexs):
    return [d["name"] for d in perp_dexs if isinstance(d, dict) and d.get("name")]

def marches(dex, meta_ctx):
    """(nom complet, volume notionnel 24 h) des marches non delistes d'un dex HIP-3."""
    meta, ctxs = meta_ctx; out = []
    for u, c in zip(meta.get("universe", []), ctxs):
        if u.get("isDelisted"): continue
        n = u["name"] if ":" in u["name"] else f"{dex}:{u['name']}"
        try: v = float((c or {}).get("dayNtlVlm") or 0)
        except (TypeError, ValueError): v = 0.0
        out.append((n, v))
    return out

def classement(par_dex, validateurs):
    """Regle 2 a 4 du pre-enregistrement, avant les bougies : hors crypto, un marche par sous-jacent, tri par volume decroissant."""
    crypto = {base(n) for n in validateurs}
    best = {}
    for dex in sorted(par_dex):
        for n, v in par_dex[dex]:
            b = base(n)
            if b in crypto: continue
            if b not in best or v > best[b][1]: best[b] = (n, v)
    return sorted(best.values(), key=lambda x: (-x[1], x[0]))[:CANDIDATS_MAX]

def collect(F, out, clock):
    end = K._start(F, clock, H)
    w1 = end - 5000 * H
    if not F.done("perp_dexs.json"): F.save("perp_dexs.json", F.post({"type": "perpDexs"}, 20))
    dexs = dex_names(json.load(open(os.path.join(out, "perp_dexs.json"))))
    if not F.done("meta_validateurs.json"): F.save("meta_validateurs.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    vm, _ = json.load(open(os.path.join(out, "meta_validateurs.json")))
    validateurs = [u["name"] for u in vm["universe"] if ":" not in u["name"]]
    par_dex = {}
    for d in dexs:
        rel = f"meta/{fichier(d)}.json"
        if not F.done(rel): F.save(rel, F.post({"type": "metaAndAssetCtxs", "dex": d}, 20))
        par_dex[d] = marches(d, json.load(open(os.path.join(out, rel))))
    rang = classement(par_dex, validateurs)
    retenus, bougies = [], {}
    for n, _ in rang:
        rel = f"candles/{fichier(n)}_1h.json"
        if not F.done(rel): F.save(rel, F.candles(n, "1h", w1, end, H)); print(f"1h {n}")
        bougies[n] = len(json.load(open(os.path.join(out, rel))))
        if bougies[n] >= BOUGIES_MIN: retenus.append(n)
        if len(retenus) == RETENUS: break
    for n in retenus:
        rel = f"funding/{fichier(n)}.json"
        if not F.done(rel): F.save(rel, F.funding(n, w1, end)); print(f"funding {n}")
    if not F.done("candles/BTC_1h.json"): F.save("candles/BTC_1h.json", F.candles("BTC", "1h", w1, end, H))
    if not F.done("funding/BTC.json"): F.save("funding/BTC.json", F.funding("BTC", w1, end))
    frais = [{k: v for k, v in d.items() if "fee" in k.lower() or k == "name"} for d in json.load(open(os.path.join(out, "perp_dexs.json"))) if isinstance(d, dict)]
    return K._finish(F, out, {"jeu": "hip3", "coins": retenus, "dexs": dexs, "debut_1h_ms": w1,
                              "classement": [{"marche": n, "volume_24h": v, "bougies_1h": bougies.get(n)} for n, v in rang],
                              "frais_publies": frais})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=400)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    man = collect(F, a.out, clock)
    print("COLLECTE HIP3 TERMINEE")
    return man

if __name__ == "__main__":
    main()
