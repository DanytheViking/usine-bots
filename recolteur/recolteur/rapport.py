"""Rapport de T6 a partir du journal (lecture seule) : cascades, trades papier, PF net en frais x1, x2, x3, critere d'abandon.
    python3 -m recolteur.rapport [--journal data/journal.jsonl]"""
import os, sys, json, argparse
from collections import Counter
from . import config as C, journal as J
from .papier import pf_of

def lire(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")] if os.path.exists(path) else []

def resume(evs):
    trades = [e["data"] for e in evs if e["type"] == "sortie"]
    cas = [e["data"] for e in evs if e["type"] == "cascade"]
    out = {"cascades": len(cas), "cascades_completes": sum(1 for c in cas if c["signal_complet"]),
           "refus": dict(Counter(c["refus"] for c in cas if c["refus"]).most_common()), "trades": len(trades),
           "remplissages": sum(1 for e in evs if e["type"] == "remplissage"), "issues": dict(Counter(t["issue"] for t in trades))}
    for m in (1.0, 2.0, C.STRESS):
        pf, rs = pf_of(trades, m)
        out[f"frais_x{int(m)}"] = {"pf": pf, "esperance_R": (sum(rs) / len(rs)) if rs else None, "somme_R": sum(rs)}
    pf3 = out[f"frais_x{int(C.STRESS)}"]["pf"]
    if len(trades) < C.ABANDON_TRADES: out["verdict"] = f"EN COURS : {len(trades)} trades papier sur {C.ABANDON_TRADES} avant le premier jugement"
    elif pf3 is not None and pf3 < C.ABANDON_PF: out["verdict"] = f"ABANDON : PF net {pf3:.2f} (frais x3) sous {C.ABANDON_PF}"
    else: out["verdict"] = f"SE MAINTIENT : PF net {pf3 if pf3 == float('inf') else round(pf3, 2)} (frais x3) au-dessus de {C.ABANDON_PF}"
    if trades:
        moy = lambda k: sum(t[k] for t in trades if t.get(k) is not None) / max(1, sum(1 for t in trades if t.get(k) is not None))
        out["moyennes"] = {k: round(moy(k), 4) for k in ("mfe_R", "mae_R", "duree_ms", "profondeur_obtenue", "latence_ms")}
    univ = [e for e in evs if e["type"] == "univers"]
    out["univers"] = univ[-1]["data"]["univers"] if univ else None
    return out

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--journal", default=os.path.join(C.DATA_DIR, "journal.jsonl"))
    a = ap.parse_args(argv)
    ok, n, msg = J.verify(a.journal)
    print(f"journal : {'intact' if ok else 'ALTERE'}, {n} evenements ({msg})")
    if not ok: return 1
    r = resume(lire(a.journal))
    print(json.dumps(r, indent=1, ensure_ascii=False, default=str))
    return 0

if __name__ == "__main__":
    sys.exit(main())
