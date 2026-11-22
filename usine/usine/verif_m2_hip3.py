"""Test de M2 sur les marches HIP-3 (or, argent, petrole, indices, actions), selon PREREG-hip3-m2.
M2_1h_hip3 (decisif) : M2 inchange sur bougies 1 h. M2_4h_reconstruit (information) : M2 4 h sur les memes bougies agregees.
Frais de base HIP-3 = 2 fois le bareme validateur (hypothese prudente figee) : le scenario frais doubles vaut 4 fois le bareme validateur.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_m2_hip3 --spec specs/USINE-SPEC-HIP3.json --data /d/hip3 --out /out [--attendre 14400]"""
import os, sys, json, argparse
import numpy as np
from peanut import replay as RP, replay_oos as OOS
from . import verdicts as V, verdicts_v3 as V3, verdicts_lab4 as VL, verif_m2_1h as VM
from .collecte_hip3 import fichier

H, H4, D = VM.H, VM.H4, VM.D
CANDIDATS = ("M2_1h_hip3", "M2_4h_reconstruit")
DECISIF = "M2_1h_hip3"
FACTEUR_HIP3 = 2.0
FICHIERS = ("sim.py", "strategies.py", "verdicts.py", "verdicts_v3.py", "verif_m2_1h.py", "collecte_hip3.py", "verif_m2_hip3.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in V.REQUIRED + ("stress_frais", "decisif", "facteur_frais_hip3") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise V.SpecError("scenarios de frais imposes : [1, 2]")
    if float(spec["criteres"].get("pf_min", 0)) < 1.35: raise V.SpecError("PF minimal : 1,35")
    if int(spec["criteres"].get("trades_min", 0)) < 30: raise V.SpecError("au moins 30 trades")
    if float(spec["facteur_frais_hip3"]) != FACTEUR_HIP3: raise V.SpecError("facteur de frais HIP-3 fige a 2")
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF: raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    return spec, RP.sha_file(path)

def load(d):
    man = V._verify(d); end = int(man["end_ms"])
    b1 = {c: V._bars(os.path.join(d, "candles", f"{fichier(c)}_1h.json"), end, H) for c in man["coins"]}
    fund = {c: V._fund(os.path.join(d, "funding", f"{fichier(c)}.json")) for c in man["coins"]}
    btc = V._bars(os.path.join(d, "candles", "BTC_1h.json"), end, H)
    return man, {c: x for c, x in b1.items() if len(x)}, fund, btc, V._fund(os.path.join(d, "funding", "BTC.json"))

def hip3(trades):
    """Frais de base HIP-3 : frais du bareme validateur multiplies par le facteur fige."""
    return [RP.with_fees(t, FACTEUR_HIP3) for t in trades]

def run_all(b1, fund):
    b4 = {c: VM.vers_4h(x) for c, x in b1.items()}
    return {"M2_1h_hip3": (hip3([t for c, x in sorted(b1.items()) for t in VM.m2(c, x, fund.get(c), H, "M2_1h_hip3")]), b1, H),
            "M2_4h_reconstruit": (hip3([t for c, x in sorted(b4.items()) for t in VM.m2(c, x, fund.get(c), H4, "M2_4h_reconstruit")]), b4, H4)}

def journalier(trades, cut):
    """Somme des R par jour UTC de sortie, en evaluation."""
    out = {}
    for t in trades:
        if "R" in t and t["signal_ts"] >= cut: k = t["exit_ts"] // D; out[k] = out.get(k, 0.0) + t["R"]
    return out

def correlation(a, b):
    """Correlation des R journaliers (jours ou l'un des deux a trade, zero sinon). None si moins de 10 jours."""
    jours = sorted(set(a) | set(b))
    if len(jours) < 10: return None
    x, y = np.array([a.get(j, 0.0) for j in jours]), np.array([b.get(j, 0.0) for j in jours])
    if x.std() == 0 or y.std() == 0: return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)

def decide(row):
    """Regle de decision pre-enregistree, sur M2_1h_hip3 (evaluation, frais doubles)."""
    ev = row["evaluation_frais_doubles"]["global"]; e2 = ev["esperance_R"]
    if e2 is None or ev["trades"] == 0: return "AUCUN TRADE en evaluation : pas de recommandation"
    if row["verdict"].startswith("AVANTAGE"):
        return "AVANTAGE : adapter le bot aux marches HIP-3, papier deux semaines, puis proposition chiffree a Richard (rien en reel sans son accord ecrit)"
    if e2 < 0: return "ESPERANCE NEGATIVE : M2 sur HIP-3 abandonne, sans nouveau reglage"
    return "ESPERANCE >= 0 SANS AVANTAGE DEMONTRE : rien en reel sur la foi de ce test (Richard reste libre d'une exception ecrite)"

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man, b1, fund, btc, fbtc = load(data); end = int(man["end_ms"])
    t0 = int(man["debut_1h_ms"])
    runs = run_all(b1, fund)
    rows = {}
    for n in CANDIDATS:
        trades, bars, tf = runs[n]
        r = V3.evaluate(n, trades, t0, end, bars, tf, spec)
        r["trades_par_mois"] = VM.frequence(r, t0, end)
        rows[n] = r
    cut = rows[DECISIF]["coupe_ms"]
    btc_trades = VM.m2("BTC", btc, fbtc, H, "M2_1h_btc") if len(btc) else []
    corr = correlation(journalier(runs[DECISIF][0], cut), journalier(btc_trades, cut))
    decision = decide(rows[DECISIF])
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "decision": decision,
           "notes": {"coins": man["coins"], "classement": man.get("classement", []), "frais_publies": man.get("frais_publies", []),
                     "correlation_journaliere_avec_m2_btc": corr, "facteur_frais_hip3": FACTEUR_HIP3}}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "verdicts.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(out, "verdicts.md"), "w").write(markdown(rep))
    print(decision)
    print(f"rapport : {os.path.join(out, 'verdicts.md')} (sha256 {RP.sha_file(os.path.join(out, 'verdicts.md'))})")
    return rep

def markdown(rep):
    md = VM.markdown(rep).replace("# Test de M2 en 1 h sur les actifs de Moonshot", "# Test de M2 sur les marches HIP-3")
    md = md.replace("M2_1h_moonshot decide", "M2_1h_hip3 decide").replace("Actifs du jeu", "Marches du jeu")
    L = ["", f"Frais de base HIP-3 = {rep['notes']['facteur_frais_hip3']:g} x bareme validateur ; frais doubles = 4 x.",
         f"Correlation journaliere avec M2 1 h sur BTC (evaluation) : {rep['notes']['correlation_journaliere_avec_m2_btc']}", "",
         "| marche | volume 24 h | bougies 1 h |", "|---|---|---|"]
    for x in rep["notes"]["classement"]:
        L.append(f"| {x['marche']} | {round(x['volume_24h'])} | {x['bougies_1h'] if x['bougies_1h'] is not None else '–'} |")
    return md + "\n".join(L) + "\n"

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
