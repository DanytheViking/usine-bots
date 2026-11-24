"""Lab v6 « Furie Momentum » pour Smart Peanut, selon PREREG-lab6-furie-momentum.
FM_1h_furie (decisif) : tendance EMA 50 / 200 1 h, entree sur cassure du plus haut (plus bas) des 24 bougies precedentes,
stop 3 x ATR(14), sortie a la cloture de l'autre cote de l'EMA 50.
FM_1h_pyramide (information) : FM_1h_furie avec au plus un ajout de meme risque sur une position gagnante.
M2T_1h_tendance (temoin) : regles du Lab v5 inchangees.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_furie --spec specs/USINE-SPEC-LAB6.json --data /d/fm --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_lab4 as VL, strategies_lab4 as L, verif_m2_tendance as VT
from .sim import atr, run_position

H = S.H
FM = {"canal": 24, "stop_atr": 3.0, "ajout_R": 1.0}
CANDIDATS = ("FM_1h_furie", "FM_1h_pyramide", "M2T_1h_tendance")
DECISIF, TEMOIN = "FM_1h_furie", "M2T_1h_tendance"
VOLUME_MIN = 2_000_000.0
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py", "verif_m2_tendance.py", "verif_furie.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "decisif", "temoin", "fraction_evaluation", "stress_frais", "palier",
                        "palier_furie", "paliers_publies", "voie_rapide", "bootstrap", "volume_min_usd", "max_positions") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF or spec["temoin"] != TEMOIN:
        raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10: raise V.SpecError("voie rapide du Lab : 40 trades et +0,10 R")
    if max(float(spec["palier"]), float(spec["palier_furie"])) > 0.20: raise V.SpecError("borne du Lab : 20 % par trade")
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    if not 1 <= int(spec["max_positions"]) <= 2: raise V.SpecError("plafond du Lab : deux positions au plus")
    return spec, RP.sha_file(path)

def furie(coin, df, fund, pyramide=False):
    """Trades de Furie Momentum sur un actif. Avec pyramide, un ajout au plus par position (trade separe, strat FM_1h_pyramide)."""
    strat = "FM_1h_pyramide" if pyramide else "FM_1h_furie"
    a = atr(df).values; liq = L.liquidite(df, H); cl = df.close.values; n = FM["canal"]
    f = df.close.ewm(span=S.M2["rapide"], adjust=False).mean().values
    s = df.close.ewm(span=S.M2["lente"], adjust=False).mean().values
    hh = df.high.rolling(n).max().shift(1).values; ll = df.low.rolling(n).min().shift(1).values
    casse_haut = lambda i: not np.isnan(hh[i]) and cl[i] > hh[i]
    casse_bas = lambda i: not np.isnan(ll[i]) and cl[i] < ll[i]
    ajouts = []
    def sig(i):
        if np.isnan(a[i]) or np.isnan(liq[i]) or liq[i] < VOLUME_MIN: return None
        if f[i] > s[i] and casse_haut(i): return ("long", FM["stop_atr"] * a[i])
        if f[i] < s[i] and casse_bas(i): return ("short", FM["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        sortie = (lambda k: cl[k] < f[k]) if side == "long" else (lambda k: cl[k] > f[k])
        tr, k = run_position(df, i, side, dist, coin, strat, H, fund, exit_fn=sortie)
        if pyramide and tr and "R" in tr:
            sgn = 1 if side == "long" else -1; e = tr["entry"]; R = abs(e - tr["stop"])
            casse = casse_haut if side == "long" else casse_bas
            for m in range(i + 1, k):
                if sgn * (cl[m] - e) >= FM["ajout_R"] * R and casse(m) and not np.isnan(a[m]):
                    fin = lambda q, k=k: q >= k or sortie(q)                     # l'ajout sort au plus tard apres la sortie de la position
                    t2, _ = run_position(df, m, side, FM["stop_atr"] * a[m], coin, strat, H, fund, exit_fn=fin)
                    if t2 and "R" in t2: ajouts.append({**t2, "ajout": True})
                    break
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    base = S._flat_loop(df, S.M2["lente"], sig, opn)
    return base + ajouts

def evaluate(name, trades, t0, t1, spec):
    row = VL.evaluate(name, trades, t0, t1, spec)
    vr = spec["voie_rapide"]; e = row["evaluation_frais_doubles"]; g = row["croissance_palier"]
    manque = []
    if e["trades"] < int(vr["trades_min"]): manque.append(f"moins de {vr['trades_min']} trades ({e['trades']})")
    if e["esperance_R"] is None or e["esperance_R"] < float(vr["esperance_min_R"]): manque.append(f"esperance < +{vr['esperance_min_R']} R ({RP.fmt(e['esperance_R'])})")
    if g is None or g <= 0: manque.append(f"croissance composee a {int(round(100 * float(spec['palier'])))} % non positive")
    row["verdict"] = "PASSE LA VOIE RAPIDE" if not manque else "NE PASSE PAS : " + " ; ".join(manque)
    return row

def decide(fm, temoin, spec):
    e = fm["evaluation_frais_doubles"]["esperance_R"]
    if e is None: return "AUCUN TRADE en evaluation : pas de recommandation"
    if fm["verdict"] != "PASSE LA VOIE RAPIDE":
        if e < 0: return "ESPERANCE NEGATIVE : Furie Momentum abandonnee sans nouveau reglage, M2T reste en reel"
        return "NE PASSE PAS LA VOIE RAPIDE : rien en reel, M2T reste en reel"
    et = temoin["evaluation_frais_doubles"]["esperance_R"]
    if et is not None and e < et: return "PASSE LA VOIE RAPIDE MAIS MOINS BIEN QUE M2T : publiee, M2T reste en reel"
    pf = int(round(100 * float(spec["palier_furie"])))
    tr, s3, g5 = fm["entrainement_frais_doubles"]["esperance_R"], fm["esperance_sans_3_meilleurs_R"], fm["croissance_ln"].get(f"{pf} %")
    if all(x is not None and x > 0 for x in (tr, s3, g5)):
        return f"NIVEAU FURIE : proposee pour remplacer M2T au Lab a {pf} %, apres confirmation ecrite du palier, tests et audit d'Aristote"
    return "NIVEAU LAB : proposee pour remplacer M2T au Lab a 2 %, apres tests et audit d'Aristote"

def markdown(rep):
    out = ["# Lab v6 : Furie Momentum (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
           f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "", "Evaluation, frais doubles, deux positions au plus.", "",
           "| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3, ic, g = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"], r["ic_evaluation_frais_doubles"] or {}, r["croissance_ln"]
        out.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                   f"[{RP.fmt(ic.get('p05'))} ; {RP.fmt(ic.get('p95'))}] | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                   f"{RP.fmt(s3['esperance_R'])} | {e.get('pire_serie_pertes', 'n/d')} | {RP.fmt(e.get('drawdown_max_R'))} | {RP.fmt(g.get('2 %'))} | "
                   f"{RP.fmt(g.get('5 %'))} | {RP.fmt(g.get('10 %'))} | {r['verdict']} |")
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
    runs = {"FM_1h_furie": [t for c, x in sorted(b1.items()) for t in furie(c, x, fund.get(c))],
            "FM_1h_pyramide": [t for c, x in sorted(b1.items()) for t in furie(c, x, fund.get(c), pyramide=True)],
            "M2T_1h_tendance": [t for c, x in sorted(b1.items()) for t in VT.m2_tendance(c, x, fund.get(c))]}
    rows = {n: evaluate(n, runs[n], t0, end, spec) for n in CANDIDATS}
    decision = decide(rows[DECISIF], rows[TEMOIN], spec)
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
