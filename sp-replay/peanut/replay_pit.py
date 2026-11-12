"""Extension (a) de SP-20261031-04 — UNIVERS « POINT DANS LE TEMPS » (point-in-time) pour le replay, HORS LIGNE.

Problème corrigé : le replay SP-04 jouait l'univers ACTUEL du bot (15 actifs choisis aujourd'hui) sur tout l'historique
→ biais de survivance / de sélection. Ici, à chaque heure h, l'univers est recalculé avec la RÈGLE du bot (market.universe,
v0.1.3) et SEULEMENT les bougies 1 h déjà clôturées à h, sur un univers large (toutes les perps validateurs du méta, délistées
comprises quand l'API en fournit l'historique). Un signal n'est joué que si son actif était dans l'univers au moment du scan.

Règle reproduite (market.universe, v0.1.3) :
  1. liquides : volume notionnel 24 h ≥ MIN_DAY_VOLUME_USD, exclus EXCLUDE (vide par défaut) ;
  2. les 40 plus gros volumes, dans l'ordre du méta en cas d'égalité ;
  3. score = écart-type des rendements log 1 h sur ≤ 48 bougies × √24 (≥ 24 bougies exigées) ;
  4. les 12 meilleurs scores, puis BTC, ETH, SOL ajoutés s'ils sont cotés.
Approximations déclarées (voir note de limites) : volume 24 h = Σ volume × clôture des 24 dernières bougies 1 h clôturées
(le bot lit dayNtlVlm) ; score sur bougies clôturées seulement (le bot inclut la bougie 1 h en cours) ; « coté à h » = une bougie
1 h se terminant exactement à h existe.
N'importe que peanut.replay (SP-04, non modifié) et ses dépendances ; jamais broker, market, agent ni bot ; aucun réseau.
    python3 -m peanut.replay_pit --data replay-pit-data --out rapport-pit [--prereg PREREG.md]"""
import os, json, math, argparse
import numpy as np, pandas as pd
from . import replay as RP

H_MS = 3_600_000
MIN_DAY_VOLUME_USD = 5_000_000      # config.MIN_DAY_VOLUME_USD (défaut v0.1.3) — un test vérifie l'égalité
UNIVERSE_SIZE = 12                  # config.UNIVERSE_SIZE (défaut v0.1.3)
TOP_LIQUID = 40                     # market.universe : [:40]
VOL_BARS, MIN_BARS = 48, 24         # market.universe : candles(c, "1h", 48), len(df) < 24 → ignoré
BASES = ("BTC", "ETH", "SOL")

# ============================================================== données
def load_h1(data_dir, man):
    """Bougies 1 h de TOUT le méta (déjà vérifiées par RP.load contre le manifeste)."""
    out = {}
    for coin in man["coins_1h"]:
        raw = json.load(open(os.path.join(data_dir, "candles", f"{coin}_1h.json")))
        if not raw: continue
        df = pd.DataFrame(raw).rename(columns={"t": "ts", "c": "close", "v": "vol"})
        df["ts"] = df["ts"].astype("int64"); df["close"] = df["close"].astype(float); df["vol"] = df["vol"].astype(float)
        df = df[["ts", "close", "vol"]].drop_duplicates("ts").sort_values("ts")
        out[coin] = df[df.ts + H_MS <= int(man["end_ms"])].reset_index(drop=True)
    return out

def load(data_dir):
    man, bars, fund = RP.load(data_dir)                       # vérifie TOUS les fichiers du manifeste (1 h compris)
    meta = json.load(open(os.path.join(data_dir, "meta.json")))
    order = [u["name"] for u in meta["universe"] if ":" not in u["name"]]
    return man, bars, fund, load_h1(data_dir, man), order

# ============================================================== univers point dans le temps
def features(h1: dict):
    """Par actif : Series indexées par l'heure de CLÔTURE (ts + 1 h) → (volume 24 h, score de volatilité, nb de bougies)."""
    out = {}
    for coin, df in h1.items():
        close_t = df.ts.values + H_MS
        notional = (df.vol * df.close).rolling(24, min_periods=1).sum().values
        r = np.log(df.close).diff()
        score = r.rolling(VOL_BARS - 1, min_periods=1).std(ddof=0).values * math.sqrt(24)   # comme np.std (ddof 0) ; seuil de 24 bougies : nb ci-dessous
        nb = np.minimum(np.arange(1, len(df) + 1), VOL_BARS)
        out[coin] = (close_t, notional, score, nb)
    return out

def universe_at(h, feats, order):
    """Univers que le bot aurait calculé à l'heure h, avec les seules bougies 1 h clôturées à h."""
    vol, sc = {}, {}
    for coin in order:
        f = feats.get(coin)
        if f is None: continue
        close_t, notional, score, nb = f
        k = int(np.searchsorted(close_t, h, side="right")) - 1
        if k < 0 or close_t[k] != h: continue                     # pas de bougie se terminant à h : pas coté (ou délisté) à h
        vol[coin] = float(notional[k]); sc[coin] = (float(score[k]) if nb[k] >= MIN_BARS and not np.isnan(score[k]) else None)
    liq = sorted([c for c in order if c in vol and vol[c] >= MIN_DAY_VOLUME_USD], key=lambda c: -vol[c])[:TOP_LIQUID]
    scored = [(sc[c], c) for c in liq if sc[c] is not None]
    top = [c for _, c in sorted(scored, reverse=True)[:UNIVERSE_SIZE]]
    for b in BASES:
        if b in vol and b not in top: top.append(b)
    return top

def universe_series(h1, order, t0, t1):
    """{heure h: univers} pour toutes les heures de [t0, t1]."""
    feats = features(h1); h = (t0 // H_MS) * H_MS; out = {}
    while h <= t1:
        out[h] = universe_at(h, feats, order); h += H_MS
    return out

def member(useries, coin, t_ms):
    """Univers en vigueur au moment d'un scan à t : celui calculé à la dernière heure pleine ≤ t."""
    return coin in useries.get((t_ms // H_MS) * H_MS, ())

# ============================================================== replay filtré par l'univers point dans le temps
def replay_pit(bars, fund, strat, useries):
    """Même boucle et même simulation que RP.replay (SP-04), plus le filtre d'appartenance à l'univers au moment du scan."""
    tf, fn = RP.STRATS[strat]; trades, skipped = [], 0
    for (coin, t), df in sorted(bars.items()):
        if t != tf or len(df) < RP.WINDOW: continue
        busy = -1
        for i in range(RP.WINDOW - 2, len(df) - 1):
            if i <= busy: continue
            t_scan = int(df.ts[i]) + RP.TF_MS[tf]                 # le bot scanne à la clôture de la bougie i
            w = df.iloc[i + 2 - RP.WINDOW: i + 2].reset_index(drop=True)
            c = fn(coin, w, RP.funding_an_at(fund[coin], t_scan))
            if not c: continue
            if useries is not None and not member(useries, coin, t_scan): skipped += 1; continue
            res, busy = RP.simulate(c, df, i, tf, fund[coin], 1.0)
            trades.append(res)
    return trades, skipped

def run(data_dir, prereg=None):
    man, bars, fund, h1, order = load(data_dir)
    t_all0 = min(int(df.ts.iloc[0]) for df in bars.values() if len(df)); t_all1 = int(man["end_ms"])
    us = universe_series(h1, order, t_all0, t_all1)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"manifeste": RP.sha_file(os.path.join(data_dir, "manifest.json")), "replay_pit.py": RP.sha_file(os.path.join(here, "replay_pit.py")),
              "replay.py": RP.sha_file(os.path.join(here, "replay.py")), "signals.py": RP.sha_file(os.path.join(here, "signals.py"))}
    if prereg: hashes["pre-enregistrement"] = RP.sha_file(prereg)
    sizes = [len(v) for v in us.values()]
    rep = {"tache": "SP-20261031-04 extension (a) — univers point dans le temps", "avertissement": RP.WARNING, "empreintes": hashes,
           "univers": {"actifs_meta_1h": len(h1), "union_jouee": sorted({c for v in us.values() for c in v}), "heures": len(us),
                       "taille_min": min(sizes) if sizes else 0, "taille_max": max(sizes) if sizes else 0,
                       "regle": {"volume_min_usd": MIN_DAY_VOLUME_USD, "top_liquides": TOP_LIQUID, "taille": UNIVERSE_SIZE,
                                 "bougies_vol": VOL_BARS, "bougies_min": MIN_BARS, "toujours": list(BASES)}},
           "strategies": {}}
    trades = {}
    missing = sorted({c for v in us.values() for c in v if (c, "15m") not in bars})
    rep["univers"]["membres_sans_bougies_5m_15m"] = missing
    for strat, (tf, _) in RP.STRATS.items():
        tr, skipped = replay_pit(bars, fund, strat, us); trades[strat] = tr
        tss = [int(df.ts.iloc[0]) for (c, t), df in bars.items() if t == tf and len(df)] or [0]
        t0, t1 = min(tss), max(int(df.ts.iloc[-1]) + RP.TF_MS[tf] for (c, t), df in bars.items() if t == tf and len(df))
        res = {}
        for label, mult in (("frais_base", 1.0), ("frais_doubles", 2.0)):
            x = [RP.with_fees(t, mult) for t in tr]
            res[label] = {"global": RP.metrics(x), "sous_periodes": [{"debut_ms": int(t0 + (t1 - t0) * k / 2), "fin_ms": int(t0 + (t1 - t0) * (k + 1) / 2),
                          **RP.metrics(h)} for k, h in enumerate(RP.halves(x, t0, t1, 2))]}
        rep["strategies"][strat] = {"unite": tf, "fenetre_ms": [t0, t1], "signaux_hors_univers": skipped, **res}
    return rep, trades

def markdown(rep):
    md = RP.markdown({**rep, "actifs": rep["univers"]["union_jouee"], "parametres": {"univers": "point dans le temps (règle v0.1.3, recalcul horaire)"}})
    extra = ["", "## Univers point dans le temps", f"- actifs du méta avec bougies 1 h : {rep['univers']['actifs_meta_1h']}",
             f"- heures : {rep['univers']['heures']} ; taille de l'univers : {rep['univers']['taille_min']} à {rep['univers']['taille_max']}",
             f"- membres sans bougies 5 m / 15 m dans le jeu (signaux impossibles à jouer) : {', '.join(rep['univers']['membres_sans_bougies_5m_15m']) or 'aucun'}"]
    extra += [f"- {s} : signaux écartés car actif hors univers au moment du scan : {v['signaux_hors_univers']}" for s, v in rep["strategies"].items()]
    return md + "\n".join(extra) + "\n"

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True); ap.add_argument("--prereg")
    a = ap.parse_args(argv)
    rep, _ = run(a.data, a.prereg)
    for k, v in rep["empreintes"].items(): print(f"sha256 {k} : {v}")
    os.makedirs(a.out, exist_ok=True)
    json.dump(rep, open(os.path.join(a.out, "replay_pit.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(a.out, "replay_pit.md"), "w").write(markdown(rep))
    print(f"rapport : {os.path.join(a.out, 'replay_pit.md')} (sha256 {RP.sha_file(os.path.join(a.out, 'replay_pit.md'))})")

if __name__ == "__main__":
    main()
