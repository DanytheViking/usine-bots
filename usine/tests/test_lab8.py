"""Tests hors ligne du Lab v8 (Tendance 4 h confirmee).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab8.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_tendance_4h as VT4, collecte_t4h as KT, strategies as S
from tests.test_usine import clk, bars, no_fund
from tests.test_v2 import FakeAPI2, NOW

H, H4 = 3_600_000, 4 * 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB8.json")

def serie(c, vol=1e6):
    df = bars(np.asarray(c, float), step=H4); df.loc[:, "vol"] = vol / df.close; return df

def baisse(n=600): return 100 * np.exp(-0.002 * np.arange(n))

def test_entre_dans_la_tendance_sans_croisement():
    df = serie(baisse())
    assert S.m2_croisement_ema("X", df, no_fund()) == []
    t = VT4.tendance("X", df, no_fund())
    assert t and t[0]["side"] == "short" and t[0]["strat"] == "T4H_confirmee" and t[0]["signal_ts"] == df.ts.values[S.M2["lente"]] + H4

def test_pas_d_entree_du_mauvais_cote_de_l_ema50():
    c = baisse(); c[300:306] = c[299] * 1.3                                       # rebond au-dessus de l'EMA 50 : le stop saute, puis attente
    df = serie(c); em = df.close.ewm(span=50, adjust=False).mean().values; ts = df.ts.values
    conf = VT4.tendance("X", df, no_fund()); libre = VT4.tendance("X", df, no_fund(), confirme=False)
    assert conf[0]["issue"] == "STOP"
    for x in conf:
        i = int(np.searchsorted(ts, x["signal_ts"] - H4))
        assert c[i] < em[i]                                                     # chaque short est pris sous l'EMA 50
    pendant = lambda xs: [x for x in xs if ts[300] < x["fill_ts"] <= ts[306]]
    assert pendant(libre) and not pendant(conf)                                 # sans confirmation on rentre dans le rebond, avec confirmation non
    assert any(x["fill_ts"] > ts[306] for x in conf)                            # et on revient quand le prix repasse sous l'EMA 50

def test_retournement_au_croisement():
    c = np.concatenate([100 * np.exp(-0.002 * np.arange(500)), 100 * np.exp(-1.0) * np.exp(0.004 * np.arange(1, 400))])
    t = VT4.tendance("X", serie(c), no_fund())
    s = [x for x in t if x["issue"] == "sortie signal"]
    assert s and any(x["side"] == "long" and x["fill_ts"] == s[0]["exit_ts"] for x in t)

def test_filtre_de_volume_sur_24_h():
    assert VT4.tendance("X", serie(baisse(), vol=2e5), no_fund()) == []           # 6 x 200 000 $ = 1,2 M$ < 2 M$
    assert VT4.tendance("X", serie(baisse(), vol=4e5), no_fund())                 # 2,4 M$

def test_temoin_identique_a_m2():
    c = np.concatenate([np.linspace(200, 100, 600), np.linspace(100, 220, 500), np.linspace(220, 120, 500)])
    df = serie(c); a = VT4.croisement("X", df, no_fund()); b = S.m2_croisement_ema("X", df, no_fund())
    assert a and [(x["signal_ts"], x["side"], x.get("R")) for x in a] == [(x["signal_ts"], x["side"], x.get("R")) for x in b]
    assert all(x["strat"] == "M2_4h_croisement" for x in a)

def test_regle_de_decision():
    spec = json.load(open(SPEC))
    def row(v, e, n=60, tr=0.1, s3=0.1):
        return {"verdict": v, "evaluation_frais_doubles": {"esperance_R": e, "trades": n}, "entrainement_frais_doubles": {"esperance_R": tr},
                "esperance_sans_3_meilleurs_R": s3}
    assert VT4.decide(row("PASSE LA VOIE RAPIDE", 0.3), spec).startswith("NIVEAU REEL")
    assert VT4.decide(row("PASSE LA VOIE RAPIDE", 0.3, tr=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VT4.decide(row("PASSE LA VOIE RAPIDE", 0.3, s3=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VT4.decide(row("NE PASSE PAS : x", 0.5, n=12), spec).startswith("NON CONCLUANT")
    assert VT4.decide(row("NE PASSE PAS : x", -0.1), spec).startswith("ESPERANCE NEGATIVE")
    assert VT4.decide(row("NE PASSE PAS : x", 0.05), spec).startswith("NE PASSE PAS")

class Fake(FakeAPI2):
    def __call__(self, body):
        if body["type"] == "metaAndAssetCtxs":
            noms = ["BTC", "ETH", "kPEPE", "XMR", "DOGE", "xyz:TSLA"]
            return [{"universe": [{"name": c} for c in noms]}, [{} for _ in noms]]
        if body["type"] == "candleSnapshot":
            r = body["req"]; assert r["interval"] == "4h"; s, e = r["startTime"], r["endTime"]
            ts = list(range(s // H4 * H4, e, H4)); rng = np.random.default_rng(int(hashlib.sha256(r["coin"].encode()).hexdigest()[:6], 16))
            x = 100 * np.exp(0.6 * np.sin(np.arange(len(ts)) / 250) + np.cumsum(rng.normal(0, 0.008, len(ts))))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": a, "o": f"{b:.6f}", "c": f"{c:.6f}", "h": f"{max(b, c) * 1.003:.6f}", "l": f"{min(b, c) * 0.997:.6f}",
                     "v": f"{1e6 / c:.4f}"} for a, b, c in zip(ts, o, x)]
        return super().__call__(body)

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KT.main(["--out", d], post=Fake(), clock=now, sleep=sl)

def test_collecte_13_actifs_en_4_h():
    d = os.path.join(tempfile.mkdtemp(), "t4h"); man = collect(d)
    assert man["coins"] == ["BTC", "ETH", "kPEPE", "XMR"] and man["jeu"] == "t4h"
    assert man["debut_4h_ms"] == man["end_ms"] - 5000 * H4 and man["end_ms"] % H4 == 0 and "candles/XMR_4h.json" in man["files"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_bout_en_bout_et_registre():
    d = os.path.join(tempfile.mkdtemp(), "t4h"); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VT4.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VT4.CANDIDATS) and rep["decision"]
    assert rep["candidats"]["T4H_confirmee"]["evaluation_sans_plafond_frais_doubles"]["trades"] > 0
    assert all("5 %" in r["croissance_ln"] for r in rep["candidats"].values())
    assert rep["decision"] in open(os.path.join(out, "verdicts.md")).read()
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VT4.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab8-tendance-4h.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.02 and s["max_positions"] == 2 and s["volume_min_usd"] == 2000000
    assert s["decisif"] == "T4H_confirmee" and s["temoin"] == "M2_4h_croisement"
    assert s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10}
    bad = dict(s, max_positions=3); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VT4.load_spec(p); assert False
    except Exception as e: assert "deux positions" in str(e)

def test_source_propre():
    for f in ("verif_tendance_4h.py", "collecte_t4h.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
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
