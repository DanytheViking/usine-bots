"""Verdicts du Lab v4 « furie » selon PREREG-lab4-furie et la voie rapide du Lab (PRIORITES.md, section LAB).
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
--attendre N : attend jusqu'a N secondes que le manifeste du jeu existe (collecte lancee par un travail voisin).
    python3 -m usine.verdicts_lab4 --spec specs/USINE-SPEC-LAB4.json --data /d/lab4 --out /out [--attendre 14400]"""
import os, sys, json, time, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import verdicts as V, strategies_lab4 as L

M15, H, D = L.M15, L.H, L.D
CANDIDATS = ("L1_compression_1h", "L1_compression_15m", "L1b_asie_us_15m", "L2_top_movers_1h")
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "fraction_evaluation", "stress_frais", "max_positions",
                        "palier", "paliers_publies", "voie_rapide", "bootstrap") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS): raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10:
        raise V.SpecError("voie rapide du Lab : au moins 40 trades et +0,10 R")
    if float(spec["palier"]) > 0.20 or int(spec["max_positions"]) > 2: raise V.SpecError("bornes du Lab : 20 % et deux positions au plus")
    return spec, RP.sha_file(path)

def load(d):
    man = V._verify(d); end = int(man["end_ms"])
    b1 = {c: V._bars(os.path.join(d, "candles", f"{c}_1h.json"), end, H) for c in man["coins"]}
    b15 = {c: V._bars(os.path.join(d, "candles", f"{c}_15m.json"), end, M15) for c in man["coins"]}
    fund = {c: V._fund(os.path.join(d, "funding", f"{c}.json")) for c in man["coins"]}
    return man, {c: x for c, x in b1.items() if len(x)}, {c: x for c, x in b15.items() if len(x)}, fund

def run_all(man, b1, b15, fund):
    t1, t15, end = int(man["debut_1h_ms"]), int(man["debut_15m_ms"]), int(man["end_ms"])
    return {
        "L1_compression_1h": ([t for c, x in sorted(b1.items()) for t in L.l1_compression(c, x, fund.get(c), H, "L1_compression_1h")], t1, end),
        "L1_compression_15m": ([t for c, x in sorted(b15.items()) for t in L.l1_compression(c, x, fund.get(c), M15, "L1_compression_15m")], t15, end),
        "L1b_asie_us_15m": ([t for c, x in sorted(b15.items()) for t in L.l1b_asie_us(c, x, fund.get(c))], t15, end),
        "L2_top_movers_1h": ([t for c, x in sorted(b1.items()) for t in L.l2_top_movers(c, x, fund.get(c))], t1, end),
    }

def _rs(ts): return [t["R"] for t in ts if "R" in t]

def evaluate(name, trades, t0, t1, spec):
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (t1 - t0))
    plaf = L.capacite(trades, int(spec["max_positions"]))
    tr, ev, cheval = V.split(plaf, cut)
    _, ev_libre, _ = V.split([t for t in trades if "R" in t], cut)
    x2 = lambda xs: [RP.with_fees(t, 2.0) for t in xs]
    ev2, tr2 = x2(ev), x2(tr)
    m_ev, m_tr = RP.metrics(ev2), RP.metrics(tr2)
    rs = sorted(_rs(ev2)); jours = max((t1 - cut) / D, 1e-9)
    f = float(spec["palier"]); vr = spec["voie_rapide"]
    g = {f"{int(round(100 * p))} %": L.croissance(rs, p) for p in spec["paliers_publies"]}
    sans3 = rs[:-3] if len(rs) > 3 else []
    bs = spec["bootstrap"]
    row = {"coupe_utc": V.dt.datetime.fromtimestamp(cut / 1000, V.dt.timezone.utc).isoformat()[:16] + "Z", "trades_a_cheval_exclus": len(cheval),
           "evaluation_frais_doubles": m_ev, "entrainement_frais_doubles": m_tr,
           "evaluation_frais_base": RP.metrics(ev), "evaluation_frais_stress": RP.metrics([RP.with_fees(t, float(spec["stress_frais"])) for t in ev]),
           "evaluation_sans_plafond_frais_doubles": RP.metrics(x2(ev_libre)),
           "croissance_ln": g, "esperance_sans_3_meilleurs_R": round(float(np.mean(sans3)), 4) if sans3 else None,
           "trades_par_jour": round(len(rs) / jours, 2), "jours_evaluation": round(jours, 1),
           "ic_evaluation_frais_doubles": OOS.bootstrap(ev2, int(bs["tirages"]), int(bs["graine"])),
           "par_actif": OOS.by_coin(ev2)}
    e, n, gf, et = m_ev["esperance_R"], m_ev["trades"], L.croissance(rs, f), m_tr["esperance_R"]
    manque = []
    if n < int(vr["trades_min"]): manque.append(f"moins de {vr['trades_min']} trades ({n})")
    if e is None or e < float(vr["esperance_min_R"]): manque.append(f"esperance < +{vr['esperance_min_R']} R ({RP.fmt(e)})")
    if gf is None or gf <= 0: manque.append(f"croissance composee a {int(round(100 * f))} % non positive")
    if et is None or et <= 0: manque.append(f"entrainement non positif ({RP.fmt(et)})")
    row["croissance_palier"] = gf
    row["verdict"] = "PASSE LA VOIE RAPIDE" if not manque else "NE PASSE PAS : " + " ; ".join(manque)
    if not manque:
        weak = []
        for c in sorted({t["coin"] for t in ev2}):
            r = [t["R"] for t in ev2 if t["coin"] != c]
            if not r or np.mean(r) < float(vr["esperance_min_R"]): weak.append(c)
        row["dependant_de"] = weak
    return row

def decide(rows):
    ok = [(r["croissance_palier"], n) for n, r in rows.items() if r["verdict"] == "PASSE LA VOIE RAPIDE"]
    if not ok: return None, "AUCUN CANDIDAT NE PASSE : rien ne va en reel sur la foi de ce test (Richard reste libre d'une exception)"
    best = max(ok)[1]
    return best, f"{best} PASSE : propose pour le reel au Lab au palier en cours, apres les tests P0b et l'audit d'Aristote"

def attendre(data, secondes, sleep=time.sleep, clock=time.time):
    fin = clock() + secondes
    while not os.path.exists(os.path.join(data, "manifest.json")):
        if clock() >= fin: raise V.SpecError(f"manifeste absent apres {secondes} s : collecte non terminee")
        sleep(60)
    sleep(60)                                                                   # le manifeste vient d'etre ecrit : laisser finir l'ecriture

def markdown(rep):
    L_ = [f"# Verdicts du Lab v4 « furie » (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
          f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "",
          "Serie decisive : evaluation, frais doubles, deux positions au plus.", "",
          "| candidat | trades eval. | trades / jour | esperance (R) | PF | croissance ln a 10 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | pire serie | verdict |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3 = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"]
        L_.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                  f"{RP.fmt(r['croissance_palier'])} | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                  f"{RP.fmt(s3['esperance_R'])} | {e.get('pire_serie_pertes', '–')} | {r['verdict']} |")
    L_ += ["", f"Actifs du jeu : {', '.join(rep['notes']['coins'])}", ""]
    return "\n".join(L_)

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man, b1, b15, fund = load(data)
    runs = run_all(man, b1, b15, fund)
    rows = {n: evaluate(n, *runs[n], spec) for n in CANDIDATS}
    best, decision = decide(rows)
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "retenu": best, "decision": decision, "notes": {"coins": man["coins"]}}
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
        if a.attendre: attendre(a.data, a.attendre)
        run(a.spec, a.data, a.out)
    except (V.SpecError, OOS.SpecError, RP.Tampered) as e: sys.exit(f"refus : {e}")

if __name__ == "__main__":
    main()
