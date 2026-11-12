"""Verification de M2 sur les memecoins du jeu v3 (Smart Peanut v2), selon PREREG-verif-M2-memecoins.
Vue B (decisive) : filtre de volume 24 h >= 2 M$ a l'entree, comme le bot reel. Vue A : sans filtre (information).
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_m2_memes --spec specs/USINE-SPEC-M2MEMES.json --data /data/v3 --out rapport-m2-memes"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_v3 as V3

H4 = 4 * 3_600_000
VOLUME_MIN = 2_000_000.0
VUES = ("M2_memes_filtre_volume", "M2_memes_sans_filtre")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in V.REQUIRED + ("stress_frais", "volume_min_usd") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise V.SpecError("scenarios de frais imposes : [1, 2]")
    if float(spec["criteres"].get("pf_min", 0)) < 1.2: raise V.SpecError("PF minimal : 1,2")
    if sorted(spec["candidats"]) != sorted(VUES): raise V.SpecError("vues attendues : " + ", ".join(VUES))
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    return spec, RP.sha_file(path)

def vol24(df):
    """Volume en dollars des 24 h closes a la cloture de chaque bougie (6 bougies 4 h)."""
    return (df.vol * df.close).rolling(6, min_periods=6).sum().values

def m2_filtre(coin, df, fund):
    """M2 dont chaque entree (retournement compris) exige un volume 24 h >= 2 M$ a la cloture du signal."""
    v = vol24(df)
    return _replay(coin, df, fund, lambda i: not np.isnan(v[i]) and v[i] >= VOLUME_MIN)

def _replay(coin, df, fund, ok):
    p = S.M2; a = S.atr(df).values
    f = df.close.ewm(span=p["rapide"], adjust=False).mean().values
    s = df.close.ewm(span=p["lente"], adjust=False).mean().values
    up = lambda i: f[i] > s[i] and f[i - 1] <= s[i - 1]
    dn = lambda i: f[i] < s[i] and f[i - 1] >= s[i - 1]
    def sig(i):
        if np.isnan(a[i]) or not ok(i): return None
        if up(i): return ("long", p["stop_atr"] * a[i])
        if dn(i): return ("short", p["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        tr, k = S.run_position(df, i, side, dist, coin, "M2_memes", H4, fund, exit_fn=dn if side == "long" else up)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return S._flat_loop(df, p["lente"], sig, opn)

def decide(row):
    """Regle de decision pre-enregistree, sur la vue filtre volume (evaluation, frais doubles)."""
    ev = row["evaluation_frais_doubles"]["global"]; e2 = ev["esperance_R"]
    if e2 is None or ev["trades"] == 0: return "AUCUN TRADE en evaluation : pas de recommandation"
    if e2 < 0: return "ESPERANCE NEGATIVE : recommandation de mettre Smart Peanut en pause (decision de Richard)"
    if row["verdict"].startswith("AVANTAGE"): return "AVANTAGE DEMONTRE : Smart Peanut continue"
    return "ESPERANCE >= 0 SANS AVANTAGE DEMONTRE : Smart Peanut continue a 1 %, sans augmentation"

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in ("sim.py", "strategies.py", "verdicts.py", "verif_m2_memes.py")},
              "manifeste_v3": RP.sha_file(os.path.join(data, "manifest.json"))}
    man, b4, _, fund, _ = V3.load(data); end = int(man["end_ms"])
    t0 = min(int(x.ts.iloc[0]) for x in b4.values())
    runs = {"M2_memes_filtre_volume": [t for c, x in sorted(b4.items()) for t in m2_filtre(c, x, fund.get(c))],
            "M2_memes_sans_filtre": [t for c, x in sorted(b4.items()) for t in _replay(c, x, fund.get(c), lambda i: True)]}
    rows = {n: V3.evaluate(n, runs[n], t0, end, b4, H4, spec) for n in VUES}
    decision = decide(rows["M2_memes_filtre_volume"])
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "decision": decision, "notes": {"memes": man["memes"]}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    md = V.markdown(rep).replace("catalogue v1", "verification M2 sur les memecoins (Smart Peanut v2)")
    L = ["", "## Decision pre-enregistree (vue filtre volume, evaluation, frais doubles)", "", f"**{decision}**", "",
         "## Testeur durci", "", "| vue | trades eval. | esperance frais x3 (R) | PF frais x3 | somme R x 1 % | acheter et garder | actifs dont l'avantage depend |",
         "|---|---|---|---|---|---|---|"]
    for n, r in rows.items():
        s3 = r["evaluation_frais_stress"]["global"]; bh = r["acheter_et_garder"]
        L.append(f"| {n} | {s3['trades']} | {RP.fmt(s3['esperance_R'])} | {RP.fmt(s3['profit_factor'])} | {r['strategie_1pc_pct']} % | "
                 f"{bh['rendement_pct'] if bh['rendement_pct'] is not None else '–'} % ({bh['actifs']} actifs) | {', '.join(r.get('dependant_de', [])) or '–'} |")
    open(os.path.join(out, "verdicts.md"), "w").write(md + "\n".join(L) + "\n")
    print(decision)
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try: run(a.spec, a.data, a.out)
    except (V.SpecError, OOS.SpecError, RP.Tampered) as e: sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
