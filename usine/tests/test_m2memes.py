"""Tests hors ligne de la verification M2 sur les memecoins.
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_m2memes.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_m2_memes as VM, strategies as S, verdicts as V
from tests.test_usine import bars, no_fund
from tests.test_v3 import collect

H4 = 4 * 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-M2MEMES.json")

def wave(n=1500, vol=1e6):
    c = 100 * np.exp(0.4 * np.sin(np.arange(n) / 60) + 0.0001 * np.arange(n))
    return bars(c, step=H4, vols=np.full(n, vol))

def strip(ts): return [{k: v for k, v in t.items() if k != "strat"} for t in ts]

def test_sans_filtre_identique_au_testeur():
    df = wave(); a = VM._replay("X", df, no_fund(), lambda i: True); b = S.m2_croisement_ema("X", df, no_fund())
    assert len(a) > 5 and strip(a) == strip(b)

def test_filtre_volume_24h():
    df = wave(vol=1e6)
    df.loc[:, "vol"] = 1e5 / df.close                                                         # 6 x 100 000 $ = 600 000 $ < 2 M$
    assert VM.m2_filtre("X", df, no_fund()) == []
    df.loc[:, "vol"] = 4e5 / df.close                                                         # 6 x 400 000 $ = 2,4 M$
    assert strip(VM.m2_filtre("X", df, no_fund())) == strip(S.m2_croisement_ema("X", df, no_fund()))
    v = VM.vol24(df); assert np.isnan(v[4]) and abs(v[5] - 2.4e6) < 1e-3

def test_filtre_bloque_une_entree_precise():
    df = wave(); df.loc[:, "vol"] = 4e5 / df.close
    ref = S.m2_croisement_ema("X", df, no_fund()); first = ref[0]
    i = int(np.searchsorted(df.ts.values, first["signal_ts"] - H4))
    df.loc[i - 5:i, "vol"] = 1.0                                                              # volume nul sur les 24 h du premier signal
    got = VM.m2_filtre("X", df, no_fund())
    assert got and got[0]["signal_ts"] != first["signal_ts"]

def test_regle_de_decision():
    row = lambda e, n, v: {"evaluation_frais_doubles": {"global": {"esperance_R": e, "trades": n}}, "verdict": v}
    assert VM.decide(row(-0.01, 50, "PAS D'AVANTAGE")).startswith("ESPERANCE NEGATIVE")
    assert VM.decide(row(0.0, 50, "PAS D'AVANTAGE")).startswith("ESPERANCE >= 0")
    assert VM.decide(row(0.3, 50, "AVANTAGE")).startswith("AVANTAGE DEMONTRE")
    assert VM.decide(row(-0.5, 50, "AVANTAGE")).startswith("ESPERANCE NEGATIVE")
    assert VM.decide(row(None, 0, "NON CONCLUANT")).startswith("AUCUN TRADE")

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-verif-M2-memecoins.md"), "rb").read()).hexdigest()
    assert s["criteres"] == {"trades_min": 30, "pf_min": 1.2, "jours_min_ic": 7} and s["volume_min_usd"] == 2000000
    for bad in ({**s, "volume_min_usd": 1e6}, {**s, "criteres": {**s["criteres"], "pf_min": 1.1}}, {**s, "candidats": ["M2_memes_sans_filtre"]}):
        p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
        try: VM.load_spec(p); assert False
        except V.SpecError: pass

def test_bout_en_bout_et_registre():
    d, man = collect(); out = os.path.join(tempfile.mkdtemp(), "o"); buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rep = VM.run(SPEC, d, out)
    lines = buf.getvalue().splitlines()
    assert lines[0].startswith("sha256 specification : ") and any(x in lines[1] for x in ("ESPERANCE", "AVANTAGE", "AUCUN"))
    for n in VM.VUES: assert "coupe_utc" in rep["candidats"][n] and "acheter_et_garder" in rep["candidats"][n]
    md = open(os.path.join(out, "verdicts.md")).read()
    assert "Decision pre-enregistree" in md and rep["decision"] in md
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VM.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_source_propre():
    src = open(os.path.join(ROOT, "usine", "verif_m2_memes.py"), encoding="utf-8").read()
    assert "\u2014" not in src and "import requests" not in src

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
