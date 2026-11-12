"""Verdicts du catalogue v1 de l'usine, sur donnees figees (manifestes sha256), HORS LIGNE.

Pour chaque candidat : entrainement = trades sortis avant la coupe, evaluation = trades dont le signal est apres la coupe,
trades a cheval exclus (ils sont comptes). Couts identiques pour tous, scenario frais doubles, base « ne rien trader »,
comptes par actif, funding reel. Criteres et bootstrap : ceux de la specification gelee. La specification est verifiee
et son sha256 imprime en PREMIER ; un registre dans le dossier de sortie refuse toute autre specification.
    python3 -m usine.verdicts --spec specs/USINE-SPEC-v1.json --out rapport-usine \\
        [--pit /data/pit] [--majeurs /data/majeurs] [--baleines /data/baleines]"""
import os, sys, json, argparse, datetime as dt
import numpy as np, pandas as pd
from peanut import replay as RP, replay_pit as PIT, replay_oos as OOS
from . import strategies as S, copie as C

H, H4 = 3_600_000, 4 * 3_600_000
REQUIRED = ("id", "gel_utc", "fraction_evaluation", "scenarios_frais", "criteres", "bootstrap", "prereg_sha256", "candidats")
CANDIDATS = ("M1_cassure_donchian_4h", "M2_croisement_ema_4h", "P1_cassure_volume_1h", "P2_rotation_momentum_4h", "C1_copie_baleines")

class SpecError(Exception): pass

def load_spec(path):
    spec = json.load(open(path)); miss = [k for k in REQUIRED if k not in spec]
    if miss: raise SpecError("specification incomplete : " + ", ".join(miss))
    if not 0 < float(spec["fraction_evaluation"]) < 1: raise SpecError("fraction_evaluation hors de ]0, 1[")
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise SpecError("scenarios de frais imposes : [1, 2]")
    if not {"trades_min", "pf_min", "jours_min_ic"} <= set(spec["criteres"]): raise SpecError("criteres incomplets")
    if sorted(spec["candidats"]) != sorted(CANDIDATS): raise SpecError("la liste des candidats ne correspond pas au catalogue v1")
    return spec, RP.sha_file(path)

# ------------------------------------------------------------------ donnees
def _verify(d):
    man = json.load(open(os.path.join(d, "manifest.json")))
    for rel, h in sorted(man["files"].items()):
        p = os.path.join(d, rel)
        if not os.path.exists(p) or RP.sha_file(p) != h: raise RP.Tampered(f"{rel} : absent ou empreinte differente du manifeste")
    return man

def _bars(path, end_ms, step):
    raw = json.load(open(path))
    df = pd.DataFrame(raw).rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "vol"})
    if df.empty: return df
    for c in ("open", "high", "low", "close", "vol"): df[c] = df[c].astype(float)
    df["ts"] = df["ts"].astype("int64")
    df = df[["ts", "open", "high", "low", "close", "vol"]].drop_duplicates("ts").sort_values("ts")
    return df[df.ts + step <= end_ms].reset_index(drop=True)

def _fund(path):
    fr = json.load(open(path))
    return (np.array([int(x["time"]) for x in fr], dtype="int64"), np.array([float(x["fundingRate"]) for x in fr]))

def load_majeurs(d):
    man = _verify(d); end = int(man["end_ms"])
    return man, {c: _bars(os.path.join(d, "candles", f"{c}_4h.json"), end, H4) for c in man["coins"]}, \
        {c: _fund(os.path.join(d, "funding", f"{c}.json")) for c in man["coins"]}

def load_pit(d):
    """Jeu du 01/11 : verification complete par replay_pit (manifeste), puis bougies 1 h OHLC des actifs joues."""
    man, bars, fund, h1c, order = PIT.load(d)
    end = int(man["end_ms"]); w0 = end - 5000 * 900_000
    us = PIT.universe_series(h1c, order, w0, end)
    union = sorted({c for v in us.values() for c in v})
    h1 = {c: _bars(os.path.join(d, "candles", f"{c}_1h.json"), end, H) for c in union}
    return man, {c: df for c, df in h1.items() if len(df)}, fund, us, w0, end

def load_baleines(d):
    man = _verify(d); w = {}
    for rel in man["files"]:
        if rel.startswith("fills/"):
            x = json.load(open(os.path.join(d, rel)))
            w[x["adresse"]] = {"fills": x["fills"], "compte": float(x["compte"]), "complet": bool(x["complet"])}
    return man, w

# ------------------------------------------------------------------ decoupe sans chevauchement
def split(trades, cut):
    tr, ev, straddle = [], [], []
    for t in trades:
        if t["signal_ts"] >= cut: ev.append(t)
        elif "exit_ts" in t and t["exit_ts"] <= cut: tr.append(t)
        else: straddle.append(t)
    return tr, ev, straddle

def evaluate(name, trades, t0, t1, spec):
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (t1 - t0))
    tr, ev, straddle = split(trades, cut)
    row = {"coupe_ms": cut, "coupe_utc": dt.datetime.fromtimestamp(cut / 1000, dt.timezone.utc).isoformat()[:16] + "Z",
           "fenetre_utc": [dt.datetime.fromtimestamp(x / 1000, dt.timezone.utc).isoformat()[:10] for x in (t0, t1)],
           "trades_a_cheval_exclus": len(straddle)}
    for seg, xs in (("entrainement", tr), ("evaluation", ev)):
        for m in spec["scenarios_frais"]:
            lab = "frais_base" if m == 1 else "frais_doubles"; ys = [RP.with_fees(t, float(m)) for t in xs]
            row[f"{seg}_{lab}"] = {"global": RP.metrics(ys), "par_actif": OOS.by_coin(ys)}
    bs = spec["bootstrap"]
    row["ic_evaluation_frais_doubles"] = OOS.bootstrap([RP.with_fees(t, 2.0) for t in ev], int(bs["tirages"]), int(bs["graine"]))
    row["verdict"] = OOS.verdict(row["entrainement_frais_base"]["global"], row["evaluation_frais_base"]["global"],
                                 row["evaluation_frais_doubles"]["global"], row["ic_evaluation_frais_doubles"], spec["criteres"])
    return row

# ------------------------------------------------------------------ candidats
def run_majeurs(d):
    man, bars, fund = load_majeurs(d); out = {}
    t0 = min(int(df.ts.iloc[0]) for df in bars.values()); t1 = int(man["end_ms"])
    for name, fn in (("M1_cassure_donchian_4h", S.m1_cassure_donchian), ("M2_croisement_ema_4h", S.m2_croisement_ema)):
        out[name] = ([t for c, df in sorted(bars.items()) for t in fn(c, df, fund[c])], t0, t1)
    return man, out

def run_pit(d):
    man, h1, fund, us, w0, end = load_pit(d)
    is_member = lambda coin, t: PIT.member(us, coin, t)
    p1 = [t for c, df in sorted(h1.items()) for t in S.p1_cassure_volume(c, df, fund.get(c), is_member, w0)]
    p2 = S.p2_rotation_momentum(h1, fund, lambda h: us.get(h, ()), w0, end)
    return man, {"P1_cassure_volume_1h": (p1, w0, end), "P2_rotation_momentum_4h": (p2, w0, end)}, (h1, fund, us, w0, end)

def run_copie(d, pit_ctx, spec):
    man, wallets = load_baleines(d)
    h1, fund, us, w0, end = pit_ctx
    cut = int(w0 + (1 - float(spec["fraction_evaluation"])) * (end - w0))
    chosen, why = C.select(wallets, cut)
    playable = lambda coin, t: coin in ("BTC", "ETH", "SOL") or PIT.member(us, coin, t)
    trades = C.copy_trades(wallets, chosen, h1, fund, playable, w0, end)
    info = {"wallets_telecharges": len(wallets), "wallets_retenus": chosen,
            "exclusions": {k: sum(1 for v in why.values() if v == k) for k in sorted(set(why.values()))}}
    return man, {"C1_copie_baleines": (trades, w0, end)}, info

def run(spec_path, out, pit=None, majeurs=None, baleines=None):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in ("sim.py", "strategies.py", "copie.py", "verdicts.py")}}
    runs, notes, pit_ctx = {}, {}, None
    if majeurs:
        man, r = run_majeurs(majeurs); runs.update(r); hashes["manifeste_majeurs"] = RP.sha_file(os.path.join(majeurs, "manifest.json"))
    if pit:
        man, r, pit_ctx = run_pit(pit); runs.update(r); hashes["manifeste_pit"] = RP.sha_file(os.path.join(pit, "manifest.json"))
    if baleines and pit_ctx:
        man, r, info = run_copie(baleines, pit_ctx, spec); runs.update(r); notes["copie"] = info
        hashes["manifeste_baleines"] = RP.sha_file(os.path.join(baleines, "manifest.json"))
    rows = {}
    for name in CANDIDATS:
        if name not in runs: rows[name] = {"verdict": "NON EVALUE (donnees absentes)"}; continue
        trades, t0, t1 = runs[name]; rows[name] = evaluate(name, trades, t0, t1, spec)
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "notes": notes}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(out, "verdicts.md"), "w").write(markdown(rep))
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

# ------------------------------------------------------------------ rapport
COLS = ["trades", "taux_reussite", "profit_factor", "esperance_R", "somme_R", "pire_serie_pertes", "drawdown_max_R", "funding_R", "frais_R"]
BASE = {c: 0 for c in COLS} | {"taux_reussite": None, "profit_factor": None, "esperance_R": 0.0, "somme_R": 0.0, "drawdown_max_R": 0.0, "funding_R": 0.0, "frais_R": 0.0}

def _table(rows):
    L = ["| candidat | " + " | ".join(COLS) + " |", "|" + "---|" * (len(COLS) + 1)]
    for name, m in rows: L.append(f"| {name} | " + " | ".join(RP.fmt(m.get(c)) for c in COLS) + " |")
    L.append("| ne_rien_trader | " + " | ".join(RP.fmt(BASE[c]) for c in COLS) + " |")
    return L

def markdown(rep):
    L = ["# Usine : verdicts du catalogue v1", "", "Resultats indicatifs sur donnees passees. Aucune optimisation : parametres figes par le pre-enregistrement.",
         "", "## Empreintes (sha256)"] + [f"- {k} : `{v}`" for k, v in rep["empreintes"].items()]
    L += ["", "## Verdicts (evaluation, criteres annonces)", ""]
    for name, r in rep["candidats"].items():
        extra = f" (coupe {r['coupe_utc']}, fenetre {r['fenetre_utc'][0]} au {r['fenetre_utc'][1]})" if "coupe_utc" in r else ""
        L.append(f"- **{name}** : {r['verdict']}{extra}")
    L.append("- **ne_rien_trader** : reference (0 R, aucun frais, aucun risque)")
    done = [(n, r) for n, r in rep["candidats"].items() if "coupe_utc" in r]
    for seg in ("entrainement", "evaluation"):
        for lab in ("frais_base", "frais_doubles"):
            L += ["", f"## {seg} : {lab.replace('_', ' ')}", ""] + _table([(n, r[f"{seg}_{lab}"]["global"]) for n, r in done])
    L += ["", "## Comptes par actif (evaluation, frais doubles)"]
    for n, r in done:
        L += ["", f"### {n}", "", "| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |", "|---|---|---|---|---|---|"]
        for c, m in r["evaluation_frais_doubles"]["par_actif"].items():
            L.append(f"| {c} | {m['trades']} | {RP.fmt(m['taux_reussite'])} | {RP.fmt(m['esperance_R'])} | {RP.fmt(m['somme_R'])} | {RP.fmt(m['funding_R'])} |")
        L.append("| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |")
        ic = r.get("ic_evaluation_frais_doubles")
        if ic: L.append(f"\nIC bootstrap de l'esperance (frais doubles) : [{ic['p05']} ; {ic['p95']}] R sur {ic['jours']} jours ; trades a cheval exclus : {r['trades_a_cheval_exclus']}")
    if "copie" in rep["notes"]:
        c = rep["notes"]["copie"]
        L += ["", "## Copieur : selection des wallets (avant la coupe)", f"- telecharges : {c['wallets_telecharges']} ; retenus : {len(c['wallets_retenus'])}"]
        L += [f"- exclus ({k}) : {v}" for k, v in c["exclusions"].items()]
    return "\n".join(L) + "\n"

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--pit"); ap.add_argument("--majeurs"); ap.add_argument("--baleines")
    a = ap.parse_args(argv)
    try:
        run(a.spec, a.out, a.pit, a.majeurs, a.baleines)
    except (SpecError, OOS.SpecError, RP.Tampered) as e:
        sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
