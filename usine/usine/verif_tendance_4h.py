"""Lab v8 « Tendance 4 h confirmee » pour Smart Peanut, selon PREREG-lab8-tendance-4h.
T4H_confirmee (decisif) : sans position, entree dans le sens de EMA 50 / 200 en 4 h quand la cloture est du bon cote de l'EMA 50,
stop 3 x ATR(14), sortie au croisement inverse.
T4H_tendance (information) : memes regles sans la condition sur l'EMA 50. M2_4h_croisement (temoin) : M2 au croisement seul.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_tendance_4h --spec specs/USINE-SPEC-LAB8.json --data /d/t4h --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_lab4 as VL, strategies_lab4 as L
from .sim import atr, run_position

H4 = S.H4
CANDIDATS = ("T4H_confirmee", "T4H_tendance", "M2_4h_croisement")
DECISIF, TEMOIN = "T4H_confirmee", "M2_4h_croisement"
VOLUME_MIN = 2_000_000.0
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py", "verif_tendance_4h.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "decisif", "temoin", "fraction_evaluation", "stress_frais", "palier",
                        "paliers_publies", "voie_rapide", "bootstrap", "volume_min_usd", "max_positions") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF or spec["temoin"] != TEMOIN:
        raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10: raise V.SpecError("voie rapide du Lab : 40 trades et +0,10 R")
    if float(spec["palier"]) > 0.20: raise V.SpecError("borne du Lab : 20 % par trade")
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    if not 1 <= int(spec["max_positions"]) <= 2: raise V.SpecError("plafond du Lab : deux positions au plus")
    return spec, RP.sha_file(path)

def tendance(coin, df, fund, confirme=True):
    """Entree dans la tendance EMA 50 / 200 en 4 h ; avec confirme, seulement si la cloture est du cote de la tendance par rapport a l'EMA 50."""
    strat = "T4H_confirmee" if confirme else "T4H_tendance"
    p = S.M2; a = atr(df).values; liq = L.liquidite(df, H4); cl = df.close.values
    f = df.close.ewm(span=p["rapide"], adjust=False).mean().values
    s = df.close.ewm(span=p["lente"], adjust=False).mean().values
    up = lambda i: f[i] > s[i] and f[i - 1] <= s[i - 1]
    dn = lambda i: f[i] < s[i] and f[i - 1] >= s[i - 1]
    def sig(i):
        if np.isnan(a[i]) or np.isnan(liq[i]) or liq[i] < VOLUME_MIN: return None
        side = "long" if f[i] > s[i] else "short"
        if confirme and not (cl[i] > f[i] if side == "long" else cl[i] < f[i]): return None
        return (side, p["stop_atr"] * a[i])
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, strat, H4, fund, exit_fn=dn if side == "long" else up)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return S._flat_loop(df, p["lente"], sig, opn)

def croisement(coin, df, fund):
    return [{**t, "strat": "M2_4h_croisement"} for t in S.m2_croisement_ema(coin, df, fund)]

def evaluate(name, trades, t0, t1, spec):
    row = VL.evaluate(name, trades, t0, t1, spec)
    vr = spec["voie_rapide"]; e = row["evaluation_frais_doubles"]; g = row["croissance_palier"]
    manque = []
    if e["trades"] < int(vr["trades_min"]): manque.append(f"moins de {vr['trades_min']} trades ({e['trades']})")
    if e["esperance_R"] is None or e["esperance_R"] < float(vr["esperance_min_R"]): manque.append(f"esperance < +{vr['esperance_min_R']} R ({RP.fmt(e['esperance_R'])})")
    if g is None or g <= 0: manque.append(f"croissance composee a {int(round(100 * float(spec['palier'])))} % non positive")
    row["verdict"] = "PASSE LA VOIE RAPIDE" if not manque else "NE PASSE PAS : " + " ; ".join(manque)
    return row

def decide(row, spec):
    e = row["evaluation_frais_doubles"]; esp = e["esperance_R"]
    if esp is None or e["trades"] < int(spec["voie_rapide"]["trades_min"]):
        return f"NON CONCLUANT : {e['trades']} trades en evaluation ({spec['voie_rapide']['trades_min']} exiges), aucun seuil retouche"
    if row["verdict"] != "PASSE LA VOIE RAPIDE":
        if esp < 0: return "ESPERANCE NEGATIVE : abandon sans nouveau reglage"
        return "NE PASSE PAS LA VOIE RAPIDE : rien en reel"
    tr, s3 = row["entrainement_frais_doubles"]["esperance_R"], row["esperance_sans_3_meilleurs_R"]
    if all(x is not None and x > 0 for x in (tr, s3)):
        return "NIVEAU REEL : propose a Richard pour remplacer M2T 1 h au Lab a 2 %, apres sa confirmation ecrite, le code du bot, les tests et l'audit d'Aristote"
    return "NIVEAU PAPIER : deux semaines en observation (aucun ordre) avant toute proposition de reel"

def markdown(rep):
    out = ["# Lab v8 : Tendance 4 h confirmee (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
           f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "", "Evaluation, frais doubles, deux positions au plus.", "",
           "| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3, ic, g = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"], r["ic_evaluation_frais_doubles"] or {}, r["croissance_ln"]
        out.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                   f"[{RP.fmt(ic.get('p05'))} ; {RP.fmt(ic.get('p95'))}] | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                   f"{RP.fmt(s3['esperance_R'])} | {e.get('pire_serie_pertes', 'n/d')} | {RP.fmt(e.get('drawdown_max_R'))} | "
                   f"{RP.fmt(g.get('2 %'))} | {RP.fmt(g.get('5 %'))} | {RP.fmt(g.get('10 %'))} | {r['verdict']} |")
    out += ["", f"Actifs du jeu : {', '.join(rep['notes']['coins'])}", ""]
    return "\n".join(out)

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man = V._verify(data); end = int(man["end_ms"]); t0 = int(man["debut_4h_ms"])
    b1 = {c: V._bars(os.path.join(data, "candles", f"{c}_4h.json"), end, H4) for c in man["coins"]}
    b1 = {c: x for c, x in b1.items() if len(x)}
    fund = {c: V._fund(os.path.join(data, "funding", f"{c}.json")) for c in b1}
    runs = {"T4H_confirmee": [t for c, x in sorted(b1.items()) for t in tendance(c, x, fund.get(c))],
            "T4H_tendance": [t for c, x in sorted(b1.items()) for t in tendance(c, x, fund.get(c), confirme=False)],
            "M2_4h_croisement": [t for c, x in sorted(b1.items()) for t in croisement(c, x, fund.get(c))]}
    rows = {n: evaluate(n, runs[n], t0, end, spec) for n in CANDIDATS}
    decision = decide(rows[DECISIF], spec)
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
