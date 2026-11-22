"""Tests hors ligne du test M2 sur les marches HIP-3 (collecte et univers, frais HIP-3, verdicts, regle de decision).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_hip3.py"""
import os, sys, json, io, tempfile, hashlib, contextlib, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import collecte_hip3 as KH, verif_m2_hip3 as VH, verdicts as V
from peanut import replay as RP

H = 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-HIP3.json")
NOW = int(dt.datetime(2026, 11, 22, 21, tzinfo=dt.timezone.utc).timestamp())
VALIDATEURS = ["BTC", "ETH", "kPEPE", "PAXG"]
DEX = {"xyz": [("GOLD", 9e6, 5000), ("XYZ100", 8e6, 5000), ("TSLA", 7e6, 1500), ("SILVER", 6e6, 5000), ("BTC", 5e7, 5000)],
       "flx": [("flx:GOLD", 1e6, 5000), ("OIL", 5e6, 5000), ("PEPE", 4e6, 5000), ("OLD", 9e9, 5000, True)]}

def nbougies(coin):
    for d, xs in DEX.items():
        for x in xs:
            n = x[0] if ":" in x[0] else f"{d}:{x[0]}"
            if n == coin: return x[2]
    return 5000

class FakeAPI:
    def __init__(self): self.calls = []
    def __call__(self, body):
        self.calls.append(body); t = body["type"]
        if t == "perpDexs": return [None, {"name": "xyz", "deployerFeeScale": "1.0"}, {"name": "flx"}]
        if t == "metaAndAssetCtxs":
            if "dex" not in body: return [{"universe": [{"name": c} for c in VALIDATEURS]}, [{} for _ in VALIDATEURS]]
            xs = DEX[body["dex"]]
            return [{"universe": [{"name": x[0], **({"isDelisted": True} if len(x) > 3 else {})} for x in xs]},
                    [{"dayNtlVlm": str(x[1])} for x in xs]]
        if t == "candleSnapshot":
            r = body["req"]; assert r["interval"] == "1h"; e = r["endTime"]
            n = nbougies(r["coin"]); ts = list(range(e - n * H, e, H))
            rng = np.random.default_rng(int(hashlib.sha256(r["coin"].encode()).hexdigest()[:6], 16))
            x = 100 * np.exp(0.3 * np.sin(np.arange(len(ts)) / 90) + np.cumsum(rng.normal(0, 0.004, len(ts))))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": a, "o": f"{b:.6f}", "c": f"{c:.6f}", "h": f"{max(b, c) * 1.002:.6f}", "l": f"{min(b, c) * 0.998:.6f}",
                     "v": f"{1e5 / c:.4f}"} for a, b, c in zip(ts, o, x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        raise ValueError(t)

def clk(t):
    c = [float(t)]
    return (lambda: c[0]), (lambda s: c.__setitem__(0, c[0] + s))

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KH.main(["--out", d], post=FakeAPI(), clock=now, sleep=sl)

def test_univers_regle_preenregistree():
    d = tempfile.mkdtemp(); man = collect(d)
    # BTC et PEPE (crypto) exclus, OLD (deliste) exclu, flx:GOLD ecarte au profit de xyz:GOLD, TSLA sous 2000 bougies
    assert man["coins"] == ["xyz:GOLD", "xyz:XYZ100", "xyz:SILVER", "flx:OIL"], man["coins"]
    assert [x["marche"] for x in man["classement"]] == ["xyz:GOLD", "xyz:XYZ100", "xyz:TSLA", "xyz:SILVER", "flx:OIL"]
    assert "candles/xyz_GOLD_1h.json" in man["files"] and "funding/flx_OIL.json" in man["files"] and "candles/BTC_1h.json" in man["files"]
    assert "funding/xyz_TSLA.json" not in man["files"] and man["jeu"] == "hip3"
    assert {"name": "xyz", "deployerFeeScale": "1.0"} in man["frais_publies"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_base_sous_jacent():
    assert KH.base("xyz:GOLD") == "GOLD" and KH.base("kPEPE") == "PEPE" and KH.base("1000BONK") == "BONK" and KH.base("xyz:KO") == "KO"

def test_frais_hip3_doubles():
    t = {"R": 1.0, "gross_R": 1.2, "fees_R": 0.1, "funding_R": -0.1}
    x = VH.hip3([t])[0]
    assert abs(x["fees_R"] - 0.2) < 1e-12 and abs(x["R"] - 0.9) < 1e-12
    y = RP.with_fees(x, 2.0); assert abs(y["fees_R"] - 0.4) < 1e-12                    # scenario frais doubles = 4 x bareme validateur

def test_verdicts_bout_en_bout():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VH.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VH.CANDIDATS) and os.path.exists(os.path.join(out, "verdicts.md"))
    r = rep["candidats"]["M2_1h_hip3"]
    assert r["evaluation_frais_doubles"]["global"]["trades"] > 0
    assert "Frais de base HIP-3 = 2 x" in open(os.path.join(out, "verdicts.md")).read()

def test_correlation():
    a = {i: float(i % 3) for i in range(20)}
    assert VH.correlation(a, a) == 1.0 and VH.correlation({1: 1.0}, {1: 1.0}) is None

def test_regle_de_decision():
    row = lambda e, n, v: {"evaluation_frais_doubles": {"global": {"esperance_R": e, "trades": n}}, "verdict": v}
    assert VH.decide(row(0.2, 50, "AVANTAGE CRÉDIBLE")).startswith("AVANTAGE : adapter")
    assert VH.decide(row(0.05, 50, "PAS D'AVANTAGE : x")).startswith("ESPERANCE >= 0")
    assert VH.decide(row(-0.05, 50, "PAS D'AVANTAGE : x")).startswith("ESPERANCE NEGATIVE")
    assert VH.decide(row(None, 0, "NON CONCLUANT")).startswith("AUCUN TRADE")

def test_spec_figee_et_bornes():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-hip3-m2.md"), "rb").read()).hexdigest()
    assert s["criteres"] == {"trades_min": 30, "pf_min": 1.35, "jours_min_ic": 7} and s["facteur_frais_hip3"] == 2
    for bad in (dict(s, criteres={**s["criteres"], "pf_min": 1.2}), dict(s, facteur_frais_hip3=1), dict(s, decisif="M2_4h_reconstruit")):
        p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
        try: VH.load_spec(p); assert False
        except V.SpecError: pass

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]; ok = 0
    for n, f in tests:
        try: f(); ok += 1; print("ok", n)
        except Exception as e:
            import traceback; traceback.print_exc(); print("ECHEC", n, repr(e))
    print(f"{ok}/{len(tests)} tests ok")
    sys.exit(0 if ok == len(tests) else 1)
