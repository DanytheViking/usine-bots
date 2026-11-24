"""Tests hors ligne du Lab v6 (Furie Momentum).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab6.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_furie as VF, strategies as S
from tests.test_usine import bars, no_fund
from tests.test_lab5 import collect

H = 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB6.json")

def serie(c, vol=1e6):
    df = bars(np.asarray(c, float), step=H); df.loc[:, "vol"] = vol / df.close; return df

def hausse_par_paliers(n=900):
    """Tendance haussiere avec des paliers plats puis des poussees : cassures de 24 h dans la tendance."""
    pas = np.where((np.arange(n) // 40) % 2 == 0, 0.004, -0.001)
    return 100 * np.exp(np.cumsum(pas))

def test_entre_sur_cassure_dans_la_tendance():
    t = VF.furie("X", serie(hausse_par_paliers()), no_fund())
    assert t and all(x["side"] == "long" for x in t)
    assert all(x["signal_ts"] >= serie(hausse_par_paliers()).ts.values[S.M2["lente"]] + H for x in t)

def test_rien_sans_cassure():
    c = 100 * np.exp(0.002 * np.arange(400)); c = np.concatenate([c, np.full(400, c[-1])])   # tendance puis plat : plus de cassure
    t = VF.furie("X", serie(c), no_fund())
    df = serie(c)
    assert all(x["signal_ts"] <= df.ts.values[401] + H for x in t)

def test_pas_de_short_en_tendance_haussiere():
    c = hausse_par_paliers(); c[600:610] = c[599] * 0.9                                  # chute breve sans croisement des EMA
    assert all(x["side"] == "long" for x in VF.furie("X", serie(c), no_fund()))

def test_filtre_de_volume():
    assert VF.furie("X", serie(hausse_par_paliers(), vol=5e4), no_fund()) == []

def test_sortie_a_l_ema50():
    t = VF.furie("X", serie(hausse_par_paliers()), no_fund())
    assert any(x["issue"] == "sortie signal" for x in t)

def test_pyramide_un_ajout_gagnant_au_plus():
    df = serie(hausse_par_paliers())
    base = VF.furie("X", df, no_fund()); pyr = VF.furie("X", df, no_fund(), pyramide=True)
    aj = [x for x in pyr if x.get("ajout")]
    assert len([x for x in pyr if not x.get("ajout")]) == len(base) and len(aj) <= len(base) and aj
    for x in aj:
        b = max((y for y in base if y["fill_ts"] < x["fill_ts"]), key=lambda y: y["fill_ts"])
        assert x["entry"] - b["entry"] >= abs(b["entry"] - b["stop"]) * 0.99            # ajout seulement sur une position a +1 R

def test_regle_de_decision():
    spec = json.load(open(SPEC))
    def row(v, e, tr=0.1, s3=0.1, g5=0.01):
        return {"verdict": v, "evaluation_frais_doubles": {"esperance_R": e}, "entrainement_frais_doubles": {"esperance_R": tr},
                "esperance_sans_3_meilleurs_R": s3, "croissance_ln": {"5 %": g5}}
    tem = row("x", 0.2)
    assert VF.decide(row("PASSE LA VOIE RAPIDE", 0.3), tem, spec).startswith("NIVEAU FURIE")
    assert VF.decide(row("PASSE LA VOIE RAPIDE", 0.3, tr=-0.1), tem, spec).startswith("NIVEAU LAB")
    assert VF.decide(row("PASSE LA VOIE RAPIDE", 0.15), tem, spec).startswith("PASSE LA VOIE RAPIDE MAIS")
    assert VF.decide(row("NE PASSE PAS : x", -0.1), tem, spec).startswith("ESPERANCE NEGATIVE")
    assert VF.decide(row("NE PASSE PAS : x", 0.05), tem, spec).startswith("NE PASSE PAS")

def test_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VF.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VF.CANDIDATS) and rep["decision"]
    assert all("5 %" in r["croissance_ln"] for r in rep["candidats"].values())
    assert rep["decision"] in open(os.path.join(out, "verdicts.md")).read()
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VF.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab6-furie-momentum.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.02 and s["palier_furie"] == 0.05 and s["max_positions"] == 2 and s["volume_min_usd"] == 2000000
    assert s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10}
    bad = dict(s, max_positions=3); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VF.load_spec(p); assert False
    except Exception as e: assert "deux positions" in str(e)

def test_source_propre():
    src = open(os.path.join(ROOT, "usine", "verif_furie.py"), encoding="utf-8").read()
    assert "—" not in src and "–" not in src and "import requests" not in src

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try:
            with contextlib.redirect_stdout(io.StringIO()): f()
            print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
