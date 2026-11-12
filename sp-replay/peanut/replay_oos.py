"""Extension (b) de SP-20261031-04 — HOLDOUT TEMPOREL FIXE, annoncé à l'avance, et comparaison à coûts égaux. HORS LIGNE.

Cahier des charges (Socrate, transmis le 31/10/2026) intégré :
  - découpe fixée dans un fichier de spécification GELÉ (sha256 imprimé) AVANT lecture des résultats ; le dossier de sortie
    garde un registre : une seconde exécution avec une spécification différente est REFUSÉE (pas de retouche après lecture) ;
  - mêmes coûts pour tous les candidats (constantes de peanut.replay, aucun réglage par stratégie), scénario frais doublés
    systématique ;
  - base « ne rien trader » dans chaque tableau ;
  - comptes par actif, pas seulement l'agrégat ;
  - funding réel inclus (simulation de peanut.replay) ;
  - AUCUNE optimisation : rien n'est ajusté sur la période d'entraînement ; elle sert seulement de contrôle de cohérence.
    python3 -m peanut.replay_oos --data replay-pit-data --spec specs/OOS-SPEC.json --out rapport-oos [--univers pit|actuel]"""
import os, json, argparse, datetime as dt
from collections import defaultdict
import numpy as np
from . import replay as RP

BASELINE = "ne_rien_trader"
REQUIRED = ("id", "gel_utc", "fraction_evaluation", "embargo_min", "scenarios_frais", "criteres", "bootstrap")

class SpecError(Exception): pass

# ============================================================== spécification gelée
def load_spec(path):
    spec = json.load(open(path)); miss = [k for k in REQUIRED if k not in spec]
    if miss: raise SpecError(f"spécification incomplète : {', '.join(miss)}")
    if not 0 < float(spec["fraction_evaluation"]) < 1: raise SpecError("fraction_evaluation hors de ]0, 1[")
    if sorted(spec["scenarios_frais"]) != [1, 2]: raise SpecError("scénarios de frais imposés : [1, 2] (base et doublés)")
    if not {"trades_min", "pf_min", "jours_min_ic"} <= set(spec["criteres"]): raise SpecError("critères incomplets (trades_min, pf_min, jours_min_ic)")
    if float(spec["embargo_min"]) < RP.ENTRY_TTL_MIN + RP.MAX_HOLD_MIN:
        raise SpecError(f"embargo < {RP.ENTRY_TTL_MIN + RP.MAX_HOLD_MIN} min : un trade d'entraînement pourrait chevaucher l'évaluation")
    return spec, RP.sha_file(path)

def check_ledger(out, spec_sha):
    """Registre du dossier de sortie : la première spécification utilisée y est inscrite ; toute autre est refusée."""
    os.makedirs(out, exist_ok=True); p = os.path.join(out, "oos_ledger.json")
    if os.path.exists(p):
        led = json.load(open(p))
        if led["spec_sha256"] != spec_sha:
            raise SpecError(f"refus : ce dossier a déjà été évalué avec la spécification {led['spec_sha256'][:12]}… — "
                            f"une découpe modifiée après lecture est interdite (nouveau dossier ET nouvelle annonce requis)")
        return led
    led = {"spec_sha256": spec_sha, "premiere_execution": "registre créé"}
    json.dump(led, open(p, "w"), indent=1); return led

# ============================================================== découpe
def split(trades, t0, t1, frac_eval, embargo_ms):
    """Entraînement : signaux dans [t0, coupe − embargo[ ; évaluation : signaux dans [coupe, t1]. Embargo : écarté."""
    cut = t0 + (1 - frac_eval) * (t1 - t0)
    is_, oos, emb = [], [], []
    for t in trades:
        s = t["signal_ts"]
        (oos if s >= cut else is_ if s < cut - embargo_ms else emb).append(t)
    return is_, oos, emb, int(cut)

# ============================================================== statistiques
def by_coin(trades):
    g = defaultdict(list)
    for t in trades: g[t["coin"]].append(t)
    return {c: RP.metrics(v) for c, v in sorted(g.items())}

def bootstrap(trades, n, seed):
    """IC de l'espérance en R par rééchantillonnage de JOURS UTC entiers (blocs), graine fixe → déterministe."""
    done = [t for t in trades if "R" in t]
    if not done: return None
    days = defaultdict(list)
    for t in done: days[t["signal_ts"] // 86_400_000].append(t["R"])
    keys = sorted(days); rng = np.random.default_rng(seed); means = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys)); rs = [r for k in pick for r in days[keys[k]]]
        means.append(float(np.mean(rs)))
    return {"p05": round(float(np.percentile(means, 5)), 4), "p50": round(float(np.percentile(means, 50)), 4),
            "p95": round(float(np.percentile(means, 95)), 4), "jours": len(keys), "tirages": n}

def verdict(is_base, oos_base, oos_dbl, ic_dbl, crit):
    if oos_base["trades"] < crit["trades_min"]: return "NON CONCLUANT (moins de %d trades en évaluation)" % crit["trades_min"]
    if not ic_dbl or ic_dbl["jours"] < crit["jours_min_ic"]:
        return "NON CONCLUANT (intervalle de confiance sur moins de %d jours d'évaluation)" % crit["jours_min_ic"]
    ok = [("PF évaluation ≥ %.2f" % crit["pf_min"], (oos_base["profit_factor"] or 0) >= crit["pf_min"]),
          ("espérance évaluation > 0 en frais doublés", (oos_dbl["esperance_R"] or 0) > 0),
          ("IC 5 % de l'espérance (frais doublés) > 0", bool(ic_dbl) and ic_dbl["p05"] > 0),
          ("espérance entraînement > 0 (cohérence)", (is_base["esperance_R"] or 0) > 0)]
    failed = [k for k, v in ok if not v]
    return "AVANTAGE CRÉDIBLE (au-dessus de « ne rien trader »)" if not failed else "PAS D'AVANTAGE : " + " ; ".join(failed)

def baseline_metrics():
    return {"signaux": 0, "remplis": 0, "taux_remplissage": None, "trades": 0, "ouverts_fin": 0, "taux_reussite": None,
            "profit_factor": None, "esperance_R": 0.0, "somme_R": 0.0, "pire_serie_pertes": 0, "drawdown_max_R": 0.0,
            "funding_R": 0.0, "frais_R": 0.0, "issues": {}}

# ============================================================== évaluation de tous les candidats, à coûts égaux
def evaluate(trades_by_strat, windows, spec):
    """trades_by_strat : {stratégie: liste de trades simulés en frais de base} ; windows : {stratégie: (t0, t1)}."""
    frac, emb = float(spec["fraction_evaluation"]), int(float(spec["embargo_min"]) * 60_000)
    bs, crit = spec["bootstrap"], spec["criteres"]; out = {}
    for strat, trades in trades_by_strat.items():
        t0, t1 = windows[strat]
        is_, oos, embargo, cut = split(trades, t0, t1, frac, emb)
        row = {"coupe_ms": cut, "coupe_utc": dt.datetime.fromtimestamp(cut / 1000, dt.timezone.utc).isoformat()[:16] + "Z",
               "signaux_embargo": len(embargo)}
        for seg, xs in (("entrainement", is_), ("evaluation", oos)):
            for m in spec["scenarios_frais"]:
                label = "frais_base" if m == 1 else "frais_doubles"; ys = [RP.with_fees(t, float(m)) for t in xs]
                row[f"{seg}_{label}"] = {"global": RP.metrics(ys), "par_actif": by_coin(ys)}
        row["ic_evaluation_frais_doubles"] = bootstrap([RP.with_fees(t, 2.0) for t in oos], int(bs["tirages"]), int(bs["graine"]))
        row["verdict"] = verdict(row["entrainement_frais_base"]["global"], row["evaluation_frais_base"]["global"],
                                 row["evaluation_frais_doubles"]["global"], row["ic_evaluation_frais_doubles"], crit)
        out[strat] = row
    base = baseline_metrics()
    out[BASELINE] = {"verdict": "référence (0 R, aucun frais, aucun risque)", **{f"{s}_{l}": {"global": base, "par_actif": {}}
                     for s in ("entrainement", "evaluation") for l in ("frais_base", "frais_doubles")}}
    return out

# ============================================================== rapport
COLS = ["trades", "taux_reussite", "profit_factor", "esperance_R", "somme_R", "pire_serie_pertes", "drawdown_max_R", "funding_R", "frais_R"]

def markdown(rep):
    L = [RP.WARNING, "", f"# Holdout temporel fixe — {rep['tache']}", "", "## Empreintes (sha256)"]
    L += [f"- {k} : `{v}`" for k, v in rep["empreintes"].items()]
    s = rep["spec"]
    L += ["", "## Découpe annoncée (spécification gelée)", f"- id : {s['id']} — gelée le {s['gel_utc']}",
          f"- évaluation = dernière fraction {s['fraction_evaluation']} de la fenêtre de chaque unité de temps ; embargo {s['embargo_min']} min",
          f"- coûts identiques pour tous : maker {RP.FEE_MAKER:.5%}, taker {RP.FEE_TAKER:.5%}, glissement stop {RP.STOP_SLIP:.3%}, sorties taker ; scénario frais doublés systématique",
          f"- univers : {rep['univers']}", ""]
    for seg in ("entrainement", "evaluation"):
        for label in ("frais_base", "frais_doubles"):
            L += [f"## {seg} — {label.replace('_', ' ')}", "", "| candidat | " + " | ".join(COLS) + " |", "|" + "---|" * (len(COLS) + 1)]
            for strat, row in rep["resultats"].items():
                g = row[f"{seg}_{label}"]["global"]
                L += [f"| {strat} | " + " | ".join(RP.fmt(g[c]) for c in COLS) + " |"]
            L += [""]
    L += ["## Verdicts (évaluation, critères annoncés)", ""]
    for strat, row in rep["resultats"].items():
        ic = row.get("ic_evaluation_frais_doubles")
        L += [f"- **{strat}** : {row['verdict']}" + (f" — IC espérance frais doublés [{ic['p05']} ; {ic['p95']}] R sur {ic['jours']} jours" if ic else "")
              + (f" — coupe {row['coupe_utc']}, signaux en embargo {row['signaux_embargo']}" if "coupe_utc" in row else "")]
    L += ["", "## Comptes par actif (évaluation, frais doublés)"]
    for strat, row in rep["resultats"].items():
        if strat == BASELINE: continue
        pa = row["evaluation_frais_doubles"]["par_actif"]
        L += ["", f"### {strat}", "", "| actif | trades | taux_reussite | esperance_R | somme_R | funding_R |", "|---|---|---|---|---|---|"]
        L += [f"| {c} | {m['trades']} | {RP.fmt(m['taux_reussite'])} | {RP.fmt(m['esperance_R'])} | {RP.fmt(m['somme_R'])} | {RP.fmt(m['funding_R'])} |" for c, m in pa.items()]
        L += ["| ne_rien_trader | 0 | – | 0.000 | 0.000 | 0.000 |"]
    return "\n".join(L) + "\n"

def run(data_dir, spec_path, out, univers="pit", prereg=None):
    spec, spec_sha = load_spec(spec_path)
    check_ledger(out, spec_sha)                                      # AVANT tout calcul : pas de retouche après lecture
    here = os.path.dirname(os.path.abspath(__file__))
    if univers == "pit":
        from . import replay_pit as P
        _, trades = P.run(data_dir); man, bars, _, _, _ = P.load(data_dir)
    else:
        man, bars, fund = RP.load(data_dir); trades = {s: RP.replay(bars, fund, s) for s in RP.STRATS}
    windows = {}
    for strat, (tf, _) in RP.STRATS.items():
        dfs = [df for (c, t), df in bars.items() if t == tf and len(df)]
        windows[strat] = (min(int(d.ts.iloc[0]) for d in dfs), max(int(d.ts.iloc[-1]) + RP.TF_MS[tf] for d in dfs))
    hashes = {"specification": spec_sha, "manifeste": RP.sha_file(os.path.join(data_dir, "manifest.json")),
              "replay_oos.py": RP.sha_file(os.path.join(here, "replay_oos.py")), "replay.py": RP.sha_file(os.path.join(here, "replay.py")),
              "signals.py": RP.sha_file(os.path.join(here, "signals.py"))}
    if univers == "pit": hashes["replay_pit.py"] = RP.sha_file(os.path.join(here, "replay_pit.py"))
    if prereg: hashes["pre-enregistrement"] = RP.sha_file(prereg)
    rep = {"tache": "SP-20261031-04 extension (b)", "empreintes": hashes, "spec": spec,
           "univers": "point dans le temps (extension a)" if univers == "pit" else "ACTUEL (biais de survivance — comparaison seulement)",
           "resultats": evaluate(trades, windows, spec)}
    json.dump(rep, open(os.path.join(out, "replay_oos.json"), "w"), indent=1, sort_keys=True, default=str)
    open(os.path.join(out, "replay_oos.md"), "w").write(markdown(rep))
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--data", required=True); ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--univers", choices=("pit", "actuel"), default="pit"); ap.add_argument("--prereg")
    a = ap.parse_args(argv)
    print(f"sha256 specification : {RP.sha_file(a.spec)}")
    rep = run(a.data, a.spec, a.out, a.univers, a.prereg)
    for k, v in rep["empreintes"].items(): print(f"sha256 {k} : {v}")
    print(f"rapport : {os.path.join(a.out, 'replay_oos.md')} (sha256 {RP.sha_file(os.path.join(a.out, 'replay_oos.md'))})")

if __name__ == "__main__":
    main()
