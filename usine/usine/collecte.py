"""Collecteurs de donnees de l'usine (endpoints publics Hyperliquid seulement : aucune cle, aucun ordre).

  majeurs  : bougies 4 h (5000 max, environ 2 ans) et funding de BTC, ETH, SOL, pour la ligne Moonshot.
  baleines : classement public, puis fills des 100 wallets les plus actifs du mois dont le compte est entre 10 000 et
             5 000 000 USDC, sur 60 jours, pour le candidat C1.
Reprenables (meme commande apres une coupure), fin figee a la premiere execution, ecriture atomique, manifeste sha256 a la
fin, refus d'ecraser un jeu fige. Debit plafonne (poids par minute), meme bareme que replay_pit_fetch.
    python3 -m usine.collecte majeurs --out donnees-majeurs [--budget 600]
    python3 -m usine.collecte baleines --out donnees-baleines [--budget 600]"""
import os, sys, json, time, argparse, datetime as dt
from peanut.replay_pit_fetch import Fetcher, sha

H, H4, DAY = 3_600_000, 4 * 3_600_000, 86_400_000
MAJEURS = ("BTC", "ETH", "SOL")
LEADERBOARD_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
POOL = 100
FILLS_DAYS = 60
FILLS_PAGE = 2000
FILLS_MAX_PAGES = 5

def _get_json(url):
    import requests
    r = requests.get(url, timeout=60); r.raise_for_status(); return r.json()

def _now_utc(): return dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z"

def _start(F, clock, step):
    if "end_ms" not in F.partial:
        F.partial["end_ms"] = int(clock() * 1000) // step * step; F.partial["started_utc"] = _now_utc()
    return int(F.partial["end_ms"])

def _finish(F, out, extra):
    files = {rel: F.partial["files"][rel] for rel in sorted(F.partial["files"])}
    man = {"created_utc": _now_utc(), "started_utc": F.partial.get("started_utc"), "end_ms": int(F.partial["end_ms"]),
           "files": files, "collecte_sha256": sha(os.path.abspath(__file__)), "budget_poids_min": F.pacer.budget, **extra}
    json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1, sort_keys=True)
    os.remove(F.partial_path)
    print(f"manifeste : {sha(os.path.join(out, 'manifest.json'))}")
    return man

def majeurs(F, out, clock):
    end = _start(F, clock, H4); start = end - 5000 * H4
    for c in MAJEURS:
        rel = f"candles/{c}_4h.json"
        if not F.done(rel): F.save(rel, F.candles(c, "4h", start, end, H4)); print(f"4h {c}")
        rel = f"funding/{c}.json"
        if not F.done(rel): F.save(rel, F.funding(c, start, end)); print(f"funding {c}")
    return _finish(F, out, {"jeu": "majeurs", "coins": list(MAJEURS), "intervalle": "4h", "debut_ms": start})

def pool_from_leaderboard(lb):
    """Les POOL wallets au plus gros volume du mois, compte entre 10 000 et 5 000 000 USDC (critere de volume, pas de P&L)."""
    rows = []
    for r in lb.get("leaderboardRows", []):
        try:
            acct = float(r["accountValue"]); perf = dict(r["windowPerformances"]); vlm = float(perf["month"]["vlm"])
        except (KeyError, TypeError, ValueError):
            continue
        if 10_000 <= acct <= 5_000_000: rows.append((vlm, r["ethAddress"].lower(), acct))
    rows.sort(reverse=True)
    return [{"adresse": a, "compte": acct, "volume_mois": v} for v, a, acct in rows[:POOL]]

def fills(F, addr, start, end):
    """userFillsByTime pagine vers l'avant (2000 par reponse, 10000 fills recents au plus). Renvoie (fills, complet)."""
    out, seen, t = [], set(), start
    for _ in range(FILLS_MAX_PAGES):
        page = F.post({"type": "userFillsByTime", "user": addr, "startTime": t, "endTime": end, "aggregateByTime": False},
                      20 + FILLS_PAGE // 20)
        new = [x for x in page if (x.get("tid"), x.get("time")) not in seen]
        for x in new: seen.add((x.get("tid"), x.get("time")))
        out += new
        if len(page) < FILLS_PAGE or not new: return sorted(out, key=lambda x: int(x["time"])), True
        t = max(int(x["time"]) for x in page) + 1
    return sorted(out, key=lambda x: int(x["time"])), False

def baleines(F, out, clock, get_json=_get_json):
    end = _start(F, clock, H); start = end - FILLS_DAYS * DAY
    if not F.done("leaderboard_pool.json"):
        F.save("leaderboard_pool.json", pool_from_leaderboard(get_json(LEADERBOARD_URL)))
    pool = json.load(open(os.path.join(out, "leaderboard_pool.json")))
    for w in pool:
        rel = f"fills/{w['adresse']}.json"
        if F.done(rel): continue
        fs, complet = fills(F, w["adresse"], start, end)
        F.save(rel, {"adresse": w["adresse"], "compte": w["compte"], "complet": complet, "fills": fs}); print(f"fills {w['adresse'][:10]} {len(fs)}")
    return _finish(F, out, {"jeu": "baleines", "debut_ms": start, "nb_wallets": len(pool), "source_classement": LEADERBOARD_URL})

def main(argv=None, post=None, clock=time.time, sleep=time.sleep, get_json=_get_json):
    ap = argparse.ArgumentParser(); ap.add_argument("jeu", choices=["majeurs", "baleines"])
    ap.add_argument("--out", required=True); ap.add_argument("--budget", type=int, default=600)
    a = ap.parse_args(argv)
    if os.path.exists(os.path.join(a.out, "manifest.json")): sys.exit(f"refus : {a.out}/manifest.json existe deja (jeu fige, jamais ecrase)")
    os.makedirs(a.out, exist_ok=True)
    F = Fetcher(a.out, min(a.budget, 900), post, clock, sleep)
    return majeurs(F, a.out, clock) if a.jeu == "majeurs" else baleines(F, a.out, clock, get_json)

if __name__ == "__main__":
    main()
