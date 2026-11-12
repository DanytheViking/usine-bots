"""SP-20261031-04 — Replay historique HORS LIGNE des 3 signaux de Smart Peanut, sur un jeu de données figé (manifeste sha256).

Garanties :
  - lecture seule : aucune clé, aucun ordre, AUCUN appel réseau (le téléchargement unique est fait par replay_fetch.py) ;
  - n'importe que les fonctions de signal existantes (peanut.signals), sans les modifier ; jamais broker, market, agent ni bot ;
  - AUCUNE optimisation : on mesure les paramètres actuels (v0.1.3), on ne les ajuste pas.
Exécution prudente :
  - le signal est lu sur la bougie CLÔTURÉE i, avec la même fenêtre que le bot (120 bougies) ; l'ordre maker vit à partir de la
    bougie i+1 (jamais sur la bougie du signal), pendant 15 min ;
  - rempli seulement si le prix TRAVERSE la limite (bas < limite pour un achat, haut > limite pour une vente) ;
  - stop et cible touchés dans la même bougie → STOP ; sur la bougie de remplissage, seul le stop est testé ;
  - toutes les sorties (stop, cible, temps max) paient le taux TAKER ; le stop subit en plus un glissement de 0,05 % ;
  - funding horaire réel (fundingHistory) comptabilisé pour chaque échéance pendant la détention.
    python3 -m peanut.replay --data replay-data --out rapport-replay [--prereg PREREG.md]"""
import os, json, math, hashlib, argparse
import numpy as np, pandas as pd
from .signals import rebond_flush, retour_vwap, funding_contre

# --- paramètres v0.1.3, recopiés (un test vérifie qu'ils sont identiques à ceux du bot) ---
WINDOW = 120                 # bougies passées aux signaux, comme signals.scan (market.candles(coin, tf, 120))
ENTRY_TTL_MIN = 15
MAX_HOLD_MIN = 240
# --- frais : barème de base Hyperliquid, perps validateurs, palier 0 (docs officielles « Fees », consultées le 31/10/2026) ---
FEE_MAKER = 0.00015
FEE_TAKER = 0.00045
STOP_SLIP = 0.0005           # glissement de base sur les stops (pré-enregistrement du 30/10)
TF_MS = {"5m": 300_000, "15m": 900_000}
STRATS = {                   # stratégie → (unité de temps, fonction de signal)
    "rebond_flush": ("5m", lambda coin, w, f: rebond_flush(coin, w)),
    "retour_vwap": ("15m", lambda coin, w, f: retour_vwap(coin, w)),
    "funding_contre": ("15m", lambda coin, w, f: funding_contre(coin, w, f)),
}
WARNING = ("⚠️ AVERTISSEMENT — historique court (~5000 bougies au plus : ~17 jours en 5 min, ~52 jours en 15 min), probablement "
           "un seul régime de marché. Résultats indicatifs, AUCUNE optimisation de paramètres : on mesure les paramètres actuels, "
           "on ne les ajuste pas.")

def sha_file(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()

# ============================================================== données figées
class Tampered(Exception): pass

def load(data_dir):
    """Vérifie CHAQUE fichier contre le manifeste avant toute lecture. Refuse au moindre écart."""
    man = json.load(open(os.path.join(data_dir, "manifest.json")))
    for rel, h in sorted(man["files"].items()):
        p = os.path.join(data_dir, rel)
        if not os.path.exists(p) or sha_file(p) != h: raise Tampered(f"{rel} : absent ou empreinte différente du manifeste")
    end = int(man["end_ms"]); bars, fund = {}, {}
    for coin in man["coins"]:
        for tf in ("5m", "15m"):
            raw = json.load(open(os.path.join(data_dir, "candles", f"{coin}_{tf}.json")))
            df = pd.DataFrame(raw).rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "vol"})
            if df.empty: continue
            for c in ("open", "high", "low", "close", "vol"): df[c] = df[c].astype(float)
            df["ts"] = df["ts"].astype("int64")
            df = df[["ts", "open", "high", "low", "close", "vol"]].drop_duplicates("ts").sort_values("ts")
            df = df[df.ts + TF_MS[tf] <= end].reset_index(drop=True)        # bougie encore ouverte au téléchargement : exclue
            bars[(coin, tf)] = df
        fr = json.load(open(os.path.join(data_dir, "funding", f"{coin}.json")))
        fund[coin] = (np.array([int(x["time"]) for x in fr], dtype="int64"), np.array([float(x["fundingRate"]) for x in fr]))
    return man, bars, fund

def funding_an_at(fund, t_ms):
    """Funding annualisé connu à l'instant t (dernière échéance ≤ t) — jamais une valeur future."""
    times, rates = fund
    k = np.searchsorted(times, t_ms, side="right") - 1
    return float(rates[k]) * 24 * 365 if k >= 0 else 0.0

# ============================================================== un trade
def simulate(cand, df, i, tf, fund, fee_mult=1.0):
    """Simule l'ordre issu du signal lu sur la bougie clôturée i. Renvoie un dict (issue, R…) et l'indice de fin d'occupation."""
    tfm = TF_MS[tf]; long_ = cand.side == "long"; sgn = 1 if long_ else -1
    e, st, tp = cand.entry, cand.stop, cand.tp; R = abs(e - st)
    ttl_bars = math.ceil(ENTRY_TTL_MIN * 60_000 / tfm); n = len(df)
    base = {"coin": cand.coin, "strat": cand.strat, "side": cand.side, "signal_ts": int(df.ts[i]), "entry": e, "stop": st, "tp": tp}
    j_fill = None
    for j in range(i + 1, min(n, i + 1 + ttl_bars)):
        if (df.low[j] < e) if long_ else (df.high[j] > e): j_fill = j; break
    if j_fill is None:
        return {**base, "issue": "non rempli"}, min(n - 1, i + ttl_bars)
    t_fill = int(df.ts[j_fill]); exit_px = issue = None; k_end = None
    if (df.low[j_fill] <= st) if long_ else (df.high[j_fill] >= st):    # bougie de remplissage : stop seul
        exit_px, issue, k_end = st, "STOP", j_fill
    else:
        for k in range(j_fill + 1, n):
            hit_s = (df.low[k] <= st) if long_ else (df.high[k] >= st)
            hit_t = (df.high[k] >= tp) if long_ else (df.low[k] <= tp)
            if hit_s: exit_px, issue, k_end = st, "STOP", k; break
            if hit_t: exit_px, issue, k_end = tp, "CIBLE", k; break
            if int(df.ts[k]) + tfm - t_fill >= MAX_HOLD_MIN * 60_000:
                exit_px, issue, k_end = float(df.close[k]), "temps max", k; break
    if issue is None:
        return {**base, "issue": "ouvert en fin de données", "fill_ts": t_fill}, n - 1
    if issue == "STOP": exit_px = st * (1 - STOP_SLIP) if long_ else st * (1 + STOP_SLIP)
    t_exit = int(df.ts[k_end]) + tfm
    gross = sgn * (exit_px - e)
    fees = (e * FEE_MAKER + exit_px * FEE_TAKER) * fee_mult
    times, rates = fund; fsum = 0.0
    for t, r in zip(times, rates):
        if t_fill < t <= t_exit:
            kk = min(n - 1, max(0, int(np.searchsorted(df.ts.values, t, side="right") - 1)))
            fsum += sgn * r * float(df.close[kk])                         # > 0 = payé (long sous funding positif)
    return {**base, "issue": issue, "fill_ts": t_fill, "exit_ts": t_exit, "exit": exit_px,
            "R": (gross - fees - fsum) / R, "gross_R": gross / R, "fees_R": fees / R, "funding_R": -fsum / R}, k_end

# ============================================================== replay d'une stratégie
def replay(bars, fund, strat, fee_mult=1.0):
    tf, fn = STRATS[strat]; trades = []
    for (coin, t), df in sorted(bars.items()):
        if t != tf or len(df) < WINDOW: continue
        busy = -1
        for i in range(WINDOW - 2, len(df) - 1):
            if i <= busy: continue
            w = df.iloc[i + 2 - WINDOW: i + 2].reset_index(drop=True)      # dernière ligne = bougie i+1 (« en cours ») : non lue
            c = fn(coin, w, funding_an_at(fund[coin], int(df.ts[i]) + TF_MS[tf]))
            if not c: continue
            res, busy = simulate(c, df, i, tf, fund[coin], fee_mult)
            trades.append(res)
    return trades

def with_fees(t, mult):
    """Même trade, frais multipliés par `mult` (les remplissages et sorties ne dépendent pas des frais)."""
    if "R" not in t or mult == 1.0: return dict(t)
    return {**t, "fees_R": t["fees_R"] * mult, "R": t["gross_R"] - t["fees_R"] * mult + t["funding_R"]}

# ============================================================== métriques
def metrics(trades):
    sig = len(trades); done = [t for t in trades if "R" in t]
    done.sort(key=lambda t: (t["exit_ts"], t["coin"]))
    rs = [t["R"] for t in done]; pos, neg = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    streak = worst = 0
    for r in rs:
        streak = streak + 1 if r < 0 else 0; worst = max(worst, streak)
    eq = np.cumsum(rs) if rs else np.array([0.0]); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq)) if rs else 0.0
    filled = len(done) + sum(1 for t in trades if t["issue"] == "ouvert en fin de données")
    return {"signaux": sig, "remplis": filled, "taux_remplissage": round(filled / sig, 4) if sig else None, "trades": len(done),
            "ouverts_fin": filled - len(done), "taux_reussite": round(sum(r > 0 for r in rs) / len(rs), 4) if rs else None,
            "profit_factor": round(pos / neg, 3) if neg else (None if not pos else float("inf")),
            "esperance_R": round(float(np.mean(rs)), 4) if rs else None, "somme_R": round(float(sum(rs)), 4),
            "pire_serie_pertes": worst, "drawdown_max_R": round(dd, 4),
            "funding_R": round(sum(t["funding_R"] for t in done), 4), "frais_R": round(sum(t["fees_R"] for t in done), 4),
            "issues": {k: sum(1 for t in trades if t["issue"] == k) for k in sorted({t["issue"] for t in trades})}}

def halves(trades, t0, t1, n=2):
    """Sous-périodes de durée égale sur la fenêtre de données [t0, t1[, par heure du SIGNAL."""
    cuts = [t0 + (t1 - t0) * k / n for k in range(n + 1)]; cuts[-1] = float("inf")
    return [[t for t in trades if cuts[k] <= t["signal_ts"] < cuts[k + 1]] for k in range(n)]

# ============================================================== rapport
def fmt(v):
    if v is None: return "–"
    if isinstance(v, float): return "∞" if v == float("inf") else f"{v:.3f}"
    return str(v)

def run(data_dir, prereg=None, subperiods=2):
    man, bars, fund = load(data_dir)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"manifeste": sha_file(os.path.join(data_dir, "manifest.json")), "replay.py": sha_file(os.path.join(here, "replay.py")),
              "signals.py": sha_file(os.path.join(here, "signals.py"))}
    if prereg: hashes["pre-enregistrement"] = sha_file(prereg)
    out = {"tache": "SP-20261031-04", "avertissement": WARNING, "empreintes": hashes, "actifs": man["coins"],
           "parametres": {"fenetre": WINDOW, "ttl_entree_min": ENTRY_TTL_MIN, "duree_max_min": MAX_HOLD_MIN, "frais_maker": FEE_MAKER,
                          "frais_taker": FEE_TAKER, "glissement_stop": STOP_SLIP, "sorties": "taker", "remplissage": "traversée stricte",
                          "entree": "à partir de la bougie suivant le signal", "meme_bougie": "STOP"}, "strategies": {}}
    for strat, (tf, _) in STRATS.items():
        tss = [int(df.ts.iloc[0]) for (c, t), df in bars.items() if t == tf and len(df)] or [0]
        tse = [int(df.ts.iloc[-1]) + TF_MS[tf] for (c, t), df in bars.items() if t == tf and len(df)] or [0]
        t0, t1 = min(tss), max(tse)
        res = {}; base = replay(bars, fund, strat, 1.0)          # mêmes remplissages : seuls les frais changent entre scénarios
        for label, mult in (("frais_base", 1.0), ("frais_doubles", 2.0)):
            tr = [with_fees(t, mult) for t in base]
            res[label] = {"global": metrics(tr), "sous_periodes": [{"debut_ms": int(t0 + (t1 - t0) * k / subperiods),
                          "fin_ms": int(t0 + (t1 - t0) * (k + 1) / subperiods), **metrics(h)} for k, h in enumerate(halves(tr, t0, t1, subperiods))]}
        out["strategies"][strat] = {"unite": tf, "fenetre_ms": [t0, t1], **res}
    return out

def markdown(rep):
    L = [rep["avertissement"], "", f"# Replay Smart Peanut — {rep['tache']}", "", "## Empreintes (sha256)"]
    L += [f"- {k} : `{v}`" for k, v in rep["empreintes"].items()]
    L += ["", f"Actifs ({len(rep['actifs'])}) : {', '.join(rep['actifs'])}", "", "## Paramètres (ceux de la v0.1.3, non ajustés)"]
    L += [f"- {k} : {v}" for k, v in rep["parametres"].items()]
    L += ["- frais : barème de base Hyperliquid perps palier 0, maker 0,015 % / taker 0,045 % (docs officielles « Fees », consultées le 31/10/2026) ; scénario frais doublés"]
    cols = ["signaux", "remplis", "taux_remplissage", "trades", "taux_reussite", "profit_factor", "esperance_R", "somme_R",
            "pire_serie_pertes", "drawdown_max_R", "funding_R", "frais_R"]
    for strat, s in rep["strategies"].items():
        L += ["", f"## {strat} ({s['unite']})"]
        for label in ("frais_base", "frais_doubles"):
            L += ["", f"### {label.replace('_', ' ')}", "", "| période | " + " | ".join(cols) + " |", "|" + "---|" * (len(cols) + 1)]
            L += ["| globale | " + " | ".join(fmt(s[label]["global"][c]) for c in cols) + " |"]
            for k, sp in enumerate(s[label]["sous_periodes"], 1):
                L += [f"| sous-période {k} | " + " | ".join(fmt(sp[c]) for c in cols) + " |"]
            L += ["", "issues : " + ", ".join(f"{k} {v}" for k, v in s[label]["global"]["issues"].items())]
    return "\n".join(L) + "\n"

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--prereg"); ap.add_argument("--subperiods", type=int, default=2)
    a = ap.parse_args(argv)
    rep = run(a.data, a.prereg, max(2, a.subperiods))
    for k, v in rep["empreintes"].items(): print(f"sha256 {k} : {v}")
    os.makedirs(a.out, exist_ok=True)
    json.dump(rep, open(os.path.join(a.out, "replay.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(a.out, "replay.md"), "w").write(markdown(rep))
    print(f"rapport : {os.path.join(a.out, 'replay.md')} (sha256 {sha_file(os.path.join(a.out, 'replay.md'))})")

if __name__ == "__main__":
    main()
