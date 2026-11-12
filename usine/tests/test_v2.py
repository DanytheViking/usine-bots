"""Tests hors ligne du catalogue v2 (collecteurs v2, verdicts v2).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_v2.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import collecte_v2 as K2, verdicts_v2 as V2, collecte as K
from tests.test_usine import clk, fill

H, H4, DAY = 3_600_000, 4 * 3_600_000, 86_400_000
NOW = 1_793_404_800
COINS = ["BTC", "ETH", "SOL"] + [f"A{k:02d}" for k in range(14)] + ["JEUNE", "MORT", "xyz:TSLA"]

def meta_ctx():
    uni = [{"name": c, **({"isDelisted": True} if c == "MORT" else {})} for c in COINS]
    vol = {c: 1e9 - k * 1e7 for k, c in enumerate(COINS)}; vol["JEUNE"] = 9.9e8; vol["MORT"] = 9.95e8; vol["xyz:TSLA"] = 9.99e8
    vol["A13"] = 1e6
    return [{"universe": uni}, [{"dayNtlVlm": str(vol[c])} for c in COINS]]

class FakeAPI2:
    def __init__(self, fail_after=None): self.calls, self.fail_after = [], fail_after
    def __call__(self, body):
        if self.fail_after is not None and len(self.calls) >= self.fail_after: raise ConnectionError("coupure")
        self.calls.append(body); t = body["type"]
        if t == "metaAndAssetCtxs": return meta_ctx()
        if t == "candleSnapshot":
            r = body["req"]; step = H4 if r["interval"] == "4h" else H; s, e = r["startTime"], r["endTime"]
            if r["coin"] == "JEUNE": s = max(s, e - 800 * step)
            seed = int(hashlib.sha256(r["coin"].encode()).hexdigest()[:6], 16)
            ts = list(range(s // step * step, e, step)); rng = np.random.default_rng(seed)
            x = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(ts))) + 2 * np.sin(np.arange(len(ts)) / 150))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": t_, "o": f"{a:.5f}", "c": f"{b:.5f}", "h": f"{max(a, b) * 1.003:.5f}", "l": f"{min(a, b) * 0.997:.5f}", "v": "10"}
                    for t_, a, b in zip(ts, o, x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        if t == "userFillsByTime":
            s = body["startTime"]
            return [fill("ETH", s + k * 6 * H, 100, 1, "B" if k % 2 == 0 else "A", 0 if k % 2 == 0 else 1, pnl=0 if k % 2 == 0 else 2.0) for k in range(200)]
        raise ValueError(t)

def lb():
    row = lambda a, acct, v: {"ethAddress": a, "accountValue": str(acct), "windowPerformances": [["month", {"vlm": str(v)}]]}
    rows = [row(f"0x{k:040x}", 20_000 + k, 2e6 + k) for k in range(400)]
    rows += [row("0xgros", 9e6, 5e6), row("0xactif", 5e4, 9e8), row("0xpetit", 5e4, 1e5), {"x": 1}]
    return {"leaderboardRows": rows}

def test_classement_et_regle_etendu():
    r = K2.ranking(meta_ctx())
    names = [n for n, _ in r]
    assert "xyz:TSLA" not in names and "MORT" not in names and names[0] == "BTC"
    d = os.path.join(tempfile.mkdtemp(), "et"); clock, sleep = clk(NOW)
    man = K2.main(["etendu", "--out", d], post=FakeAPI2(), clock=clock, sleep=sleep)
    assert man["coins"] == [f"A{k:02d}" for k in range(10)]                       # top 10 hors BTC ETH SOL, JEUNE ecarte
    sel = json.load(open(os.path.join(d, "selection.json")))
    assert sel["ecartes"] == {"JEUNE": 800} and "BTC" not in man["coins"]
    assert all(f"funding/{c}.json" in man["files"] for c in man["coins"]) and "funding/JEUNE.json" not in man["files"]

def test_etendu_reprise():
    d = os.path.join(tempfile.mkdtemp(), "et"); clock, sleep = clk(NOW)
    try: K2.main(["etendu", "--out", d], post=FakeAPI2(fail_after=5), clock=clock, sleep=sleep); assert False
    except ConnectionError: pass
    api = FakeAPI2(); c2, s2 = clk(NOW + 10 * DAY)
    man = K2.main(["etendu", "--out", d], post=api, clock=c2, sleep=s2)
    assert man["end_ms"] == NOW * 1000 // H4 * H4 and man["coins"] == [f"A{k:02d}" for k in range(10)]
    assert not any(c["type"] == "candleSnapshot" and c["req"]["coin"] == "A00" for c in api.calls)

def test_echantillon_aleatoire_deterministe_et_filtre():
    p1, p2 = K2.sample_pool(lb()), K2.sample_pool(lb())
    assert p1 == p2 and len(p1) == 150
    addrs = {p["adresse"] for p in p1}
    assert not addrs & {"0xgros", "0xactif", "0xpetit"}
    assert addrs != {f"0x{k:040x}" for k in range(150)}                           # pas les 150 premiers : vrai tirage
    few = {"leaderboardRows": lb()["leaderboardRows"][:3] + lb()["leaderboardRows"][-4:]}
    assert {p["adresse"] for p in K2.sample_pool(few)} == {f"0x{k:040x}" for k in range(3)}   # bornes de compte et de volume

def test_baleines2_univers_joue():
    d = os.path.join(tempfile.mkdtemp(), "b2"); clock, sleep = clk(NOW)
    small = {"leaderboardRows": lb()["leaderboardRows"][:5]}
    man = K2.main(["baleines2", "--out", d], post=FakeAPI2(), clock=clock, sleep=sleep, get_json=lambda u: small)
    assert man["nb_wallets"] == 5 and "A13" not in man["coins"] and {"BTC", "ETH", "SOL", "JEUNE"} <= set(man["coins"])
    assert "MORT" not in man["coins"] and "xyz:TSLA" not in man["coins"]

def build_all():
    et = os.path.join(tempfile.mkdtemp(), "et"); clock, sleep = clk(NOW)
    K2.main(["etendu", "--out", et], post=FakeAPI2(), clock=clock, sleep=sleep)
    b2 = os.path.join(tempfile.mkdtemp(), "b2"); clock, sleep = clk(NOW)
    K2.main(["baleines2", "--out", b2], post=FakeAPI2(), clock=clock, sleep=sleep, get_json=lambda u: {"leaderboardRows": lb()["leaderboardRows"][:5]})
    mj = os.path.join(tempfile.mkdtemp(), "mj"); clock, sleep = clk(NOW)
    K.main(["majeurs", "--out", mj], post=FakeAPI2(), clock=clock, sleep=sleep)
    return et, b2, mj

def test_verdicts_v2_bout_en_bout():
    et, b2, mj = build_all(); spec = os.path.join(ROOT, "specs", "USINE-SPEC-v2.json"); out = os.path.join(tempfile.mkdtemp(), "o")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rep = V2.run(spec, out, etendu=et, baleines2=b2, majeurs=mj)
    assert buf.getvalue().splitlines()[0].startswith("sha256 specification : ")
    for n in ("M2_etendu", "C1_v2", "M2_13_actifs_information"): assert "coupe_utc" in rep["candidats"][n], n
    assert rep["candidats"]["M2_13_actifs_information"]["verdict"].startswith("INFORMATION SEULEMENT")
    m2 = rep["candidats"]["M2_etendu"]
    coins = set(m2["evaluation_frais_base"]["par_actif"]) | set(m2["entrainement_frais_base"]["par_actif"])
    assert coins and not coins & {"BTC", "ETH", "SOL"}                             # verdict principal : nouveaux actifs seulement
    info = rep["candidats"]["M2_13_actifs_information"]
    assert {"BTC", "ETH", "SOL"} & (set(info["evaluation_frais_base"]["par_actif"]) | set(info["entrainement_frais_base"]["par_actif"]))
    assert rep["notes"]["copie"]["wallets_telecharges"] == 5
    md = open(os.path.join(out, "verdicts.md")).read()
    assert "catalogue v2" in md and "Actifs de M2_etendu" in md and md.count("| ne_rien_trader |") >= 4
    other = json.load(open(spec)); other["criteres"]["pf_min"] = 1.1
    p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: V2.run(p, out, etendu=et); assert False
    except Exception as e: assert "refus" in str(e)

def test_spec_v2():
    s = json.load(open(os.path.join(ROOT, "specs", "USINE-SPEC-v2.json")))
    h = lambda f: hashlib.sha256(open(os.path.join(ROOT, "docs", f), "rb").read()).hexdigest()
    assert s["prereg_sha256"] == h("PREREG-usine-catalogue-v2.md") and s["criteres"] == {"trades_min": 30, "pf_min": 1.2, "jours_min_ic": 7}
    p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump({**s, "candidats": ["M2_etendu"]}, open(p, "w"))
    try: V2.load_spec(p); assert False
    except V2.V.SpecError: pass
    assert (K2.NB_ETENDU, K2.MIN_BARS_4H, K2.GRAINE, K2.ECHANTILLON, K2.VLM_MIN, K2.VLM_MAX, K2.VOL_JOUE) == (10, 1500, 20261112, 150, 1e6, 5e7, 5e6)

def test_sources_v2_propres():
    for f in ("collecte_v2.py", "verdicts_v2.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
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
