"""Verdicts du catalogue v3 (ligne Chasseur, T1 a T5) avec le Testeur durci (addendum v3, point A) :
  - base « acheter et garder » en plus de « ne rien trader » ;
  - scenario de stress a frais x 3 publie (le critere d'esperance reste au scenario x 2) ;
  - leave-one-asset-out : un candidat dont l'avantage disparait sans un seul actif ne passe pas ;
  - seuil de PF releve a 1,35 (cinq candidats testes ensemble) ;
  - perps delistes inclus quand l'historique existe.
Hors ligne, sur donnees figees ; le sha256 de la specification est imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verdicts_v3 --spec specs/USINE-SPEC-v3.json --data /data/v3 --out rapport-usine-v3"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies_v3 as S3, verdicts as V

H, H4, D = 3_600_000, 4 * 3_600_000, 24 * 3_600_000
CANDIDATS_V3 = ("T1_tortue", "T2_tortue_disciplinee", "T3_druckenmiller", "T4_contrarien", "T5_listings")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in V.REQUIRED + ("stress_frais",) if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise V.SpecError("scenarios de frais imposes : [1, 2]")
    if float(spec["criteres"].get("pf_min", 0)) < 1.35: raise V.SpecError("le lot v3 exige un PF minimal de 1,35")
    if sorted(spec["candidats"]) != sorted(CANDIDATS_V3): raise V.SpecError("la liste des candidats ne correspond pas au catalogue v3")
    return spec, RP.sha_file(path)

def load(d):
    man = V._verify(d); end = int(man["end_ms"])
    b4 = {c: V._bars(os.path.join(d, "candles", f"{c}_4h.json"), end, H4) for c in man["memes"]}
    b1 = {c: V._bars(os.path.join(d, "candles", f"{c}_1h.json"), end, H) for c in sorted(set(man["memes"]) | set(man["listings"]))}
    fund = {c: V._fund(os.path.join(d, "funding", f"{c}.json")) for c in sorted(set(man["memes"]) | set(man["listings"]))}
    btc = V._bars(os.path.join(d, "candles", "BTC_1d.json"), end, D)
    return man, {c: x for c, x in b4.items() if len(x)}, {c: x for c, x in b1.items() if len(x)}, fund, btc

def run_all(d):
    man, b4, b1, fund, btc = load(d); end = int(man["end_ms"])
    t0_4 = min(int(x.ts.iloc[0]) for x in b4.values()) if b4 else end
    t0_1 = int(man["debut_1h_ms"])
    allow = S3.btc_regime(btc)
    memes1 = {c: b1[c] for c in man["memes"] if c in b1}
    runs = {
        "T1_tortue": ([t for c, x in sorted(b4.items()) for t in S3.t1_tortue(c, x, fund.get(c))], t0_4, end, b4, H4),
        "T2_tortue_disciplinee": ([t for c, x in sorted(b4.items()) for t in S3.t2_tortue_disciplinee(c, x, fund.get(c), allow)], t0_4, end, b4, H4),
        "T3_druckenmiller": (S3.t3_druckenmiller(b4, fund, t0_4, end), t0_4, end, b4, H4),
        "T4_contrarien": ([t for c, x in sorted(memes1.items()) for t in S3.t4_contrarien(c, x, fund.get(c))], t0_1, end, memes1, H),
        "T5_listings": ([t for c in man["listings"] if c in b1 for t in S3.t5_listings(c, b1[c], fund.get(c), int(b1[c].ts.iloc[0]))],
                        t0_1, end, {c: b1[c] for c in man["listings"] if c in b1}, H),
    }
    return man, runs

def buy_and_hold(bars, cut, t1, tf):
    """Rendement moyen (en %) d'une position longue sans levier, egalement ponderee, de la coupe a la fin, sur les actifs cotes a la coupe."""
    rs = []
    for c, x in bars.items():
        ts = x.ts.values; k = int(np.searchsorted(ts, cut))
        if k >= len(ts) or ts[0] > cut: continue
        rs.append(float(x.close.values[-1] / x.open.values[k] - 1))
    return {"actifs": len(rs), "rendement_pct": round(100 * float(np.mean(rs)), 2) if rs else None}

def loao(trades, t0, t1, spec):
    """Recalcule le verdict sans chaque actif, a tour de rôle. Renvoie la liste des actifs dont le retrait fait perdre l'avantage."""
    coins = sorted({t["coin"] for t in trades}); weak = []
    for c in coins:
        r = V.evaluate("x", [t for t in trades if t["coin"] != c], t0, t1, spec)
        if not r["verdict"].startswith("AVANTAGE"): weak.append(c)
    return weak

def evaluate(name, trades, t0, t1, bars, tf, spec):
    row = V.evaluate(name, trades, t0, t1, spec)
    _, ev, _ = V.split(trades, row["coupe_ms"])
    m3 = float(spec["stress_frais"])
    row["evaluation_frais_stress"] = {"global": RP.metrics([RP.with_fees(t, m3) for t in ev])}
    row["acheter_et_garder"] = buy_and_hold(bars, row["coupe_ms"], t1, tf)
    s2 = row["evaluation_frais_doubles"]["global"]["somme_R"] or 0.0
    row["strategie_1pc_pct"] = round(s2 * 1.0, 2)
    if row["verdict"].startswith("AVANTAGE"):
        weak = loao(trades, t0, t1, spec); row["dependant_de"] = weak
        if weak: row["verdict"] = "PAS D'AVANTAGE : depend d'un seul actif (" + ", ".join(weak) + ")"
    return row

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in ("sim.py", "strategies.py", "strategies_v3.py", "verdicts.py", "verdicts_v3.py")},
              "manifeste_v3": RP.sha_file(os.path.join(data, "manifest.json"))}
    man, runs = run_all(data)
    rows = {name: evaluate(name, *runs[name][:3], runs[name][3], runs[name][4], spec) for name in CANDIDATS_V3}
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows,
           "notes": {"memes": man["memes"], "listings": man["listings"]}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    md = V.markdown(rep).replace("catalogue v1", "catalogue v3 (Team Chasseur)")
    L = ["", "## Testeur durci", "", "| candidat | trades eval. | esperance frais x3 (R) | PF frais x3 | strategie a 1 % (somme R x 1 %) | acheter et garder | actifs dont l'avantage depend |",
         "|---|---|---|---|---|---|---|"]
    for n, r in rows.items():
        s3 = r["evaluation_frais_stress"]["global"]; bh = r["acheter_et_garder"]
        L.append(f"| {n} | {s3['trades']} | {RP.fmt(s3['esperance_R'])} | {RP.fmt(s3['profit_factor'])} | {r['strategie_1pc_pct']} % | "
                 f"{bh['rendement_pct'] if bh['rendement_pct'] is not None else '–'} % ({bh['actifs']} actifs) | {', '.join(r.get('dependant_de', [])) or '–'} |")
    L += ["", f"Memecoins du jeu : {', '.join(man['memes'])}", f"Listings de la fenetre 1 h : {', '.join(man['listings']) or 'aucun'}", ""]
    open(os.path.join(out, "verdicts.md"), "w").write(md + "\n".join(L))
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try: run(a.spec, a.data, a.out)
    except (V.SpecError, OOS.SpecError, RP.Tampered) as e: sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
