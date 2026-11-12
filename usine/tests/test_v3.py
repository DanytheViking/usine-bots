"""Tests hors ligne du catalogue v3 (Team Chasseur, T1 a T5, Testeur durci).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_v3.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from usine import collecte_v3 as K3, strategies_v3 as S3, verdicts_v3 as V3, verdicts as V
from tests.test_usine import clk, bars, no_fund

H, H4, D = 3_600_000, 4 * 3_600_000, 86_400_000
NOW = 1_794_182_400 + 5 * 3600                                   # lundi 09/11/2026 05:00 UTC
LUNDI = 1_794_182_400_000
MEMES_JEU = ["kPEPE", "kDOGS", "DOGE", "WIF", "FARTCOIN", "TRUMP"]
AUTRES = ["BTC", "ETH", "NOUVEAU", "VIEUX", "xyz:TSLA", "kDOGS2"]

# ================================================================ faux API
def meta_ctx():
    names = MEMES_JEU + AUTRES
    uni = [{"name": c, **({"isDelisted": True} if c == "kDOGS" else {})} for c in names]
    return [{"universe": uni}, [{"dayNtlVlm": "1e8"} for _ in names]]

class FakeAPI3:
    def __init__(self, fail_after=None): self.calls, self.fail_after = [], fail_after
    def __call__(self, body):
        if self.fail_after is not None and len(self.calls) >= self.fail_after: raise ConnectionError("coupure")
        self.calls.append(body); t = body["type"]
        if t == "metaAndAssetCtxs": return meta_ctx()
        if t == "candleSnapshot":
            r = body["req"]; step = {"4h": H4, "1h": H, "1d": D}[r["interval"]]; s, e = r["startTime"], r["endTime"]
            if r["coin"] == "NOUVEAU": s = max(s, e - 60 * D)                         # liste il y a 60 jours
            if r["coin"] == "kDOGS": e = min(e, NOW * 1000 - 30 * D)                   # deliste il y a 30 jours
            seed = int(hashlib.sha256((r["coin"] + r["interval"]).encode()).hexdigest()[:6], 16)
            ts = list(range((s + step - 1) // step * step, e, step)); rng = np.random.default_rng(seed)
            x = 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.02, len(ts))) + 1.5 * np.sin(np.arange(len(ts)) / 90))
            o = np.concatenate([[x[0]], x[:-1]]) if len(ts) else []
            return [{"t": t_, "o": f"{a:.6f}", "c": f"{b:.6f}", "h": f"{max(a, b) * 1.004:.6f}", "l": f"{min(a, b) * 0.996:.6f}", "v": "10"}
                    for t_, a, b in zip(ts, o, x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.0006" if (x // H) % 97 < 6 else "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        raise ValueError(t)

def collect(d=None):
    d = d or os.path.join(tempfile.mkdtemp(), "v3"); clock, sleep = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): man = K3.main(["--out", d], post=FakeAPI3(), clock=clock, sleep=sleep)
    return d, man

# ================================================================ collecteur
def test_collecte_univers_et_listings():
    assert K3.perps(meta_ctx()) == MEMES_JEU + [c for c in AUTRES if ":" not in c]   # HIP-3 exclu, delistes gardes
    d, man = collect()
    assert man["memes"] == ["kPEPE", "kDOGS", "DOGE", "WIF", "FARTCOIN", "TRUMP"]       # ordre de la liste, kDOGS deliste inclus
    assert "kDOGS2" not in man["memes"] and "BTC" not in man["memes"]
    assert man["listings"] == ["NOUVEAU"]
    assert man["debut_1h_ms"] == man["end_ms"] - 5000 * H and man["debut_4h_ms"] == man["end_ms"] - 5000 * H4
    for c in man["memes"]:
        for rel in (f"candles/{c}_4h.json", f"candles/{c}_1h.json", f"funding/{c}.json"): assert rel in man["files"], rel
    fw = json.load(open(os.path.join(d, "funding", "WIF.json")))
    assert int(fw[0]["time"]) < man["debut_1h_ms"] - 1000 * H                                  # funding des memes sur la fenetre 4 h
    assert "candles/BTC_1d.json" in man["files"] and "candles/NOUVEAU_1h.json" in man["files"] and "candles/ETH_1h.json" not in man["files"]
    assert all(f"candles_1d/{c}_1d.json" in man["files"] for c in K3.perps(meta_ctx()))
    clock, sleep = clk(NOW)
    try: K3.main(["--out", d], post=FakeAPI3(), clock=clock, sleep=sleep); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_collecte_reprise_fin_figee():
    d = os.path.join(tempfile.mkdtemp(), "v3"); clock, sleep = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()):
        try: K3.main(["--out", d], post=FakeAPI3(fail_after=9), clock=clock, sleep=sleep); assert False
        except ConnectionError: pass
        api = FakeAPI3(); c2, s2 = clk(NOW + 3 * 86400)
        man = K3.main(["--out", d], post=api, clock=c2, sleep=s2)
    assert man["end_ms"] == NOW * 1000 // H4 * H4
    assert not any(c["type"] == "candleSnapshot" and c["req"]["coin"] == "kPEPE" and c["req"]["interval"] == "4h" for c in api.calls)

# ================================================================ traders
def test_t1_cassure_55_et_sortie_20():
    c = [100.0] * 80 + [101, 103, 106, 110, 115, 120] + [120] * 10 + [118, 112, 100, 90] + [90] * 10
    df = bars(c, step=H4, spread=0.0005)
    tr = S3.t1_tortue("X", df, no_fund())
    first = tr[0]
    assert first["side"] == "long" and first["signal_ts"] == int(df.ts[80]) + H4            # cloture 101 > plus haut des 55
    assert first["entry"] == df.open[81] and first["issue"] in ("sortie signal", "STOP")
    a = S3.atr(df, 20).values[80]; assert abs((first["entry"] - first["stop"]) - 2.0 * a) < 1e-9
    df2 = df.copy(); df2.loc[90:, ["open", "high", "low", "close"]] *= 3                       # le futur ne change pas le signal
    assert S3.t1_tortue("X", df2, no_fund())[0]["signal_ts"] == first["signal_ts"]
    flat = bars([100.0] * 54 + [130.0], step=H4)
    assert S3.t1_tortue("X", flat, no_fund()) == []                                             # moins de 55 bougies precedentes

def test_t2_filtre_btc_bougie_close():
    ts = LUNDI - 300 * D + D * np.arange(300)
    cl = np.r_[np.full(299, 100.0), 50.0]                                                        # derniere journee : BTC sous sa SMA 200
    btc = pd.DataFrame({"ts": ts, "open": cl, "high": cl, "low": cl, "close": np.r_[np.linspace(50, 150, 299), 50.0]})
    allow = S3.btc_regime(btc)
    t_last_close = int(ts[-1]) + D
    assert allow("long", t_last_close - 1) and not allow("short", t_last_close - 1)            # avant la cloture : journee precedente
    assert allow("short", t_last_close) and not allow("long", t_last_close)                    # apres la cloture : nouvelle valeur
    assert not allow("long", int(ts[150]) + D)                                                  # SMA 200 pas encore disponible
    c = [100.0] * 80 + [101, 103, 106, 110, 115, 120] + [120] * 20
    df = bars(c, step=H4, t0=LUNDI - 200 * H4)
    assert S3.t2_tortue_disciplinee("X", df, no_fund(), lambda s, t: False) == []
    vus = []
    longs = S3.t2_tortue_disciplinee("X", df, no_fund(), lambda s, t: vus.append(t) or s == "long")
    assert longs and longs[0]["signal_ts"] == S3.t1_tortue("X", df, no_fund())[0]["signal_ts"] == vus[0]   # filtre lu a la cloture

def test_t3_lundi_et_meilleur_rendement():
    n = 400; t0 = LUNDI - 300 * H4
    up = bars(100 * np.exp(0.002 * np.arange(n)), step=H4, t0=t0)
    fort = bars(100 * np.exp(0.004 * np.arange(n)), step=H4, t0=t0)
    bas = bars(100 * np.exp(-0.002 * np.arange(n)), step=H4, t0=t0)
    tr = S3.t3_druckenmiller({"UP": up, "FORT": fort, "BAS": bas}, {}, int(t0), int(t0) + n * H4)
    assert tr and all(t["coin"] == "FORT" for t in tr)
    for t in tr:
        assert (t["signal_ts"] - LUNDI) % (7 * D) == 0                                          # signal : lundi 00:00 UTC
        assert t["fill_ts"] == t["signal_ts"]
        if t["issue"] == "temps max": assert t["exit_ts"] - t["fill_ts"] == 7 * D
    sig = [t["signal_ts"] for t in tr]; assert sig == sorted(set(sig))
    assert S3.t3_druckenmiller({"BAS": bas}, {}, int(t0), int(t0) + n * H4) == []              # rendement negatif : rien
    c = np.r_[100 * np.exp(0.01 * np.arange(200)), 100 * np.exp(0.01 * 199) * np.exp(-0.0005 * np.arange(1, 201))]
    pic = bars(c, step=H4, t0=t0); cl = pic.close.values; em = pic.close.ewm(span=50, adjust=False).mean().values
    lundis = [k for k in range(242, 400) if (int(pic.ts[k]) + H4 - LUNDI) % (7 * D) == 0 and cl[k] > em[k] and cl[k] < cl[k - 42]]
    assert lundis                                                                                # au-dessus de l'EMA mais rendement < 0
    pris = {t["signal_ts"] for t in S3.t3_druckenmiller({"PIC": pic}, {}, int(t0), int(t0) + 400 * H4)}
    assert not pris & {int(pic.ts[k]) + H4 for k in lundis}

def test_t4_funding_trois_heures_et_hausse():
    n = 200; t0 = LUNDI
    c = np.r_[np.full(100, 100.0), np.linspace(100, 140, 20), np.full(80, 140.0)]
    df = bars(c, step=H, t0=t0, spread=0.0005)
    times = t0 + H * np.arange(1, n + 1); rates = np.full(n, 0.00001)
    i = 119; rates[i - 2:i + 1] = 0.0006                                                         # funding regle aux clotures de i-2, i-1, i
    rates[i + 1:i + 6] = 0.0003; rates[i + 6] = 0.00005                                          # repasse sous 0,01 % a la cloture de i+6
    tr = S3.t4_contrarien("X", df, (times, rates))
    assert len(tr) == 1 and tr[0]["side"] == "short" and tr[0]["signal_ts"] == int(df.ts[i]) + H
    assert tr[0]["issue"] == "sortie signal" and tr[0]["exit_ts"] == int(df.ts[i + 7])
    r2 = rates.copy(); r2[i - 2] = 0.0004
    assert S3.t4_contrarien("X", df, (times, r2)) == []                                          # seulement deux heures au-dessus
    r3 = rates.copy(); r3[i + 1:] = 0.0006
    t3 = S3.t4_contrarien("X", df, (times, r3))
    assert t3[0]["issue"] in ("temps max", "STOP") and (t3[0]["issue"] == "STOP" or t3[0]["exit_ts"] - t3[0]["fill_ts"] == 48 * H)
    c20 = np.r_[np.full(100, 100.0), np.linspace(100, 120, 20), np.full(80, 120.0)]
    assert S3.t4_contrarien("X", bars(c20, step=H, t0=t0, spread=0.0005), (times, rates)) == []   # hausse de 20 % seulement
    flat = bars(np.full(n, 100.0), step=H, t0=t0)
    assert S3.t4_contrarien("X", flat, (times, rates)) == []                                     # pas de hausse de 30 %

def test_t5_listing_un_seul_trade():
    c = np.r_[np.linspace(10, 14, 30), np.full(100, 14.0)]
    df = bars(c, step=H, t0=LUNDI)
    tr = S3.t5_listings("NEW", df, no_fund(), int(df.ts[0]))
    assert len(tr) == 1 and tr[0]["side"] == "long" and tr[0]["signal_ts"] == int(df.ts[0]) + 24 * H
    assert tr[0]["issue"] != "temps max" or tr[0]["exit_ts"] - tr[0]["fill_ts"] == 72 * H
    down = bars(np.r_[np.linspace(14, 10, 30), np.full(100, 10.0)], step=H, t0=LUNDI)
    assert S3.t5_listings("NEW", down, no_fund(), int(down.ts[0]))[0]["side"] == "short"
    rep = np.r_[np.linspace(10, 14, 24), 13.0, np.full(100, 13.0)]; rep[23] = 13.0
    pb = bars(rep, step=H, t0=LUNDI)
    assert pb.close[23] > pb.open[0] and pb.close[23] < pb.open[23]
    assert S3.t5_listings("NEW", pb, no_fund(), int(pb.ts[0]))[0]["side"] == "long"               # compare a l'ouverture du listing
    assert S3.t5_listings("NEW", df.iloc[5:].reset_index(drop=True), no_fund(), int(df.ts[0])) == []   # debut manquant : pas de trade
    assert S3.t5_listings("NEW", df.iloc[:20], no_fund(), int(df.ts[0])) == []

def test_parametres_figes():
    assert S3.T1 == {"entree": 55, "sortie": 20, "atr": 20, "stop_atr": 2.0}
    assert S3.T3 == {"rendement_bars": 42, "ema": 50, "atr": 14, "stop_atr": 3.0, "duree_bars": 42}
    assert S3.T4 == {"funding_seuil": 0.0005, "heures": 3, "hausse": 0.30, "hausse_bars": 72, "atr": 14, "stop_atr": 2.0, "sortie_funding": 0.0001, "duree_max": 48}
    assert S3.T5 == {"attente_bars": 24, "duree_bars": 72, "atr": 14, "stop_atr": 2.0}
    assert len(K3.MEMES) == 30 and len(set(K3.MEMES)) == 30

# ================================================================ testeur durci
def test_acheter_et_garder():
    a = bars(np.linspace(100, 200, 101), step=H, t0=0); b = bars(np.linspace(100, 50, 101), step=H, t0=0)
    late = bars(np.linspace(10, 30, 21), step=H, t0=80 * H)
    r = V3.buy_and_hold({"A": a, "B": b, "L": late}, 50 * H, 101 * H, H)
    exp = ((200 / a.open[50] - 1) + (50 / b.open[50] - 1)) / 2
    assert r["actifs"] == 2 and abs(r["rendement_pct"] - round(100 * exp, 2)) < 1e-9
    assert V3.buy_and_hold({}, 0, 1, H) == {"actifs": 0, "rendement_pct": None}

def test_leave_one_asset_out(monkey=None):
    real = V.evaluate
    try:
        V.evaluate = lambda n, trades, t0, t1, spec: {"verdict": "AVANTAGE" if any(t["coin"] == "A" for t in trades) else "PAS D'AVANTAGE"}
        trades = [{"coin": c} for c in ("A", "B", "C")]
        assert V3.loao(trades, 0, 1, {}) == ["A"]
        V.evaluate = lambda n, trades, t0, t1, spec: {"verdict": "AVANTAGE"}
        assert V3.loao(trades, 0, 1, {}) == []
    finally:
        V.evaluate = real

def test_evaluate_stress_et_dependance():
    spec = json.load(open(os.path.join(ROOT, "specs", "USINE-SPEC-v3.json")))
    t0, t1 = 0, 200 * D; trades = []
    for k in range(200):
        day = k * D; coin = "SEUL" if k % 2 else "AUTRE"
        r = 2.0 if coin == "SEUL" else -0.05
        trades.append({"coin": coin, "strat": "x", "side": "long", "signal_ts": day, "fill_ts": day, "exit_ts": day + H,
                       "R": r, "gross_R": r + 0.1, "fees_R": 0.1, "funding_R": 0.0, "issue": "x"})
    b = {"SEUL": bars(np.full(300, 10.0), step=D, t0=0)}
    row = V3.evaluate("T", trades, t0, t1, b, D, spec)
    s2, s3 = row["evaluation_frais_doubles"]["global"], row["evaluation_frais_stress"]["global"]
    assert s3["trades"] == s2["trades"] and s3["esperance_R"] < s2["esperance_R"]
    assert row["dependant_de"] == ["SEUL"] and row["verdict"].startswith("PAS D'AVANTAGE : depend d'un seul actif")
    assert row["strategie_1pc_pct"] == round(s2["somme_R"], 2) and row["acheter_et_garder"]["actifs"] == 1

def test_spec_v3_figee():
    s = json.load(open(os.path.join(ROOT, "specs", "USINE-SPEC-v3.json")))
    h = lambda f: hashlib.sha256(open(os.path.join(ROOT, "docs", f), "rb").read()).hexdigest()
    assert s["prereg_sha256"] == h("PREREG-usine-catalogue-v3-chasseur.md")
    assert s["addendum_sha256"] == h("PREREG-usine-catalogue-v3-addendum-T6.md")
    assert s["mise_en_oeuvre_sha256"] == h("MISE-EN-OEUVRE-catalogue-v3.md")
    assert s["criteres"] == {"trades_min": 30, "pf_min": 1.35, "jours_min_ic": 7} and s["stress_frais"] == 3
    assert s["fraction_evaluation"] == 0.5 and sorted(s["candidats"]) == sorted(V3.CANDIDATS_V3)
    for bad in ({**s, "criteres": {**s["criteres"], "pf_min": 1.2}}, {k: v for k, v in s.items() if k != "stress_frais"},
                {**s, "candidats": s["candidats"][:4]}, {**s, "scenarios_frais": [1, 3]}):
        p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
        try: V3.load_spec(p); assert False
        except V.SpecError: pass

def test_verdicts_v3_bout_en_bout():
    d, man = collect(); spec = os.path.join(ROOT, "specs", "USINE-SPEC-v3.json"); out = os.path.join(tempfile.mkdtemp(), "o")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rep = V3.run(spec, d, out)
    assert buf.getvalue().splitlines()[0].startswith("sha256 specification : ")
    for n in V3.CANDIDATS_V3:
        r = rep["candidats"][n]
        assert "coupe_utc" in r and "evaluation_frais_stress" in r and "acheter_et_garder" in r, n
    import datetime as dt
    j1 = dt.datetime.fromtimestamp(man["debut_1h_ms"] / 1000, dt.timezone.utc).isoformat()[:10]
    assert rep["candidats"]["T4_contrarien"]["fenetre_utc"][0] == j1 == rep["candidats"]["T5_listings"]["fenetre_utc"][0]
    assert rep["candidats"]["T1_tortue"]["fenetre_utc"][0] < j1
    t5 = rep["candidats"]["T5_listings"]
    assert set(t5["evaluation_frais_base"]["par_actif"]) | set(t5["entrainement_frais_base"]["par_actif"]) <= {"NOUVEAU"}
    md = open(os.path.join(out, "verdicts.md")).read()
    assert "catalogue v3 (Team Chasseur)" in md and "## Testeur durci" in md and "Listings de la fenetre 1 h : NOUVEAU" in md
    other = json.load(open(spec)); other["gel_utc"] = "autre"
    p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: V3.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)
    f = os.path.join(d, "candles", "WIF_4h.json"); open(f, "a").write(" ")
    try: V3.run(spec, d, os.path.join(tempfile.mkdtemp(), "o2")); assert False
    except Exception as e: assert "empreinte" in str(e)

def test_sources_v3_propres():
    for f in ("collecte_v3.py", "strategies_v3.py", "verdicts_v3.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
        assert "\u2014" not in src and "import requests" not in src and "order" not in src.lower().replace("ordre", "")

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
