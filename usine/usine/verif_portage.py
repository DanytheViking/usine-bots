"""Lab v7 « Portage » pour Smart Peanut, selon PREREG-lab7-portage.
PORTAGE_1h (decisif) : funding moyen de 24 h extreme et prix repasse de l'autre cote de l'EMA 50 1 h : position contre le cote entasse,
stop 3 x ATR(14), sortie quand le funding revient a son taux de base ou apres 120 bougies.
PORTAGE_1h_sans_ema (information) : memes regles sans la condition sur l'EMA 50.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_portage --spec specs/USINE-SPEC-LAB7.json --data /d/portage --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_lab4 as VL, strategies_lab4 as L
from .sim import atr, run_position

H = S.H
PT = {"seuil": 0.00005, "retour": 0.0000125, "fenetre_h": 24, "taux_min": 20, "ema": 50, "stop_atr": 3.0, "duree_max": 120}
CANDIDATS = ("PORTAGE_1h", "PORTAGE_1h_sans_ema")
DECISIF = "PORTAGE_1h"
VOLUME_MIN = 2_000_000.0
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py", "verif_portage.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "decisif", "fraction_evaluation", "stress_frais", "palier",
                        "paliers_publies", "voie_rapide", "bootstrap", "volume_min_usd", "max_positions") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF: raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10: raise V.SpecError("voie rapide du Lab : 40 trades et +0,10 R")
    if float(spec["palier"]) > 0.20: raise V.SpecError("borne du Lab : 20 % par trade")
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    if not 1 <= int(spec["max_positions"]) <= 2: raise V.SpecError("plafond du Lab : deux positions au plus")
    return spec, RP.sha_file(path)

def funding_24h(df, fund):
    """Moyenne des taux de funding horaires de ]cloture - 24 h, cloture] pour chaque bougie ; nan sous PT["taux_min"] taux."""
    out = np.full(len(df), np.nan)
    if fund is None or not len(fund[0]): return out
    times, rates = fund; cs = np.concatenate([[0.0], np.cumsum(rates)])
    fin = df.ts.values + H
    lo = np.searchsorted(times, fin - PT["fenetre_h"] * H, side="right"); hi = np.searchsorted(times, fin, side="right")
    n = hi - lo; ok = n >= PT["taux_min"]
    out[ok] = (cs[hi[ok]] - cs[lo[ok]]) / n[ok]
    return out

def portage(coin, df, fund, avec_ema=True):
    strat = "PORTAGE_1h" if avec_ema else "PORTAGE_1h_sans_ema"
    a = atr(df).values; liq = L.liquidite(df, H); cl = df.close.values
    em = df.close.ewm(span=PT["ema"], adjust=False).mean().values
    f24 = funding_24h(df, fund)
    def sig(i):
        if np.isnan(a[i]) or np.isnan(liq[i]) or liq[i] < VOLUME_MIN or np.isnan(f24[i]): return None
        if f24[i] >= PT["seuil"] and (cl[i] < em[i] or not avec_ema): return ("short", PT["stop_atr"] * a[i])
        if f24[i] <= -PT["seuil"] and (cl[i] > em[i] or not avec_ema): return ("long", PT["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        sortie = (lambda k: f24[k] < PT["retour"]) if side == "short" else (lambda k: f24[k] > -PT["retour"])
        tr, k = run_position(df, i, side, dist, coin, strat, H, fund, max_bars=PT["duree_max"], exit_fn=sortie)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return S._flat_loop(df, PT["ema"], sig, opn)

def evaluate(name, trades, t0, t1, spec):
    row = VL.evaluate(name, trades, t0, t1, spec)
    vr = spec["voie_rapide"]; e = row["evaluation_frais_doubles"]; g = row["croissance_palier"]
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (t1 - t0))
    fr = [t["funding_R"] for t in L.capacite(trades, int(spec["max_positions"])) if t["signal_ts"] >= cut]
    row["funding_R_moyen"] = round(float(np.mean(fr)), 4) if fr else None
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
        if esp < 0: return "ESPERANCE NEGATIVE : Portage abandonne sans nouveau reglage, regle d'arret de l'addendum v3 (M2 seul)"
        return "NE PASSE PAS LA VOIE RAPIDE : rien en reel"
    tr, s3 = row["entrainement_frais_doubles"]["esperance_R"], row["esperance_sans_3_meilleurs_R"]
    if all(x is not None and x > 0 for x in (tr, s3)):
        return "NIVEAU REEL : propose a Richard pour le Lab a 2 %, apres sa confirmation ecrite, les tests d'execution et l'audit d'Aristote"
    return "NIVEAU PAPIER : deux semaines en observation (aucun ordre) avant toute proposition de reel"

def markdown(rep):
    out = ["# Lab v7 : Portage (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
           f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "", "Evaluation, frais doubles, deux positions au plus.", "",
           "| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | funding moyen (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3, ic, g = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"], r["ic_evaluation_frais_doubles"] or {}, r["croissance_ln"]
        out.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                   f"[{RP.fmt(ic.get('p05'))} ; {RP.fmt(ic.get('p95'))}] | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                   f"{RP.fmt(s3['esperance_R'])} | {RP.fmt(r['funding_R_moyen'])} | {e.get('pire_serie_pertes', 'n/d')} | {RP.fmt(e.get('drawdown_max_R'))} | "
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
    man = V._verify(data); end = int(man["end_ms"]); t0 = int(man["debut_1h_ms"])
    b1 = {c: V._bars(os.path.join(data, "candles", f"{c}_1h.json"), end, H) for c in man["coins"]}
    b1 = {c: x for c, x in b1.items() if len(x)}
    fund = {c: V._fund(os.path.join(data, "funding", f"{c}.json")) for c in b1}
    runs = {"PORTAGE_1h": [t for c, x in sorted(b1.items()) for t in portage(c, x, fund.get(c))],
            "PORTAGE_1h_sans_ema": [t for c, x in sorted(b1.items()) for t in portage(c, x, fund.get(c), avec_ema=False)]}
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
