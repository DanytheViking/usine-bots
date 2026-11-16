"""Tests hors ligne du test M2 1 h de Moonshot (collecte, agregation 4 h, verdicts, regle de decision).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_m2h1.py"""
import os, sys, json, io, tempfile, hashlib, contextlib, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import collecte_m2h1 as KM, verif_m2_1h as VM, strategies as S, verdicts as V
from tests.test_usine import clk, bars, no_fund

H, H4 = 3_600_000, 4 * 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-M2H1.json")
NOW = int(dt.datetime(2026, 11, 16, 18, tzinfo=dt.timezone.utc).timestamp())
COINS = ["BTC", "ETH", "kPEPE", "XMR"]

class FakeAPI:
    def __init__(self): self.calls = []
    def __call__(self, body):
        self.calls.append(body); t = body["type"]
        if t == "metaAndAssetCtxs": return [{"universe": [{"name": c} for c in COINS + ["DOGE", "xyz:TSLA"]]}, [{} for _ in range(6)]]
        if t == "candleSnapshot":
            r = body["req"]; assert r["interval"] == "1h"; s, e = r["startTime"], r["endTime"]
            ts = list(range((s + H - 1) // H * H, e, H))
            rng = np.random.default_rng(int(hashlib.sha256(r["coin"].encode()).hexdigest()[:6], 16))
            x = 100 * np.exp(0.3 * np.sin(np.arange(len(ts)) / 90) + np.cumsum(rng.normal(0, 0.004, len(ts))))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": a, "o": f"{b:.6f}", "c": f"{c:.6f}", "h": f"{max(b, c) * 1.002:.6f}", "l": f"{min(b, c) * 0.998:.6f}",
                     "v": f"{1e5 / c:.4f}"} for a, b, c in zip(ts, o, x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        raise ValueError(t)

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KM.main(["--out", d], post=FakeAPI(), clock=now, sleep=sl)

def test_collecte_actifs_moonshot_et_refus_d_ecraser():
    d = tempfile.mkdtemp(); man = collect(d)
    assert man["coins"] == ["BTC", "ETH", "kPEPE", "XMR"] and man["jeu"] == "m2h1"
    assert man["debut_1h_ms"] == man["end_ms"] - 5000 * H and "candles/XMR_1h.json" in man["files"] and "candles/DOGE_1h.json" not in man["files"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_liste_moonshot_identique_au_bot():
    p = os.path.join(os.path.dirname(ROOT), "moonshot2", "moon", "config.py")
    if not os.path.exists(p): return                                                     # cible usine seule sur le VPS : le bot n'est pas monte
    src = open(p, encoding="utf-8").read()
    line = next(l for l in src.splitlines() if l.startswith("COINS_DEFAUT"))
    assert tuple(eval(line.split("=", 1)[1].strip())) == KM.MOONSHOT

def test_agregation_4h_tranches_completes():
    c = 100 + np.arange(21, dtype=float); df = bars(c, step=H)
    df["ts"] = df.ts - df.ts.iloc[0] % H4 + H                                             # commence une heure apres une tranche : premiere incomplete
    x = VM.vers_4h(df)
    assert len(x) == 4 and (x.ts % H4 == 0).all()
    k = df[(df.ts >= x.ts[0]) & (df.ts < x.ts[0] + H4)]
    assert x.open[0] == k.open.iloc[0] and x.close[0] == k.close.iloc[-1] and x.high[0] == k.high.max() and x.vol[0] == k.vol.sum()

def test_m2_1h_identique_au_testeur():
    c = 100 * np.exp(0.4 * np.sin(np.arange(2500) / 150)); df = bars(c, step=H)
    a = VM.m2("X", df, no_fund(), H, "M2_1h_moonshot"); b = S.m2_croisement_ema("X", df, no_fund(), tf_ms=H)
    assert len(a) > 3 and all(t["strat"] == "M2_1h_moonshot" for t in a)
    assert [{k: v for k, v in t.items() if k != "strat"} for t in a] == [{k: v for k, v in t.items() if k != "strat"} for t in b]
    assert S.M2 == {"rapide": 50, "lente": 200, "stop_atr": 3.0}

def test_regle_de_decision():
    row = lambda e, n, v: {"evaluation_frais_doubles": {"global": {"esperance_R": e, "trades": n}}, "verdict": v}
    assert VM.decide(row(0.2, 50, "AVANTAGE CRÉDIBLE")).startswith("AVANTAGE : papier")
    assert VM.decide(row(0.05, 50, "PAS D'AVANTAGE : x")).startswith("ESPERANCE >= 0")
    assert VM.decide(row(-0.05, 50, "PAS D'AVANTAGE : x")).startswith("ESPERANCE NEGATIVE")
    assert VM.decide(row(None, 0, "NON CONCLUANT")).startswith("AUCUN TRADE")

def test_spec_figee_et_bornes():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-moonshot-m2-1h.md"), "rb").read()).hexdigest()
    assert s["criteres"] == {"trades_min": 30, "pf_min": 1.35, "jours_min_ic": 7} and s["decisif"] == "M2_1h_moonshot"
    for bad in (dict(s, criteres={**s["criteres"], "pf_min": 1.2}), dict(s, candidats=["M2_1h_moonshot"]), dict(s, decisif="M2_4h_reconstruit")):
        p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
        try: VM.load_spec(p); assert False
        except V.SpecError: pass

def test_verdicts_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = os.path.join(tempfile.mkdtemp(), "o"); buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rep = VM.run(SPEC, d, out)
    lines = buf.getvalue().splitlines()
    assert lines[0].startswith("sha256 specification : ") and lines[1] == rep["decision"]
    assert set(rep["candidats"]) == set(VM.CANDIDATS)
    for r in rep["candidats"].values(): assert "trades_par_mois" in r and "acheter_et_garder" in r and "evaluation_frais_stress" in r
    md = open(os.path.join(out, "verdicts.md")).read(); assert rep["decision"] in md
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VM.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_travaux():
    jobs = os.path.join(os.path.dirname(ROOT), "jobs")
    if not os.path.isdir(jobs): return                                                  # cible usine seule sur le VPS
    c = json.load(open(os.path.join(jobs, "m2h1-collecte-2026-11-16.json"))); v = json.load(open(os.path.join(jobs, "m2h1-verdicts-2026-11-16.json")))
    assert c["module"] == "usine.collecte_m2h1" and c["reseau"] is True and c["args"] == ["--out", "/d/m2h1"]
    assert v["module"] == "usine.verif_m2_1h" and v["reseau"] is False and "specs/USINE-SPEC-M2H1.json" in v["args"] and "--attendre" in v["args"]

def test_source_propre():
    for f in ("collecte_m2h1.py", "verif_m2_1h.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
        assert "—" not in src
        if f != "collecte_m2h1.py": assert "import requests" not in src

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
