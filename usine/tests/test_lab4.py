"""Tests hors ligne du Lab v4 « furie » (strategies, capacite, collecte, verdicts).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab4.py"""
import os, sys, json, io, tempfile, hashlib, contextlib, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from usine import strategies_lab4 as L, collecte_lab4 as KL, verdicts_lab4 as VL, verdicts as V
from tests.test_usine import clk, bars, no_fund

M15, H, D = 900_000, 3_600_000, 86_400_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB4.json")
JOUR = int(dt.datetime(2026, 11, 16, tzinfo=dt.timezone.utc).timestamp() * 1000)      # lundi, heure d'hiver americaine

def liquide(df, usd=1e6): df.loc[:, "vol"] = usd / df.close; return df

# ================================================================ L1 compression
def compression(n=260, saut=1.05):
    rng = np.random.default_rng(1)
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))
    c[-30:] = c[-31]                                                                     # compression finale
    c = np.concatenate([c, [c[-1] * saut, c[-1] * saut * 1.01, c[-1] * saut * 1.02] + [c[-1] * saut * 1.03] * 40])
    return liquide(bars(c, step=H))

def test_compression_cassure_longue_cible_2R():
    df = compression(); trs = L.l1_compression("X", df, no_fund(), H, "L1")
    t = [x for x in trs if x["signal_ts"] >= df.ts.values[260]]
    assert t, "la cassure apres compression doit donner un signal"
    t = t[0]; i = int(np.searchsorted(df.ts.values, t["signal_ts"] - H))
    assert t["side"] == "long" and t["entry"] == df.open.values[i + 1]
    assert abs(t["tp"] - t["entry"] - 2 * (t["entry"] - t["stop"])) < 1e-9

def test_compression_exige_la_liquidite():
    df = compression(); df.loc[:, "vol"] = 1e4 / df.close                                # 24 x 10 000 $ = 240 000 $
    assert L.l1_compression("X", df, no_fund(), H, "L1") == []

def test_compression_stop_au_moins_un_atr():
    df = compression(); a = L.atr(df, 14).values
    for t in L.l1_compression("X", df, no_fund(), H, "L1"):
        i = int(np.searchsorted(df.ts.values, t["signal_ts"] - H))
        assert abs(t["entry"] - t["stop"]) >= a[i] - 1e-9

# ================================================================ L1b plage Asie / seance US
def test_heure_ete_us():
    assert L.heure_ete_us(dt.date(2026, 7, 1)) and not L.heure_ete_us(dt.date(2026, 11, 16))
    assert L.heure_ete_us(dt.date(2026, 3, 8)) and not L.heure_ete_us(dt.date(2026, 3, 7))
    assert not L.heure_ete_us(dt.date(2026, 11, 1)) and L.heure_ete_us(dt.date(2026, 10, 31))
    o, f = L.seance_us(JOUR); assert (o - JOUR, f - JOUR) == (14 * H + H // 2, 21 * H)

def asie_us(breakout_h=15.0, n_jours=3):
    n = n_jours * 96; c = np.full(n, 100.0)
    k = n - 96 + int(breakout_h * 4)                                                     # dernier jour
    c[k:] = 103.0
    return liquide(bars(c, step=M15, t0=JOUR - (n_jours - 1) * D, spread=0.002))

def test_asie_us_cassure_et_sortie_fin_de_seance():
    df = asie_us(); trs = L.l1b_asie_us("X", df, no_fund())
    t = [x for x in trs if x["signal_ts"] >= JOUR]
    assert len(t) == 1 and t[0]["side"] == "long" and t[0]["issue"] == "temps max"
    assert t[0]["signal_ts"] == JOUR + 15 * H + M15 and t[0]["exit_ts"] == JOUR + 21 * H

def test_asie_us_hors_fenetre_ignoree():
    df = asie_us(breakout_h=20.5); t = [x for x in L.l1b_asie_us("X", df, no_fund()) if x["signal_ts"] >= JOUR]
    assert t == []                                                                       # 20 h 30 : moins d'une heure avant la fin

def test_asie_us_avant_ouverture_ignoree():
    df = asie_us(breakout_h=12.0)                                                        # cassure avant l'ouverture : la plage du jour est deja depassee
    t = [x for x in L.l1b_asie_us("X", df, no_fund()) if x["signal_ts"] >= JOUR]
    assert len(t) == 1 and t[0]["signal_ts"] == JOUR + 14 * H + H // 2 + M15             # premiere cloture de seance hors plage

# ================================================================ L2 top movers
def test_top_movers_volume_x3():
    c = np.concatenate([np.full(60, 100.0), [104.0], np.full(20, 104.0)])
    df = liquide(bars(c, step=H)); v = df.vol.values.copy(); v[60] *= 3.5; df.loc[:, "vol"] = v
    t = L.l2_top_movers("X", df, no_fund())
    assert len(t) == 1 and t[0]["side"] == "long" and t[0]["issue"] == "temps max"
    assert t[0]["exit_ts"] - t[0]["fill_ts"] == 6 * H
    v[60] = v[59] * 2.5; df.loc[:, "vol"] = v
    assert L.l2_top_movers("X", df, no_fund()) == []

# ================================================================ capacite et croissance
def test_capacite_deux_positions():
    tr = lambda c, a, b: {"coin": c, "fill_ts": a, "exit_ts": b, "R": 1.0}
    got = L.capacite([tr("A", 0, 10), tr("B", 1, 5), tr("C", 2, 8), tr("D", 5, 9), tr("E", 6, 7)], 2)
    assert [t["coin"] for t in got] == ["A", "B", "D"]

def test_croissance():
    assert L.croissance([], 0.1) is None and L.croissance([-11], 0.1) == float("-inf")
    assert L.croissance([1, -1], 0.1) < 0 < L.croissance([2, -1], 0.1)

# ================================================================ collecte et verdicts de bout en bout
NOW = JOUR / 1000 + 10 * 3600
COINS = ["kPEPE", "DOGE", "WIF", "BTC", "ETH", "HYPE"]

class FakeAPI:
    def __init__(self): self.calls = []
    def __call__(self, body):
        self.calls.append(body); t = body["type"]
        if t == "metaAndAssetCtxs": return [{"universe": [{"name": c} for c in COINS + ["xyz:TSLA"]]}, [{} for _ in range(7)]]
        if t == "candleSnapshot":
            r = body["req"]; step = {"1h": H, "15m": M15}[r["interval"]]; s, e = r["startTime"], r["endTime"]
            ts = list(range((s + step - 1) // step * step, e, step))
            rng = np.random.default_rng(int(hashlib.sha256((r["coin"] + r["interval"]).encode()).hexdigest()[:6], 16))
            x = 100 * np.exp(np.cumsum(rng.normal(0, 0.006, len(ts))))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": a, "o": f"{b:.6f}", "c": f"{c:.6f}", "h": f"{max(b, c) * 1.003:.6f}", "l": f"{min(b, c) * 0.997:.6f}",
                     "v": f"{2e5 / c * (4 if k % 37 == 0 else 1):.4f}"} for k, (a, b, c) in enumerate(zip(ts, o, x))]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        raise ValueError(t)

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KL.main(["--out", d], post=FakeAPI(), clock=now, sleep=sl)

def test_collecte_univers_et_refus_d_ecraser():
    d = tempfile.mkdtemp(); man = collect(d)
    assert man["coins"] == ["kPEPE", "DOGE", "WIF", "BTC", "ETH", "HYPE"] and man["jeu"] == "lab4"
    assert man["debut_15m_ms"] == man["end_ms"] - 5000 * M15 and "candles/kPEPE_15m.json" in man["files"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_verdicts_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VL.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VL.CANDIDATS) and rep["decision"]
    for r in rep["candidats"].values():
        assert r["verdict"].startswith(("PASSE", "NE PASSE PAS")) and "10 %" in r["croissance_ln"]
    md = open(os.path.join(out, "verdicts.md")).read(); assert rep["decision"] in md
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VL.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_decision_choisit_la_meilleure_croissance():
    rows = {"A": {"verdict": "PASSE LA VOIE RAPIDE", "croissance_palier": 0.01}, "B": {"verdict": "PASSE LA VOIE RAPIDE", "croissance_palier": 0.02},
            "C": {"verdict": "NE PASSE PAS : x", "croissance_palier": 0.5}}
    assert VL.decide(rows)[0] == "B"
    assert VL.decide({"C": rows["C"]})[0] is None

def test_attente_du_manifeste():
    d = tempfile.mkdtemp(); now, sl = clk(0)
    try: VL.attendre(d, 300, sleep=sl, clock=now); assert False
    except V.SpecError as e: assert "manifeste absent" in str(e)
    open(os.path.join(d, "manifest.json"), "w").write("{}"); VL.attendre(d, 300, sleep=sl, clock=now)

def test_spec_figee_et_bornes():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab4-furie.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.10 and s["max_positions"] == 2 and s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10}
    bad = dict(s, palier=0.25); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VL.load_spec(p); assert False
    except V.SpecError: pass

def test_source_propre():
    for f in ("strategies_lab4.py", "verdicts_lab4.py", "collecte_lab4.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
        assert "\u2014" not in src
        if f != "collecte_lab4.py": assert "import requests" not in src

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
