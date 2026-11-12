"""Collecteurs du catalogue v2 (endpoints publics Hyperliquid seulement : aucune cle, aucun ordre).

  etendu    : les 10 perps les plus echangees sur 24 h (hors BTC, ETH, SOL, HIP-3 et delistees) ayant au moins 1500 bougies
              4 h d'historique ; bougies 4 h (5000 max) et funding. Le classement complet est enregistre (selection.json).
  baleines2 : echantillon aleatoire (graine 20261112) de 150 wallets du classement public, compte entre 10 000 et
              5 000 000 USDC, volume du mois entre 1 et 50 millions ; fills sur 60 jours ; bougies 1 h et funding
              de BTC, ETH, SOL et des perps a plus de 5 M$ de volume 24 h au moment de la collecte.
Memes garanties que la v1 : reprenable, fin figee, ecriture atomique, manifeste sha256, refus d'ecraser.
    python3 -m usine.collecte_v2 etendu --out donnees-etendu
    python3 -m usine.collecte_v2 baleines2 --out donnees-baleines2"""
import os, sys, json, time, random, argparse
from peanut.replay_pit_fetch import Fetcher
from . import collecte as K

H, H4, DAY = K.H, K.H4, K.DAY
EXCLUS = ("BTC", "ETH", "SOL")
NB_ETENDU, MIN_BARS_4H = 10, 1500
GRAINE, ECHANTILLON = 20261112, 150
VLM_MIN, VLM_MAX = 1_000_000, 50_000_000
VOL_JOUE = 5_000_000

def ranking(meta_ctx):
    """[(nom, volume 24 h)] des perps validateurs non delistees, du plus gros au plus petit volume."""
    meta, ctxs = meta_ctx
    rows = []
    for u, c in zip(meta["universe"], ctxs):
        if ":" in u["name"] or u.get("isDelisted"): continue
        try: rows.append((u["name"], float(c.get("dayNtlVlm") or 0)))
        except (TypeError, ValueError): continue
    return sorted(rows, key=lambda r: (-r[1], r[0]))

def etendu(F, out, clock):
    end = K._start(F, clock, H4); start = end - 5000 * H4
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    rank = ranking(json.load(open(os.path.join(out, "meta_ctx.json"))))
    sel = F.partial.setdefault("selection", {"retenus": [], "ecartes": {}})
    for name, vlm in rank:
        if len(sel["retenus"]) >= NB_ETENDU: break
        if name in EXCLUS or name in sel["retenus"] or name in sel["ecartes"]: continue
        rel = f"candles/{name}_4h.json"
        if not F.done(rel): F.save(rel, F.candles(name, "4h", start, end, H4))
        n = len(json.load(open(os.path.join(out, rel))))
        if n >= MIN_BARS_4H: sel["retenus"].append(name); print(f"4h {name} {n} retenu")
        else: sel["ecartes"][name] = n; print(f"4h {name} {n} ecarte (historique court)")
        F.save("selection.json", {"regle": f"top {NB_ETENDU} volume 24 h hors {EXCLUS}, >= {MIN_BARS_4H} bougies 4 h", **sel})
    for name in sel["retenus"]:
        rel = f"funding/{name}.json"
        if not F.done(rel): F.save(rel, F.funding(name, start, end)); print(f"funding {name}")
    return K._finish(F, out, {"jeu": "etendu", "coins": sel["retenus"], "intervalle": "4h", "debut_ms": start})

def sample_pool(lb):
    rows = []
    for r in lb.get("leaderboardRows", []):
        try:
            acct = float(r["accountValue"]); vlm = float(dict(r["windowPerformances"])["month"]["vlm"])
        except (KeyError, TypeError, ValueError):
            continue
        if 10_000 <= acct <= 5_000_000 and VLM_MIN <= vlm <= VLM_MAX:
            rows.append({"adresse": r["ethAddress"].lower(), "compte": acct, "volume_mois": vlm})
    rows.sort(key=lambda r: r["adresse"])
    return random.Random(GRAINE).sample(rows, min(ECHANTILLON, len(rows)))

def baleines2(F, out, clock, get_json=K._get_json):
    end = K._start(F, clock, H); start = end - K.FILLS_DAYS * DAY
    if not F.done("leaderboard_pool.json"): F.save("leaderboard_pool.json", sample_pool(get_json(K.LEADERBOARD_URL)))
    if not F.done("meta_ctx.json"): F.save("meta_ctx.json", F.post({"type": "metaAndAssetCtxs"}, 20))
    pool = json.load(open(os.path.join(out, "leaderboard_pool.json")))
    for w in pool:
        rel = f"fills/{w['adresse']}.json"
        if F.done(rel): continue
        fs, complet = K.fills(F, w["adresse"], start, end)
        F.save(rel, {"adresse": w["adresse"], "compte": w["compte"], "complet": complet, "fills": fs}); print(f"fills {w['adresse'][:10]} {len(fs)}")
    joues = sorted(set(EXCLUS) | {n for n, v in ranking(json.load(open(os.path.join(out, "meta_ctx.json")))) if v >= VOL_JOUE})
    h_start = start - 50 * H
    for c in joues:
        rel = f"candles/{c}_1h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "1h", h_start, end, H)); print(f"1h {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, h_start, end)); print(f"funding {c}")
    return K._finish(F, out, {"jeu": "baleines2", "debut_ms": start, "nb_wallets": len(pool), "coins": joues,
                              "graine": GRAINE, "source_classement": K.LEADERBOARD_URL})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep, get_json=K._get_json):
    ap = argparse.ArgumentParser(); ap.add_argument("jeu", choices=["etendu", "baleines2"])
    ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=600)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    return etendu(F, a.out, clock) if a.jeu == "etendu" else baleines2(F, a.out, clock, get_json)

if __name__ == "__main__":
    main()
