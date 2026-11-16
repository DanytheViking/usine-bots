"""Test de M2 en 1 h sur les actifs de Moonshot, selon PREREG-moonshot-m2-1h.
M2_1h_moonshot (decisif) : M2 inchange sur bougies 1 h. M2_4h_reconstruit (information) : M2 4 h sur les memes bougies agregees.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
--attendre N : attend jusqu'a N secondes que le manifeste du jeu existe (collecte lancee par un travail voisin).
    python3 -m usine.verif_m2_1h --spec specs/USINE-SPEC-M2H1.json --data /d/m2h1 --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np, pandas as pd
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_v3 as V3, verdicts_lab4 as VL

H, H4, D = S.H, S.H4, 24 * S.H
CANDIDATS = ("M2_1h_moonshot", "M2_4h_reconstruit")
DECISIF = "M2_1h_moonshot"
FICHIERS = ("sim.py", "strategies.py", "verdicts.py", "verdicts_v3.py", "verif_m2_1h.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in V.REQUIRED + ("stress_frais", "decisif") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise V.SpecError("scenarios de frais imposes : [1, 2]")
    if float(spec["criteres"].get("pf_min", 0)) < 1.35: raise V.SpecError("PF minimal : 1,35 (priorite 1)")
    if int(spec["criteres"].get("trades_min", 0)) < 30: raise V.SpecError("au moins 30 trades")
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF: raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    return spec, RP.sha_file(path)

def load(d):
    man = V._verify(d); end = int(man["end_ms"])
    b1 = {c: V._bars(os.path.join(d, "candles", f"{c}_1h.json"), end, H) for c in man["coins"]}
    fund = {c: V._fund(os.path.join(d, "funding", f"{c}.json")) for c in man["coins"]}
    return man, {c: x for c, x in b1.items() if len(x)}, fund

def vers_4h(df):
    """Agrege des bougies 1 h en bougies 4 h UTC ; seules les tranches completes (4 bougies) sont gardees."""
    g = df.assign(k=df.ts // H4 * H4).groupby("k")
    x = pd.DataFrame({"ts": g.ts.first() // H4 * H4, "open": g.open.first(), "high": g.high.max(), "low": g.low.min(),
                      "close": g.close.last(), "vol": g.vol.sum(), "n": g.ts.count()})
    return x[x.n == 4].drop(columns="n").reset_index(drop=True)

def m2(coin, df, fund, tf_ms, nom):
    return [{**t, "strat": nom} for t in S.m2_croisement_ema(coin, df, fund, tf_ms=tf_ms)]

def run_all(b1, fund):
    b4 = {c: vers_4h(x) for c, x in b1.items()}
    return {"M2_1h_moonshot": ([t for c, x in sorted(b1.items()) for t in m2(c, x, fund.get(c), H, "M2_1h_moonshot")], b1, H),
            "M2_4h_reconstruit": ([t for c, x in sorted(b4.items()) for t in m2(c, x, fund.get(c), H4, "M2_4h_reconstruit")], b4, H4)}

def frequence(row, t0, t1):
    """Trades par mois (30 jours) en evaluation, tous actifs confondus."""
    jours = max((t1 - row["coupe_ms"]) / D, 1e-9)
    return round(30 * row["evaluation_frais_doubles"]["global"]["trades"] / jours, 1)

def decide(row):
    """Regle de decision pre-enregistree, sur M2_1h_moonshot (evaluation, frais doubles)."""
    ev = row["evaluation_frais_doubles"]["global"]; e2 = ev["esperance_R"]
    if e2 is None or ev["trades"] == 0: return "AUCUN TRADE en evaluation : pas de recommandation"
    if row["verdict"].startswith("AVANTAGE"):
        return "AVANTAGE : papier deux semaines, puis reel au risque de Moonshot sur un sous-compte cree par Richard (option 4c)"
    if e2 < 0: return "ESPERANCE NEGATIVE : M2 1 h abandonne pour Moonshot, sans nouveau reglage"
    return "ESPERANCE >= 0 SANS AVANTAGE DEMONTRE : rien en reel sur la foi de ce test (Richard reste libre d'une exception ecrite)"

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man, b1, fund = load(data); end = int(man["end_ms"])
    t0 = int(man["debut_1h_ms"])
    runs = run_all(b1, fund)
    rows = {}
    for n in CANDIDATS:
        trades, bars, tf = runs[n]
        r = V3.evaluate(n, trades, t0, end, bars, tf, spec)
        r["trades_par_mois"] = frequence(r, t0, end)
        rows[n] = r
    decision = decide(rows[DECISIF])
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "decision": decision, "notes": {"coins": man["coins"]}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(out, "verdicts.md"), "w").write(markdown(rep))
    print(decision)
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

def markdown(rep):
    L = ["# Test de M2 en 1 h sur les actifs de Moonshot", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
         f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "",
         "Evaluation, frais doubles. M2_1h_moonshot decide ; M2_4h_reconstruit est publie pour comparer le regime.", "",
         "| candidat | trades eval. | trades / mois | esperance (R) | PF | IC 5 % | entrainement (R) | frais x3 (R) | pire serie | acheter et garder | verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t = r["evaluation_frais_doubles"]["global"], r["entrainement_frais_doubles"]["global"]
        s3, bh, ic = r["evaluation_frais_stress"]["global"], r["acheter_et_garder"], r["ic_evaluation_frais_doubles"]
        lo = ic.get("p05") if isinstance(ic, dict) else None
        L.append(f"| {n} | {e['trades']} | {r['trades_par_mois']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | {RP.fmt(lo)} | "
                 f"{RP.fmt(t['esperance_R'])} | {RP.fmt(s3['esperance_R'])} | {e.get('pire_serie_pertes', '–')} | "
                 f"{bh['rendement_pct'] if bh['rendement_pct'] is not None else '–'} % | {r['verdict']} |")
    L += ["", f"Actifs du jeu : {', '.join(rep['notes']['coins'])}", ""]
    return "\n".join(L)

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--spec", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--attendre", type=int, default=0)
    a = ap.parse_args(argv)
    try:
        if a.attendre: VL.attendre(a.data, a.attendre)
        run(a.spec, a.data, a.out)
    except (V.SpecError, OOS.SpecError, RP.Tampered) as e: sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
