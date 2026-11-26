"""Lab v9 « Duel » pour Smart Peanut, selon PREREG-lab9-duel.
DUEL_4h (decisif) : force relative d'un actif contre BTC. Rapport q = prix de l'actif / prix de BTC en 4 h ; croisement EMA 50 / 200 du rapport ;
deux jambes au meme montant (achat de l'actif et vente de BTC, ou l'inverse) ; stop a 6 fois la variation absolue moyenne du rapport
(equivalent de 3 ATR), lu a la cloture ; sortie au croisement inverse.
M2_4h_temoin (information) : M2 inchange sur les prix des memes actifs.
Hors ligne, sur donnees figees ; sha256 de la specification imprime en PREMIER ; registre anti-retouche.
    python3 -m usine.verif_duel --spec specs/USINE-SPEC-LAB9.json --data /d/duel --out /out [--attendre 14400]"""
import os, sys, json, argparse
from collections import defaultdict
import numpy as np
import pandas as pd
from peanut import replay as RP, replay_oos as OOS
from . import strategies as S, verdicts as V, verdicts_lab4 as VL, strategies_lab4 as L
from .sim import FEE_TAKER, STOP_SLIP, funding_paid

H4, D = S.H4, L.D
DU = {"rapide": 50, "lente": 200, "vol": 14, "stop_x": 6.0}
CANDIDATS = ("DUEL_4h", "M2_4h_temoin")
DECISIF = "DUEL_4h"
REFERENCE = "BTC"
VOLUME_MIN = 2_000_000.0
FICHIERS = ("sim.py", "strategies.py", "strategies_lab4.py", "verdicts.py", "verdicts_lab4.py", "verif_duel.py")

def load_spec(path):
    spec = json.load(open(path))
    miss = [k for k in ("id", "gel_utc", "prereg_sha256", "candidats", "decisif", "reference", "fraction_evaluation", "stress_frais", "palier",
                        "paliers_publies", "voie_rapide", "bootstrap", "volume_min_usd", "max_positions") if k not in spec]
    if miss: raise V.SpecError("specification incomplete : " + ", ".join(miss))
    if sorted(spec["candidats"]) != sorted(CANDIDATS) or spec["decisif"] != DECISIF: raise V.SpecError("candidats attendus : " + ", ".join(CANDIDATS))
    if spec["reference"] != REFERENCE: raise V.SpecError("reference du Duel : BTC")
    vr = spec["voie_rapide"]
    if int(vr.get("trades_min", 0)) < 40 or float(vr.get("esperance_min_R", 0)) < 0.10: raise V.SpecError("voie rapide du Lab : 40 trades et +0,10 R")
    if float(spec["palier"]) > 0.20: raise V.SpecError("borne du Lab : 20 % par trade")
    if float(spec["volume_min_usd"]) != VOLUME_MIN: raise V.SpecError("filtre de volume du bot reel : 2 M$")
    if not 1 <= int(spec["max_positions"]) <= 2: raise V.SpecError("plafond du Lab : deux positions au plus")
    return spec, RP.sha_file(path)

def paire(dx, db):
    """Bougies communes a l'actif et a la reference, avec le rapport des clotures (q) et des ouvertures (qo)."""
    m = pd.merge(dx, db, on="ts", suffixes=("_x", "_b")).sort_values("ts").reset_index(drop=True)
    m["q"] = m.close_x / m.close_b; m["qo"] = m.open_x / m.open_b
    return m

def duel(coin, dx, db, fx, fb, strat="DUEL_4h"):
    """Trades du Duel pour un actif. Le resultat est en R : R = montant d'une jambe x (distance du stop / q d'entree)."""
    p = DU; m = paire(dx, db); n = len(m)
    if n <= p["lente"] + 1: return []
    ts, q, qo = m.ts.values, m.q.values, m.qo.values
    ox, cx, ob, cb = m.open_x.values, m.close_x.values, m.open_b.values, m.close_b.values
    f = m.q.ewm(span=p["rapide"], adjust=False).mean().values
    s = m.q.ewm(span=p["lente"], adjust=False).mean().values
    a = m.q.diff().abs().rolling(p["vol"], min_periods=p["vol"]).mean().values
    liq = (m.vol_x * m.close_x).rolling(D // H4, min_periods=D // H4).sum().values
    up = lambda i: f[i] > s[i] and f[i - 1] <= s[i - 1]
    dn = lambda i: f[i] < s[i] and f[i - 1] >= s[i - 1]
    def sig(i):
        if np.isnan(a[i]) or np.isnan(liq[i]) or liq[i] < VOLUME_MIN: return None
        if up(i): return ("long", p["stop_x"] * a[i])
        if dn(i): return ("short", p["stop_x"] * a[i])
        return None
    def fin(base, sgn, j, e, d, kx, issue):
        """Sortie des deux jambes a l'ouverture de kx."""
        px, pb = float(ox[kx]), float(ob[kx])
        if issue == "STOP": px, pb = px * (1 - sgn * STOP_SLIP), pb * (1 + sgn * STOP_SLIP)
        rx, rb = px / ox[j] - 1, pb / ob[j] - 1
        gross = sgn * (rx - rb)
        fees = FEE_TAKER * (2 + px / ox[j] + pb / ob[j])
        fs = funding_paid(fx, ts[j], ts[kx], sgn, ts, cx) / ox[j] + funding_paid(fb, ts[j], ts[kx], -sgn, ts, cb) / ob[j]
        return {**base, "issue": issue, "fill_ts": int(ts[j]), "exit_ts": int(ts[kx]), "entry": e, "exit": px / pb,
                "R": float((gross - fees - fs) / d), "gross_R": float(gross / d), "fees_R": float(fees / d), "funding_R": float(-fs / d)}
    def opn(i, side, dist):
        j = i + 1
        if j >= n: return None, i, False
        sgn = 1 if side == "long" else -1
        e = float(qo[j]); st = e - sgn * dist
        base = {"coin": coin, "strat": strat, "side": side, "signal_ts": int(ts[i]) + H4, "stop": float(st), "tp": None}
        if not np.isfinite(dist) or dist <= 0 or dist >= e: return {**base, "issue": "annule (stop invalide)"}, i, False
        d = dist / e; inverse = dn if side == "long" else up
        for k in range(j, n):
            stoppe = (q[k] <= st) if sgn > 0 else (q[k] >= st)
            if stoppe or inverse(k):
                if k + 1 >= n: break
                return fin(base, sgn, j, e, d, k + 1, "STOP" if stoppe else "sortie signal"), k, not stoppe
        return {**base, "issue": "ouvert en fin de données", "fill_ts": int(ts[j]), "entry": e}, n - 1, False
    return S._flat_loop(m, p["lente"], sig, opn)

def correlation_journaliere(ta, tb, cut):
    """Correlation des sommes journalieres de R (jour UTC de sortie, evaluation) entre deux series de trades ; None sous 20 jours actifs."""
    def par_jour(ts_):
        g = defaultdict(float)
        for t in ts_:
            if "R" in t and t["signal_ts"] >= cut: g[t["exit_ts"] // D] += t["R"]
        return g
    ga, gb = par_jour(ta), par_jour(tb); jours = sorted(set(ga) | set(gb))
    if len(jours) < 20: return None
    x, y = np.array([ga.get(j, 0.0) for j in jours]), np.array([gb.get(j, 0.0) for j in jours])
    if x.std() == 0 or y.std() == 0: return None
    return round(float(np.corrcoef(x, y)[0, 1]), 3)

def evaluate(name, trades, t0, t1, spec):
    row = VL.evaluate(name, trades, t0, t1, spec)
    vr = spec["voie_rapide"]; e = row["evaluation_frais_doubles"]; g = row["croissance_palier"]
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (t1 - t0))
    ev = [RP.with_fees(t, 2.0) for t in L.capacite(trades, int(spec["max_positions"])) if t["signal_ts"] >= cut]
    row["funding_R_moyen"] = round(float(np.mean([t["funding_R"] for t in ev])), 4) if ev else None
    row["pire_trade_R"] = round(float(min(t["R"] for t in ev)), 4) if ev else None
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
        if esp < 0: return "ESPERANCE NEGATIVE : Duel abandonne sans nouveau reglage"
        return "NE PASSE PAS LA VOIE RAPIDE : rien en reel"
    tr, s3 = row["entrainement_frais_doubles"]["esperance_R"], row["esperance_sans_3_meilleurs_R"]
    if all(x is not None and x > 0 for x in (tr, s3)):
        return ("NIVEAU REEL : propose a Richard pour le Lab a 2 %, apres le code d'execution a deux jambes, sa confirmation ecrite "
                "et l'audit d'Aristote ; observation sans ordre en attendant")
    return "NIVEAU PAPIER : deux semaines en observation (aucun ordre) avant toute proposition de reel"

def markdown(rep):
    out = ["# Lab v9 : Duel (Smart Peanut)", "", f"Specification {rep['specification']} (sha256 {rep['empreintes']['specification']}), "
           f"manifeste {rep['empreintes']['manifeste'][:12]}.", "", f"**{rep['decision']}**", "", "Evaluation, frais doubles, deux positions au plus.", "",
           "| candidat | trades eval. | trades / jour | esperance (R) | PF | IC 5-95 % | entrainement (R) | sans 3 meilleurs (R) | frais x3 (R) | funding moyen (R) | pire trade (R) | pire serie | baisse max (R) | ln a 2 % | ln a 5 % | ln a 10 % | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, r in rep["candidats"].items():
        e, t, s3, ic, g = r["evaluation_frais_doubles"], r["entrainement_frais_doubles"], r["evaluation_frais_stress"], r["ic_evaluation_frais_doubles"] or {}, r["croissance_ln"]
        out.append(f"| {n} | {e['trades']} | {r['trades_par_jour']} | {RP.fmt(e['esperance_R'])} | {RP.fmt(e['profit_factor'])} | "
                   f"[{RP.fmt(ic.get('p05'))} ; {RP.fmt(ic.get('p95'))}] | {RP.fmt(t['esperance_R'])} | {RP.fmt(r['esperance_sans_3_meilleurs_R'])} | "
                   f"{RP.fmt(s3['esperance_R'])} | {RP.fmt(r['funding_R_moyen'])} | {RP.fmt(r['pire_trade_R'])} | {e.get('pire_serie_pertes', 'n/d')} | "
                   f"{RP.fmt(e.get('drawdown_max_R'))} | {RP.fmt(g.get('2 %'))} | {RP.fmt(g.get('5 %'))} | {RP.fmt(g.get('10 %'))} | {r['verdict']} |")
    out += ["", f"Correlation journaliere des resultats entre le Duel et M2 (evaluation) : {RP.fmt(rep['notes']['correlation_duel_m2'])}",
            "", f"Actifs du jeu : {', '.join(rep['notes']['coins'])}", ""]
    return "\n".join(out)

def run(spec_path, data, out):
    spec, spec_sha = load_spec(spec_path)
    print(f"sha256 specification : {spec_sha}", flush=True)
    OOS.check_ledger(out, spec_sha)
    here = os.path.dirname(os.path.abspath(__file__))
    hashes = {"specification": spec_sha, **{f: RP.sha_file(os.path.join(here, f)) for f in FICHIERS},
              "manifeste": RP.sha_file(os.path.join(data, "manifest.json"))}
    man = V._verify(data); end = int(man["end_ms"]); t0 = int(man["debut_4h_ms"])
    b4 = {c: V._bars(os.path.join(data, "candles", f"{c}_4h.json"), end, H4) for c in man["coins"]}
    b4 = {c: x for c, x in b4.items() if len(x)}
    if REFERENCE not in b4: raise V.SpecError(f"bougies de {REFERENCE} absentes du jeu")
    fund = {c: V._fund(os.path.join(data, "funding", f"{c}.json")) for c in b4}
    runs = {"DUEL_4h": [t for c, x in sorted(b4.items()) if c != REFERENCE for t in duel(c, x, b4[REFERENCE], fund.get(c), fund.get(REFERENCE))],
            "M2_4h_temoin": [t for c, x in sorted(b4.items()) for t in S.m2_croisement_ema(c, x, fund.get(c))]}
    rows = {n: evaluate(n, runs[n], t0, end, spec) for n in CANDIDATS}
    decision = decide(rows[DECISIF], spec)
    cut = int(t0 + (1 - float(spec["fraction_evaluation"])) * (end - t0)); mp = int(spec["max_positions"])
    corr = correlation_journaliere(L.capacite(runs["DUEL_4h"], mp), L.capacite(runs["M2_4h_temoin"], mp), cut)
    rep = {"specification": spec["id"], "empreintes": hashes, "candidats": rows, "decision": decision,
           "notes": {"coins": sorted(b4), "reference": REFERENCE, "correlation_duel_m2": corr}}
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
