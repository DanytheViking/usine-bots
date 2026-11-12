"""Verdicts du catalogue v2 (M2_etendu, C1_v2), sur donnees figees, HORS LIGNE. Memes couts, decoupe, criteres et
rapport que la v1 ; le sha256 de la specification v2 est imprime en PREMIER et le registre refuse toute autre specification.
    python3 -m usine.verdicts_v2 --spec specs/USINE-SPEC-v2.json --out rapport-usine-v2 \\
        --etendu /data/etendu --baleines2 /data/baleines2 [--majeurs /data/majeurs]"""
import os, sys, json, argparse
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, copie as C, verdicts as V

H, H4 = 3_600_000, 4 * 3_600_000
CANDIDATS_V2 = ("M2_etendu", "C1_v2")
INFO = "M2_13_actifs_information"

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in V.REQUIRED if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise V.SpecError("scenarios de frais imposes : [1, 2]")
    if not {"trades_min", "pf_min", "jours_min_ic"} <= set(spec["criteres"]): raise V.SpecError("criteres incomplets")
    if sorted(spec["candidats"]) != sorted(CANDIDATS_V2): raise V.SpecError("la liste des candidats ne correspond pas au catalogue v2")
    return spec, RP.sha_file(path)

def m2_trades(bars, fund):
    out = []
    for c, df in sorted(bars.items()):
        for t in S.m2_croisement_ema(c, df, fund[c]): out.append({**t, "strat": "M2_croisement_ema_4h"})
    return out

def run_etendu(d, majeurs=None):
    man, bars, fund = V.load_majeurs(d)
    t0 = min(int(df.ts.iloc[0]) for df in bars.values()); t1 = int(man["end_ms"])
    runs = {"M2_etendu": (m2_trades(bars, fund), t0, t1)}
    if majeurs:
        man2, b2, f2 = V.load_majeurs(majeurs)
        allb, allf = {**bars, **b2}, {**fund, **f2}
        t0b = min(int(df.ts.iloc[0]) for df in allb.values()); t1b = max(t1, int(man2["end_ms"]))
        runs[INFO] = (m2_trades(allb, allf), t0b, t1b)
    return man, runs

def load_baleines2(d):
    man, wallets = V.load_baleines(d); end = int(man["end_ms"])
    h1 = {c: V._bars(os.path.join(d, "candles", f"{c}_1h.json"), end, H) for c in man["coins"]}
    fund = {c: V._fund(os.path.join(d, "funding", f"{c}.json")) for c in man["coins"]}
    return man, wallets, {c: df for c, df in h1.items() if len(df)}, fund

def run_c1(d, spec):
    man, wallets, h1, fund = load_baleines2(d)
    t0, t1 = int(man["debut_ms"]), int(man["end_ms"])
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (t1 - t0))
    chosen, why = C.select(wallets, cut)
    joues = set(h1)
    trades = [{**t, "strat": "C1_v2"} for t in C.copy_trades(wallets, chosen, h1, fund, lambda c, t: c in joues, t0, t1)]
    info = {"wallets_telecharges": len(wallets), "wallets_retenus": chosen,
            "exclusions": {k: sum(1 for v in why.values() if v == k) for k in sorted(set(why.values()))}}
    return man, {"C1_v2": (trades, t0, t1)}, info

def run(spec_path, out, etendu=None, baleines2=None, majeurs=None):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in ("sim.py", "strategies.py", "copie.py", "verdicts.py", "verdicts_v2.py")}}
    runs, notes = {}, {}
    if etendu:
        man, r = run_etendu(etendu, majeurs); runs.update(r); hashes["manifeste_etendu"] = RP.sha_file(os.path.join(etendu, "manifest.json"))
        notes["actifs_etendu"] = man["coins"]
    if baleines2:
        man, r, info = run_c1(baleines2, spec); runs.update(r); notes["copie"] = info
        hashes["manifeste_baleines2"] = RP.sha_file(os.path.join(baleines2, "manifest.json"))
    rows = {}
    for name in CANDIDATS_V2 + ((INFO,) if INFO in runs else ()):
        if name not in runs: rows[name] = {"verdict": "NON EVALUE (donnees absentes)"}; continue
        trades, t0, t1 = runs[name]; rows[name] = V.evaluate(name, trades, t0, t1, spec)
    if INFO in rows and "verdict" in rows[INFO]: rows[INFO]["verdict"] = "INFORMATION SEULEMENT : " + rows[INFO]["verdict"]
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "notes": notes}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    md = V.markdown(rep).replace("catalogue v1", "catalogue v2")
    if "actifs_etendu" in notes: md += f"\nActifs de M2_etendu (regle du pre-enregistrement v2) : {', '.join(notes['actifs_etendu'])}\n"
    open(os.path.join(out, "verdicts.md"), "w").write(md)
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--etendu"); ap.add_argument("--baleines2"); ap.add_argument("--majeurs")
    a = ap.parse_args(argv)
    try:
        run(a.spec, a.out, a.etendu, a.baleines2, a.majeurs)
    except (V.SpecError, OOS.SpecError, RP.Tampered) as e:
        sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
