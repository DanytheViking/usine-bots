"""Lab v5 : entree en tendance M2 1 h pour Smart Peanut, selon PREREG-lab5-tendance.
M2T_1h_tendance (decisif) : sans position, entree dans le sens de EMA 50 / 200 ; sortie et retournement au croisement inverse.
M2_1h_croisement (information) : M2 au croisement seul, meme filtre de volume (Smart Peanut 2.6.0).
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_m2_tendance --spec specs/USINE-SPEC-LAB5.json --data /d/m2t --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_lab4 as VL, strategies_lab4 as L
from .sim import atr, run_position

H, D = S.H, 24 * S.H
CANDIDATS = ("M2T_1h_tendance", "M2_1h_croisement")
DECISIF = "M2T_1h_tendance"
VOLUME_MIN = 2_000_000.0
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py", "verif_m2_tendance.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "decisif", "fraction_evaluation", "stress_frais", "palier",
                        "paliers_publies", "voie_rapide", "bootstrap", "volume_min_usd") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF: raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10: raise V.SpecError("voie rapide du Lab : 40 trades et +0,10 R")
    if float(spec["palier"]) > 0.20: raise V.SpecError("borne du Lab : 20 % par trade")
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    return spec, RP.sha_file(path)

def _m2(coin, df, fund, strat, tendance):
    p = S.M2; a = atr(df).values; liq = L.liquidite(df, H)
    f = df.close.ewm(span=p["rapide"], adjust=False).mean().values
    s = df.close.ewm(span=p["lente"], adjust=False).mean().values
    up = lambda i: f[i] > s[i] and f[i - 1] <= s[i - 1]
    dn = lambda i: f[i] < s[i] and f[i - 1] >= s[i - 1]
    def sig(i):
        if np.isnan(a[i]) or np.isnan(liq[i]) or liq[i] < VOLUME_MIN: return None
        if tendance: return ("long" if f[i] > s[i] else "short", p["stop_atr"] * a[i])
        if up(i): return ("long", p["stop_atr"] * a[i])
        if dn(i): return ("short", p["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, strat, H, fund, exit_fn=dn if side == "long" else up)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return S._flat_loop(df, p["lente"], sig, opn)

def m2_tendance(coin, df, fund): return _m2(coin, df, fund, "M2T_1h_tendance", True)
def m2_croisement(coin, df, fund): return _m2(coin, df, fund, "M2_1h_croisement", False)

def evaluate(name, trades, t0, t1, spec):
    row = VL.evaluate(name, trades, t0, t1, {**spec, "max_positions": 10 ** 6})
    vr = spec["voie_rapide"]; e = row["evaluation_frais_doubles"]; g = row["croissance_palier"]
    manque = []
    if e["trades"] < int(vr["trades_min"]): manque.append(f"moins de {vr['trades_min']} trades ({e['trades']})")
    if e["esperance_R"] is None or e["esperance_R"] < float(vr["esperance_min_R"]): manque.append(f"esperance < +{vr['esperance_min_R']} R ({RP.fmt(e['esperance_R'])})")
    if g is None or g <= 0: manque.append(f"croissance composee a {int(round(100 * float(spec['palier'])))} % non positive")
    row["verdict"] = "PASSE LA VOIE RAPIDE" if not manque else "NE PASSE PAS : " + " ; ".join(manque)
    return row

def decide(row):
    e = row["evaluation_frais_doubles"]["esperance_R"]
    if e is None: return "AUCUN TRADE en evaluation : pas de recommandation"
    if row["verdict"] == "PASSE LA VOIE RAPIDE":
        return "PASSE : proposee a Richard pour le reel au Lab a 2 %, apres sa confirmation ecrite, les tests et l'audit d'Aristote"
    if e < 0: return "ESPERANCE NEGATIVE : recommandation de ne pas la mettre en reel"
    return "ESPERANCE >= 0 SANS PASSER LA VOIE RAPIDE : reel seulement sur exception ecrite de Richard"

def markdown(rep):
    out = ["# Lab v5 : entree en tendance M2 1 h (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
           f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "", "Evaluation, frais doubles.", "",
           "| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | baisse max (R) | ln a 2 % | ln a 10 % | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3, ic, g = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"], r["ic_evaluation_frais_doubles"] or {}, r["croissance_ln"]
        out.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                   f"[{RP.fmt(ic.get('p05'))} ; {RP.fmt(ic.get('p95'))}] | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                   f"{RP.fmt(s3['esperance_R'])} | {e.get('pire_serie_pertes', '–')} | {RP.fmt(e.get('drawdown_max_R'))} | {RP.fmt(g.get('2 %'))} | {RP.fmt(g.get('10 %'))} | {r['verdict']} |")
    out += ["", f"Actifs du jeu : {', '.join(rep['notes']['coins'])}", ""]
    return "\n".join(out)

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man = V._verify(data); end = int(man["end_ms"]); t0 = int(man["debut_1h_ms"])
    b1 = {c: V._bars(os.path.join(data, "candles", f"{c}_1h.json"), end, H) for c in man["coins"]}
    b1 = {c: x for c, x in b1.items() if len(x)}
    fund = {c: V._fund(os.path.join(data, "funding", f"{c}.json")) for c in b1}
    runs = {"M2T_1h_tendance": [t for c, x in sorted(b1.items()) for t in m2_tendance(c, x, fund.get(c))],
            "M2_1h_croisement": [t for c, x in sorted(b1.items()) for t in m2_croisement(c, x, fund.get(c))]}
    rows = {n: evaluate(n, runs[n], t0, end, spec) for n in CANDIDATS}
    decision = decide(rows[DECISIF])
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "decision": decision, "notes": {"coins": sorted(b1)}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(out, "verdicts.md"), "w").write(markdown(rep))
    print(decision)
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

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
