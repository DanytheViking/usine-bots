"""Tests hors ligne du Lab v5 (entree en tendance M2 1 h).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab5.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_m2_tendance as VT, strategies as S, collecte_m2h1 as KM
from tests.test_usine import clk, bars, no_fund
from tests.test_lab4 import FakeAPI, NOW

H = 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB5.json")

def tendance_baissiere(n=600, vol=1e6):
    c = 100 * np.exp(-0.002 * np.arange(n))
    df = bars(c, step=H); df.loc[:, "vol"] = vol / df.close; return df

def test_tendance_entre_sans_croisement():
    df = tendance_baissiere()
    assert VT.m2_croisement("X", df, no_fund()) == []
    t = VT.m2_tendance("X", df, no_fund())
    assert t and t[0]["side"] == "short" and t[0]["signal_ts"] == df.ts.values[S.M2["lente"]] + H

def test_tendance_filtre_de_volume():
    assert VT.m2_tendance("X", tendance_baissiere(vol=5e4), no_fund()) == []           # 24 x 50 000 $ = 1,2 M$ < 2 M$

def test_tendance_reentre_apres_stop():
    c = 100 * np.exp(-0.002 * np.arange(600)); c[300:303] = c[200] * 1.1               # rebond qui touche le stop du short
    df = bars(c, step=H); df.loc[:, "vol"] = 1e6 / df.close
    t = [x for x in VT.m2_tendance("X", df, no_fund()) if x["side"] == "short"]
    stops = [x for x in t if x["issue"] == "STOP"]
    assert stops and any(x["fill_ts"] > stops[0]["exit_ts"] for x in t)

def test_retournement_au_croisement():
    c = np.concatenate([100 * np.exp(-0.002 * np.arange(500)), 100 * np.exp(-1.0) * np.exp(0.004 * np.arange(1, 400))])
    df = bars(c, step=H); df.loc[:, "vol"] = 1e6 / df.close
    t = VT.m2_tendance("X", df, no_fund())
    s = [x for x in t if x["issue"] == "sortie signal"]
    assert s and any(x["side"] == "long" and x["fill_ts"] == s[0]["exit_ts"] for x in t)

def collect(d):
    now, sl = clk(NOW)
    class Fake(FakeAPI):
        def __call__(self, body):
            if body["type"] == "metaAndAssetCtxs": return [{"universe": [{"name": c} for c in KM.MOONSHOT]}, [{} for _ in KM.MOONSHOT]]
            return super().__call__(body)
    with contextlib.redirect_stdout(io.StringIO()): return KM.main(["--out", d], post=Fake(), clock=now, sleep=sl)

def test_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VT.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VT.CANDIDATS) and rep["decision"]
    assert all("2 %" in r["croissance_ln"] for r in rep["candidats"].values())
    assert rep["decision"] in open(os.path.join(out, "verdicts.md")).read()
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VT.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_regle_de_decision():
    row = lambda v, e: {"verdict": v, "evaluation_frais_doubles": {"esperance_R": e}}
    assert VT.decide(row("PASSE LA VOIE RAPIDE", 0.3)).startswith("PASSE")
    assert VT.decide(row("NE PASSE PAS : x", -0.1)).startswith("ESPERANCE NEGATIVE")
    assert VT.decide(row("NE PASSE PAS : x", 0.05)).startswith("ESPERANCE >= 0")

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab5-tendance.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.02 and s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10} and s["volume_min_usd"] == 2000000

SPEC_B = os.path.join(ROOT, "specs", "USINE-SPEC-LAB5B.json")

def test_addendum_plafond_deux_positions():
    s = json.load(open(SPEC_B))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab5b-plafond.md"), "rb").read()).hexdigest()
    assert s["max_positions"] == 2 and {k: v for k, v in s.items() if k not in ("id", "gel_utc", "prereg_sha256", "max_positions", "annonce")} == \
        {k: v for k, v in json.load(open(SPEC)).items() if k not in ("id", "gel_utc", "prereg_sha256", "annonce")}
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VT.run(SPEC_B, d, out)
    with contextlib.redirect_stdout(io.StringIO()): libre = VT.run(SPEC, d, tempfile.mkdtemp())
    for n in VT.CANDIDATS:
        assert rep["candidats"][n]["evaluation_frais_doubles"]["trades"] <= libre["candidats"][n]["evaluation_frais_doubles"]["trades"]
    bad = dict(s, max_positions=3); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VT.load_spec(p); assert False
    except Exception as e: assert "deux positions" in str(e)

def test_source_propre():
    src = open(os.path.join(ROOT, "usine", "verif_m2_tendance.py"), encoding="utf-8").read()
    assert "\u2014" not in src and "\u2013" not in src and "import requests" not in src

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
