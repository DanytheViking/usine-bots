"""Tests hors ligne du paquet 1 de l'usine (simulation, catalogue v1, copieur, collecteurs, verdicts).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_usine.py"""
import os, sys, json, math, tempfile, hashlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np, pandas as pd
from usine import sim, strategies as S, copie as C, collecte as K, verdicts as V

H, H4, DAY = 3_600_000, 4 * 3_600_000, 86_400_000
T0 = 1_790_000_000_000 // H4 * H4

def bars(closes, step=H, t0=T0, spread=0.001, vols=None):
    c = np.asarray(closes, float); o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"ts": t0 + step * np.arange(len(c)), "open": o, "high": np.maximum(o, c) * (1 + spread),
                         "low": np.minimum(o, c) * (1 - spread), "close": c, "vol": vols if vols is not None else np.full(len(c), 100.0)})

def clk(t):
    c = [float(t)]
    return (lambda: c[0]), (lambda s: c.__setitem__(0, c[0] + s))

def no_fund(): return (np.array([], dtype="int64"), np.array([]))

# ================================================================ simulation
def test_entree_bougie_suivante_et_frais():
    df = bars([100] * 20 + [100, 101, 102, 103, 104, 105])
    tr, k = sim.run_position(df, 19, "long", 2.0, "X", "t", H, no_fund(), target_dist=4.0)
    assert tr["entry"] == df.open[20] and tr["fill_ts"] == df.ts[20]              # jamais sur la bougie du signal
    assert tr["issue"] == "CIBLE" and abs(tr["exit"] - 104.0) < 1e-9
    assert abs(tr["fees_R"] - (100 * sim.FEE_TAKER + 104 * sim.FEE_TAKER) / 2.0) < 1e-12
    assert abs(tr["R"] - (2.0 - tr["fees_R"] * 1)) < 1e-9 and tr["signal_ts"] == df.ts[19] + H

def test_stop_avant_cible_meme_bougie_et_glissement():
    df = bars([100] * 21); df.loc[21] = [df.ts[20] + H, 100, 110, 90, 100, 100]
    tr, _ = sim.run_position(df, 20, "long", 5.0, "X", "t", H, no_fund(), target_dist=5.0)
    assert tr["issue"] == "STOP" and abs(tr["exit"] - 95 * (1 - sim.STOP_SLIP)) < 1e-9 and tr["R"] < -1

def test_sortie_signal_a_l_ouverture_suivante():
    df = bars([100, 100, 100, 101, 102, 103, 104])
    tr, k = sim.run_position(df, 0, "short", 50.0, "X", "t", H, no_fund(), exit_fn=lambda k: k == 4)
    assert tr["issue"] == "sortie signal" and tr["exit"] == df.open[5] and k == 4 and tr["exit_ts"] == df.ts[5]

def test_funding_long_paie_si_taux_positif():
    df = bars([100] * 30)
    fund = (np.array([df.ts[5] + 1, df.ts[6] + 1], dtype="int64"), np.array([0.001, 0.001]))
    tr, _ = sim.run_position(df, 2, "long", 5.0, "X", "t", H, fund, max_bars=10)
    sh, _ = sim.run_position(df, 2, "short", 5.0, "X", "t", H, fund, max_bars=10)
    assert tr["funding_R"] < 0 and sh["funding_R"] > 0 and abs(tr["funding_R"] + 0.2 / 5.0) < 1e-9

def test_ouvert_en_fin_de_donnees():
    df = bars([100] * 10)
    tr, k = sim.run_position(df, 3, "long", 50.0, "X", "t", H, no_fund())
    assert tr["issue"] == "ouvert en fin de données" and "R" not in tr

# ================================================================ M1, M2
def trend(n=400, up=True):
    rng = np.random.default_rng(1); x = np.cumsum(rng.normal(0.4 if up else -0.4, 1.0, n)) + 1000
    return bars(x, H4, spread=0.002)

def test_m1_cassure_et_sens():
    up, dn = S.m1_cassure_donchian("U", trend(), no_fund()), S.m1_cassure_donchian("D", trend(up=False), no_fund())
    assert up and dn
    assert sum(t["side"] == "long" for t in up) > sum(t["side"] == "short" for t in up)
    assert sum(t["side"] == "short" for t in dn) > sum(t["side"] == "long" for t in dn)

def test_m1_signal_conforme_a_la_regle():
    df = trend(); hh = df.high.rolling(20).max().shift(1)
    for t in S.m1_cassure_donchian("U", df, no_fund()):
        i = int((t["signal_ts"] - H4 - df.ts[0]) // H4)
        assert (df.close[i] > hh[i]) == (t["side"] == "long")

def test_sans_regard_vers_le_futur():
    """Couper les donnees apres T ne change aucun signal anterieur a T (meme entree, meme sens)."""
    df = trend(600); cut = 450
    full = {(t["signal_ts"], t["side"], t["entry"]) for t in S.m1_cassure_donchian("U", df, no_fund()) if t["signal_ts"] <= df.ts[cut - 1]}
    part = {(t["signal_ts"], t["side"], t["entry"]) for t in S.m1_cassure_donchian("U", df.iloc[:cut].reset_index(drop=True), no_fund())}
    assert full and full <= part
    full2 = {(t["signal_ts"], t["side"]) for t in S.m2_croisement_ema("U", df, no_fund()) if t["signal_ts"] <= df.ts[cut - 1]}
    part2 = {(t["signal_ts"], t["side"]) for t in S.m2_croisement_ema("U", df.iloc[:cut].reset_index(drop=True), no_fund())}
    assert full2 <= part2

def test_m2_croisements():
    x = np.concatenate([np.linspace(100, 60, 300), np.linspace(60, 160, 300), np.linspace(160, 80, 300)])
    tr = S.m2_croisement_ema("X", bars(x, H4, spread=0.0005), no_fund())
    sides = [t["side"] for t in tr]
    assert "long" in sides and "short" in sides
    assert all(t["signal_ts"] >= bars(x, H4).ts[S.M2["lente"]] for t in tr)

# ================================================================ P1, P2
def burst():
    c = np.full(80, 100.0); c[60:] = 106.0; v = np.full(80, 100.0); v[60] = 500.0
    return bars(c, H, vols=v)

def test_p1_volume_et_univers():
    df = burst()
    yes = S.p1_cassure_volume("X", df, no_fund(), lambda c, t: True, 0)
    no = S.p1_cassure_volume("X", df, no_fund(), lambda c, t: False, 0)
    assert len(yes) == 1 and yes[0]["side"] == "long" and yes[0]["signal_ts"] == df.ts[60] + H and no == []
    df2 = df.copy(); df2.loc[60, "vol"] = 150.0
    assert S.p1_cassure_volume("X", df2, no_fund(), lambda c, t: True, 0) == []          # volume insuffisant

def test_p2_top2_positifs_au_dessus_ema_et_4h():
    n = 200; t0 = T0
    mk = lambda slope: bars(100 * np.exp(slope * np.arange(n)), H, t0)
    h1 = {"A": mk(0.004), "B": mk(0.003), "C": mk(0.002), "D": mk(-0.003)}
    tr = S.p2_rotation_momentum(h1, {}, lambda h: ("A", "B", "C", "D"), t0 + 60 * H, t0 + (n - 10) * H)
    assert tr and {t["coin"] for t in tr} == {"A", "B"} and all(t["side"] == "long" for t in tr)
    assert all(t["issue"] in ("temps max", "STOP") for t in tr)
    assert all((t["fill_ts"] % H4) == 0 for t in tr) and all(t["exit_ts"] - t["fill_ts"] <= 4 * H for t in tr)

# ================================================================ copieur
def fill(coin, t, px, sz, side, start, pnl=0.0, crossed=True, fee=0.0):
    return {"coin": coin, "time": t, "px": str(px), "sz": str(sz), "side": side, "startPosition": str(start),
            "closedPnl": str(pnl), "crossed": crossed, "fee": str(fee), "tid": t}

def test_evenements_ouverture_fermeture_retournement():
    fs = [fill("X", 1, 10, 1, "B", 0), fill("X", 2, 11, 1, "B", 1), fill("X", 3, 12, 2, "A", 2), fill("X", 4, 12, 2, "A", 0), fill("X", 5, 9, 4, "B", -2)]
    ev = [(e["type"], e["time"], e.get("side")) for e in C.events(fs)]
    assert ev == [("open", 1, "long"), ("close", 3, None), ("open", 4, "short"), ("close", 5, None), ("open", 5, "long")]

def wallet(t_cut, good_before=True, good_after=True, maker=False, compte=50_000):
    fs = []; t = t_cut - 28 * DAY + H
    for k in range(60):
        pnl = (1 if good_before else -1) * 5.0
        fs.append(fill("BTC", t + k * 10 * H, 100, 1, "B", 0, crossed=not maker)); fs.append(fill("BTC", t + k * 10 * H + H, 101, 1, "A", 1, pnl=pnl, crossed=not maker))
    for k in range(10):
        pnl = (1 if good_after else -1) * 5.0
        fs.append(fill("BTC", t_cut + k * DAY, 100, 1, "B", 0)); fs.append(fill("BTC", t_cut + k * DAY + H, 101, 1, "A", 1, pnl=pnl))
    return {"fills": fs, "compte": compte, "complet": True}

def test_selection_sans_fuite_et_exclusions():
    cut = T0 + 40 * DAY
    W = {"bon": wallet(cut), "chanceux_apres": wallet(cut, good_before=False), "mm": wallet(cut, maker=True),
         "gros": wallet(cut, compte=9e6)}
    kept, why = C.select(W, cut)
    assert kept == ["bon"] and why["chanceux_apres"] == "pas assez de semaines gagnantes"
    assert why["mm"] == "teneur de marche" and why["gros"] == "compte hors bornes"
    W2 = {"bon": wallet(cut, good_after=False)}                                   # l'apres-coupe ne change pas la selection
    assert C.select(W2, cut)[0] == ["bon"]
    late = wallet(cut); early = [f for f in late["fills"] if f["time"] < cut][:30]                 # 15 trades avant la coupe seulement
    extra = [fill("BTC", cut + k * H, 100, 1, "B" if k % 2 == 0 else "A", 0 if k % 2 == 0 else 1, pnl=0 if k % 2 == 0 else 5.0) for k in range(80)]
    W4 = {"tardif": {**late, "fills": early + extra}}
    assert C.select(W4, cut)[1]["tardif"] == "trop peu de trades"                  # les fills apres la coupe ne comptent pas
    W3 = {"court": {**wallet(cut), "complet": False, "fills": [f for f in wallet(cut)["fills"] if f["time"] > cut - 10 * DAY]}}
    assert C.select(W3, cut)[1]["court"] == "historique insuffisant"

def test_copie_retard_sortie_wallet_et_stop_pessimiste():
    n = 300; df = bars(np.full(n, 100.0), H, T0, spread=0.001); h1 = {"BTC": df}
    t_open = T0 + 100 * H + 60_000; t_close = T0 + 105 * H + 60_000
    W = {"w": {"fills": [fill("BTC", t_open, 100, 1, "B", 0), fill("BTC", t_close, 101, 1, "A", 1, pnl=1)], "compte": 5e4, "complet": True}}
    tr = C.copy_trades(W, ["w"], h1, {}, lambda c, t: True, T0, T0 + n * H)
    assert len(tr) == 1 and tr[0]["issue"] == "sortie wallet"
    assert abs(tr[0]["entry"] - 100.1) < 1e-9 and abs(tr[0]["exit"] - 101 * 0.999) < 1e-9
    df2 = df.copy(); df2.loc[100, "low"] = 50.0                                  # creux dans la bougie d'entree : stop (pessimiste)
    tr2 = C.copy_trades(W, ["w"], {"BTC": df2}, {}, lambda c, t: True, T0, T0 + n * H)
    assert tr2[0]["issue"] == "STOP"
    assert C.copy_trades(W, ["w"], h1, {}, lambda c, t: False, T0, T0 + n * H) == []   # hors univers : pas de copie

# ================================================================ decoupe et verdicts
def test_decoupe_sans_chevauchement():
    cut = 1000
    ts = [{"signal_ts": 100, "exit_ts": 900, "issue": "x"}, {"signal_ts": 500, "exit_ts": 1500, "issue": "x"}, {"signal_ts": 1200, "exit_ts": 1300, "issue": "x"}]
    tr, ev, st = V.split(ts, cut)
    assert [t["signal_ts"] for t in tr] == [100] and [t["signal_ts"] for t in ev] == [1200] and len(st) == 1

class FakeAPI:
    def __init__(self, fail_after=None): self.calls, self.fail_after = [], fail_after
    def __call__(self, body):
        if self.fail_after is not None and len(self.calls) >= self.fail_after: raise ConnectionError("coupure")
        self.calls.append(body); t = body["type"]
        if t == "candleSnapshot":
            step = H4; s, e = body["req"]["startTime"], body["req"]["endTime"]
            rng = np.random.default_rng(int(hashlib.sha256(body["req"]["coin"].encode()).hexdigest()[:6], 16))
            ts = list(range(s // step * step, e, step)); x = 1000 + np.cumsum(rng.normal(0.3, 4, len(ts)))
            return [{"t": t_, "o": f"{a:.4f}", "c": f"{b:.4f}", "h": f"{max(a, b) * 1.002:.4f}", "l": f"{min(a, b) * 0.998:.4f}", "v": "10"}
                    for t_, a, b in zip(ts, np.concatenate([[x[0]], x[:-1]]), x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        if t == "userFillsByTime":
            s = body["startTime"]; base = [fill("BTC", s + k * H, 100, 1, "B" if k % 2 == 0 else "A", 0 if k % 2 == 0 else 1) for k in range(30)]
            return [x for x in base if x["time"] >= s]
        raise ValueError(t)

def lb():
    row = lambda a, acct, v: {"ethAddress": a, "accountValue": str(acct), "windowPerformances": [["day", {"vlm": "1"}], ["month", {"vlm": str(v)}]]}
    return {"leaderboardRows": [row("0xAA", 5e4, 9e6), row("0xBB", 2e7, 9e9), row("0xCC", 2e4, 1e8), row("0xDD", 500, 9e9), {"bad": 1}]}

def test_collecte_majeurs_reprise_et_refus():
    d = os.path.join(tempfile.mkdtemp(), "maj")
    api = FakeAPI(fail_after=2); clock, sleep = clk(1_793_404_800)
    try: K.main(["majeurs", "--out", d], post=api, clock=clock, sleep=sleep); assert False
    except ConnectionError: pass
    n_before = len(api.calls); api2 = FakeAPI()
    man = K.main(["majeurs", "--out", d], post=api2, **dict(zip(("clock", "sleep"), clk(1_800_000_000))))
    assert man["end_ms"] == 1_793_404_800_000 // H4 * H4                        # fin figee a la premiere execution
    assert not any(c.get("req", {}).get("coin") == "BTC" and c["type"] == "candleSnapshot" for c in api2.calls)   # deja telecharge
    assert sorted(man["files"]) == sorted([f"candles/{c}_4h.json" for c in K.MAJEURS] + [f"funding/{c}.json" for c in K.MAJEURS])
    try: K.main(["majeurs", "--out", d], post=FakeAPI(), clock=clock, sleep=sleep); assert False
    except SystemExit: pass

def test_collecte_baleines_reservoir_par_volume():
    pool = K.pool_from_leaderboard(lb())
    assert [p["adresse"] for p in pool] == ["0xcc", "0xaa"]                     # bornes de compte, tri par volume
    d = os.path.join(tempfile.mkdtemp(), "bal")
    clock, sleep = clk(1_793_404_800)
    man = K.main(["baleines", "--out", d], post=FakeAPI(), clock=clock, sleep=sleep, get_json=lambda u: lb())
    assert "fills/0xaa.json" in man["files"] and json.load(open(os.path.join(d, "fills/0xaa.json")))["complet"] is True

def test_verdicts_bout_en_bout_registre_et_base():
    d = os.path.join(tempfile.mkdtemp(), "maj")
    clock, sleep = clk(1_793_404_800)
    K.main(["majeurs", "--out", d], post=FakeAPI(), clock=clock, sleep=sleep)
    spec = os.path.join(ROOT, "specs", "USINE-SPEC-v1.json"); out = os.path.join(tempfile.mkdtemp(), "o")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): rep = V.run(spec, out, majeurs=d)
    assert buf.getvalue().splitlines()[0].startswith("sha256 specification : ")
    md = open(os.path.join(out, "verdicts.md")).read()
    assert md.count("| ne_rien_trader |") >= 4 + len([r for r in rep["candidats"].values() if "coupe_utc" in r])
    assert rep["candidats"]["P1_cassure_volume_1h"]["verdict"].startswith("NON EVALUE")
    for name in ("M1_cassure_donchian_4h", "M2_croisement_ema_4h"):
        r = rep["candidats"][name]
        assert r["evaluation_frais_doubles"]["global"]["frais_R"] == round(2 * r["evaluation_frais_base"]["global"]["frais_R"], 4) or \
            abs(r["evaluation_frais_doubles"]["global"]["frais_R"] - 2 * r["evaluation_frais_base"]["global"]["frais_R"]) < 1e-3
    other = json.load(open(spec)); other["criteres"]["pf_min"] = 1.0
    p2 = os.path.join(tempfile.mkdtemp(), "autre.json"); json.dump(other, open(p2, "w"))
    try: V.run(p2, out, majeurs=d); assert False
    except Exception as e: assert "refus" in str(e)
    open(os.path.join(d, "candles", "BTC_4h.json"), "a").write(" ")
    try: V.run(spec, os.path.join(tempfile.mkdtemp(), "o2"), majeurs=d); assert False
    except Exception as e: assert "empreinte" in str(e)

def test_specification_validee():
    p = os.path.join(tempfile.mkdtemp(), "s.json"); s = json.load(open(os.path.join(ROOT, "specs", "USINE-SPEC-v1.json")))
    for k in ("criteres", "prereg_sha256"):
        bad = {x: v for x, v in s.items() if x != k}; json.dump(bad, open(p, "w"))
        try: V.load_spec(p); assert False
        except V.SpecError: pass
    s2 = {**s, "candidats": s["candidats"][:-1]}; json.dump(s2, open(p, "w"))
    try: V.load_spec(p); assert False
    except V.SpecError: pass

def test_spec_pointe_les_documents_figes():
    s = json.load(open(os.path.join(ROOT, "specs", "USINE-SPEC-v1.json")))
    h = lambda f: hashlib.sha256(open(os.path.join(ROOT, "docs", f), "rb").read()).hexdigest()
    assert s["prereg_sha256"] == h("PREREG-usine-catalogue-v1.md") and s["mise_en_oeuvre_sha256"] == h("MISE-EN-OEUVRE-catalogue-v1.md")

def test_parametres_figes_conformes_au_prereg():
    assert S.M1 == {"entree": 20, "sortie": 10, "stop_atr": 2.0} and S.M2 == {"rapide": 50, "lente": 200, "stop_atr": 3.0}
    assert S.P1 == {"canal": 24, "volume_x": 2.0, "stop_atr": 1.5, "cible_atr": 3.0, "duree_max": 24}
    assert S.P2 == {"rendement": 24, "ema": 50, "nb": 2, "stop_atr": 2.0, "duree": 4, "pas_h": 4}
    assert C.C1["fills_min"] == 30 and C.C1["semaines_pos"] == 3 and C.C1["stop_atr"] == 2.0 and C.C1["retard_px"] == 0.001
    assert (sim.FEE_TAKER, sim.FEE_MAKER, sim.STOP_SLIP) == (0.00045, 0.00015, 0.0005)

def test_sources_propres():
    for f in ("sim.py", "strategies.py", "copie.py", "collecte.py", "verdicts.py"):
        src = open(os.path.join(ROOT, "usine", f), encoding="utf-8").read()
        assert "\u2014" not in src
        head = src.split("\n\n")[0] + src
        assert "import requests" not in "\n".join(l for l in src.splitlines() if not l.startswith("    "))   # reseau importe tard seulement

def test_pit_et_copie_bout_en_bout():
    """Jeu au format du 01/11 (faux Hyperliquid de l'extension a), puis P1, P2 et C1 de bout en bout."""
    from tests import fixture_pit as FX
    d = os.path.join(tempfile.mkdtemp(), "pit"); FX.build(d)
    bal = os.path.join(tempfile.mkdtemp(), "bal"); clock, sleep = clk(FX.END / 1000)
    K.main(["baleines", "--out", bal], post=FakeAPI(), clock=clock, sleep=sleep, get_json=lambda u: lb())
    out = os.path.join(tempfile.mkdtemp(), "o")
    rep = V.run(os.path.join(ROOT, "specs", "USINE-SPEC-v1.json"), out, pit=d, baleines=bal)
    for n in ("P1_cassure_volume_1h", "P2_rotation_momentum_4h", "C1_copie_baleines"):
        assert "coupe_utc" in rep["candidats"][n], n
    assert rep["candidats"]["M1_cassure_donchian_4h"]["verdict"].startswith("NON EVALUE")
    assert rep["notes"]["copie"]["wallets_telecharges"] == 2
    p1 = rep["candidats"]["P1_cassure_volume_1h"]
    assert "THIN" not in p1["evaluation_frais_base"]["par_actif"] and "THIN" not in p1["entrainement_frais_base"]["par_actif"]

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
