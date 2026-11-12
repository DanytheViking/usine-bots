"""Tests hors ligne de Moonshot v2 (faux Hyperliquid, aucun reseau).
    DATA_DIR=<dossier temporaire> PYTHONPATH=.:<usine>:<sp-replay> python3 -B tests/test_moon.py"""
import os, sys, json, tempfile, datetime as dt, importlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp())
import numpy as np, pandas as pd
from moon import config as C, guard as G, signal as SG, broker as B, bot as BOT, fable as F, journal as J
from moon.market import Market

TF = C.TF_MS
NOW0 = 1_793_404_800_000 // TF * TF          # une cloture 4 h

def series(n=1000, cross_at=None, side="long"):
    """Prix en baisse puis en hausse (ou l'inverse) : un croisement EMA 50/200 se produit pres de cross_at."""
    x = np.concatenate([np.linspace(200, 100, n // 2), np.linspace(100, 260, n - n // 2)])
    if side == "short": x = x[::-1].copy() * 0 + np.concatenate([np.linspace(100, 200, n // 2), np.linspace(200, 60, n - n // 2)])
    return x

class FakeInfo:
    def __init__(self, closes, end_ms, equity=100.0, coins=C.COINS):
        self.closes, self.end_ms, self.eq, self.coins = closes, end_ms, equity, coins
        self.pos, self.orders_, self.fills, self.calls, self.lev = {}, {}, [], [], {}
        self.timeout = None
    def meta_and_asset_ctxs(self):
        return [{"universe": [{"name": c, "maxLeverage": 10, "szDecimals": 2} for c in self.coins]},
                [{"markPx": str(self.mid(c)), "funding": "0.00001"} for c in self.coins]]
    def mid(self, c): return float(self.closes.get(c, np.array([100.0]))[-1])
    def candles_snapshot(self, coin, tf, start, end):
        self.calls.append(("candles", coin)); x = self.closes.get(coin)
        if x is None: x = np.full(1000, 100.0)
        n = len(x); ts = self.end_ms - TF * np.arange(n, 0, -1)
        o = np.concatenate([[x[0]], x[:-1]])
        return [{"t": int(t), "o": str(a), "c": str(b), "h": str(max(a, b) * 1.001), "l": str(min(a, b) * 0.999), "v": "1"}
                for t, a, b in zip(ts, o, x)]
    def all_mids(self): return {c: str(self.mid(c)) for c in self.coins}
    def user_state(self, acct):
        return {"marginSummary": {"accountValue": str(self.eq)},
                "assetPositions": [{"position": {"coin": c, "szi": str(v)}} for c, v in self.pos.items()]}
    def frontend_open_orders(self, acct): return [o for os_ in self.orders_.values() for o in os_]
    def post(self, path, body):
        return {"leverage": {"type": "isolated", "value": self.lev.get(body["coin"], 0)}}
    def user_fills_by_time(self, acct, since): return [f for f in self.fills if f["time"] >= since]

class FakeExchange:
    def __init__(self, info, fill=True, lose=False):
        self.i, self.fill, self.lose, self.sent = info, fill, lose, []
    def update_leverage(self, lev, coin, is_cross=False):
        self.i.lev[coin] = lev; return {"status": "ok"}
    def bulk_orders(self, orders, grouping=None):
        self.sent.append((orders, grouping))
        if self.lose: raise TimeoutError("perdu")
        e, sl = orders
        if not self.fill:
            self.i.orders_[e["coin"]] = [{"coin": e["coin"], "oid": 8, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"}]
            return {"status": "ok", "response": {"data": {"statuses": [{"error": "Order could not immediately match"}, {"error": "x"}]}}}
        self.i.pos[e["coin"]] = e["sz"] * (1 if e["is_buy"] else -1)
        self.i.orders_[e["coin"]] = [{"coin": e["coin"], "oid": 7, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"}]
        px = self.i.mid(e["coin"])
        self.i.fills.append({"coin": e["coin"], "time": 10**15, "px": str(px), "closedPnl": "0", "fee": "0.01", "dir": "Open"})
        return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"avgPx": str(px), "totalSz": str(e["sz"])}}, "waitingForTrigger"]}}}
    def market_close(self, coin):
        self.i.pos.pop(coin, None)
        self.i.fills.append({"coin": coin, "time": 10**15 + 1, "px": str(self.i.mid(coin)), "closedPnl": "1.5", "fee": "0.01", "dir": "Close Long"})
    def cancel(self, coin, oid): self.i.orders_.pop(coin, None)

def fresh(mode="observation"):
    d = tempfile.mkdtemp(); os.environ["DATA_DIR"] = d; os.environ["MODE"] = mode
    os.environ["HL_ACCOUNT"] = "0x" + "a" * 40; os.environ["HL_AGENT_KEY"] = "0x" + "1" * 64
    for mod in (C, J, G, B, BOT, F): importlib.reload(mod)
    return d

def cross_series(side="long"):
    """1000 bougies dont la DERNIERE porte un croisement EMA 50/200 du sens demande."""
    base = np.concatenate([np.linspace(200, 100, 700), np.linspace(100, 160, 300)]) if side == "long" else \
        np.concatenate([np.linspace(100, 200, 700), np.linspace(200, 140, 300)])
    df = lambda x: pd.DataFrame({"close": x})
    for k in range(300, 1000):
        x = base[:k]
        f = df(x).close.ewm(span=50, adjust=False).mean().values; s = df(x).close.ewm(span=200, adjust=False).mean().values
        up = f[-1] > s[-1] and f[-2] <= s[-2]; dn = f[-1] < s[-1] and f[-2] >= s[-2]
        if (side == "long" and up) or (side == "short" and dn):
            pad = np.full(1000 - k, x[0]); return np.concatenate([pad, x])
    raise AssertionError("pas de croisement")

def setup(mode, side="long", fill=True, lose=False, equity=100.0, coin="ETH"):
    fresh(mode)
    now_ms = NOW0 + 60_000
    closes = {c: np.full(1000, 100.0) for c in C.COINS}; closes[coin] = cross_series(side)
    info = FakeInfo(closes, NOW0, equity)
    ex = FakeExchange(info, fill, lose) if mode == "reel" else None
    m, s, b = BOT.build(info, ex)
    return m, s, b, info, ex, dt.datetime.fromtimestamp(now_ms / 1000, dt.timezone.utc)

# ================================================================ signal
def test_signal_identique_au_testeur():
    sys.path.insert(0, os.environ.get("USINE_DIR", "/root/usine"))
    from usine import strategies as US
    x = np.concatenate([np.linspace(200, 100, 600), np.linspace(100, 220, 500), np.linspace(220, 120, 500)])
    o = np.concatenate([[x[0]], x[:-1]])
    df = pd.DataFrame({"ts": NOW0 - TF * np.arange(len(x), 0, -1), "open": o, "high": np.maximum(o, x) * 1.001, "low": np.minimum(o, x) * 0.999, "close": x, "vol": 1.0})
    ref = {(t["signal_ts"], t["side"]) for t in US.m2_croisement_ema("X", df, None, TF)}
    mine = set()
    for i in range(C.EMA_SLOW + 2, len(df)):
        ev = SG.evaluate(df.iloc[: i + 1].reset_index(drop=True))
        if ev["cross"]: mine.add((ev["bar_ts"] + TF, ev["cross"]))
    assert ref and ref <= mine                                       # chaque trade du Testeur correspond a un signal du bot

def test_bougie_en_cours_exclue():
    df = pd.DataFrame({"ts": [NOW0 - 2 * TF, NOW0 - TF, NOW0], "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "vol": 1.0})
    assert list(SG.closed(df, NOW0 + 60_000).ts) == [NOW0 - 2 * TF, NOW0 - TF]

# ================================================================ Gardien
def test_taille_risque_1_pourcent_et_minimum():
    fresh()
    ctx = {"sz_dec": 3, "max_lev": 10}
    sz, lev, notional, risk, why = G.size("long", 100.0, 1.0, 1000.0, ctx, {})
    assert not why and abs(risk - 10.0) < 0.01 and abs(sz - 3.333) < 1e-9
    sz, lev, notional, risk, why = G.size("long", 100.0, 0.5, 100.0, ctx, {})   # 1 % = 1 USDC -> 0,66 coin = 66 $
    assert not why and risk <= 1.0 + 1e-9
    sz, lev, notional, risk, why = G.size("long", 100.0, 1.0, 50.0, ctx, {})    # 0,5 USDC de risque -> 16,7 $ : ok
    assert not why
    sz, lev, notional, risk, why = G.size("long", 100.0, 5.0, 50.0, ctx, {})    # stop 15 % : 3,3 $ < minimum -> risque 1,6 USDC > 1,5 %
    assert "minimum" in why and sz == 0
    sz, lev, notional, risk, why = G.size("long", 100.0, 4.0, 100.0, ctx, {})   # stop 12 % : 8,3 $ -> minimum 10,5 $, risque 1,26 % : accepte
    assert not why and abs(notional - 10.5) < 0.01 and 0.01 < risk / 100 <= 0.015

def test_levier_et_marge():
    fresh()
    sz, lev, notional, risk, why = G.size("long", 100.0, 10.0, 1000.0, {"sz_dec": 3, "max_lev": 10}, {})   # stop 30 %
    assert not why and lev >= 1 and G.liq_distance(lev, 10, "long") >= 0.6
    full = {"X": {"notional": 4500.0, "lev": 5}}
    assert "marge" in G.size("long", 100.0, 1.0, 1000.0, {"sz_dec": 3, "max_lev": 10}, full)[4]

def test_arrets_de_ligne():
    fresh(); s = G.load()
    assert G.gate(s, 100.0) == ""
    s["start_equity"] = 100.0
    assert G.gate(s, 50.0).startswith("STOP LIGNE") and G.is_fatal(G.gate(s, 50.0))
    s["r_ledger"] = [-1.0] * 20
    assert "pertes d'affilee" in G.gate(s, 90.0)
    s["r_ledger"] = [5.0] + [-1.0, -1.0, 0.5] * 15
    assert G.drawdown_r(s["r_ledger"]) >= 22 and G.gate(s, 90.0) == ""
    s["r_ledger"] = [5.0] + [-1.0] * 19 + [0.1] + [-1.0] * 12
    assert "baisse" in G.gate(s, 90.0)
    assert (C.RISK_PER_TRADE, C.LINE_STOP, C.STOP_DD_R, C.STOP_LOSS_STREAK, C.MAX_LEVERAGE) == (0.01, 0.5, 30, 20, 5)

def test_bornes_plafonnees():
    os.environ["RISK_PER_TRADE"] = "0.05"; os.environ["LINE_STOP"] = "0.9"; os.environ["MAX_LEVERAGE"] = "20"
    try:
        importlib.reload(C); assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_LEVERAGE) == (0.01, 0.5, 5)
    finally:
        for k in ("RISK_PER_TRADE", "LINE_STOP", "MAX_LEVERAGE"): os.environ.pop(k)
        importlib.reload(C)

# ================================================================ boucle
def test_observation_ouvre_sans_ordre_puis_stop():
    m, s, b, info, ex, now = setup("observation")
    BOT.step(m, s, b, now)
    assert "ETH" in s["positions"] and s["positions"]["ETH"]["side"] == "long" and b.mode == "observation"
    assert set(s["positions"]) == {"ETH"}
    info.closes["ETH"] = np.append(info.closes["ETH"][:-1], 1.0)            # chute : stop virtuel touche
    BOT.step(m, s, b, now + dt.timedelta(minutes=1))
    assert "ETH" not in s["positions"] and s["closed"][-1]["issue"] == "STOP" and s["r_ledger"] == []   # observation : pas dans le registre reel

def test_reel_lot_ioc_et_stop_levier_relu():
    m, s, b, info, ex, now = setup("reel")
    BOT.step(m, s, b, now)
    orders, grouping = ex.sent[0]
    assert grouping == "normalTpsl" and orders[0]["order_type"] == {"limit": {"tif": "Ioc"}} and not orders[0]["reduce_only"]
    assert orders[1]["reduce_only"] and orders[1]["order_type"]["trigger"]["tpsl"] == "sl" and orders[1]["order_type"]["trigger"]["isMarket"]
    assert orders[1]["limit_px"] < orders[0]["limit_px"] and info.lev["ETH"] >= 1
    p = s["positions"]["ETH"]; assert abs(p["risk_usd"] - 1.0) < 0.05 and s["start_equity"] == 100.0

def test_reel_reponse_perdue_kill():
    m, s, b, info, ex, now = setup("reel", lose=True)
    BOT.step(m, s, b, now)
    assert os.path.exists(C.KILL_SWITCH) and "ETH" not in s["positions"]

def test_reel_ioc_non_rempli():
    m, s, b, info, ex, now = setup("reel", fill=False)
    BOT.step(m, s, b, now)
    assert "ETH" not in s["positions"] and not os.path.exists(C.KILL_SWITCH) and info.orders_ == {}

def test_reel_stop_touche_solde_en_R():
    m, s, b, info, ex, now = setup("reel")
    BOT.step(m, s, b, now)
    info.pos.pop("ETH"); info.fills.append({"coin": "ETH", "time": 10**15 + 5, "px": "90", "closedPnl": "-0.98", "fee": "0.01", "dir": "Close Long"})
    BOT.step(m, s, b, now + dt.timedelta(minutes=1))
    c = s["closed"][-1]
    assert c["issue"].startswith("STOP") and abs(c["pnl"] - (-1.0)) < 1e-9 and s["r_ledger"] and s["r_ledger"][-1] < -0.9

def test_reel_croisement_inverse_ferme_et_retourne():
    m, s, b, info, ex, now = setup("reel")
    BOT.step(m, s, b, now)
    info.closes["ETH"] = cross_series("short"); info.end_ms = NOW0 + TF
    BOT.step(m, s, b, now + dt.timedelta(hours=4))
    assert s["closed"][-1]["issue"].startswith("sortie signal") and s["positions"]["ETH"]["side"] == "short"

def test_signal_trop_ancien_non_joue():
    m, s, b, info, ex, now = setup("observation")
    BOT.step(m, s, b, now + dt.timedelta(hours=1))                     # bot demarre 1 h apres la cloture
    assert s["positions"] == {}

def test_bougie_pas_encore_publiee_reessayee():
    m, s, b, info, ex, now = setup("observation")
    info.end_ms = NOW0 - TF                                            # l'API n'a pas encore la derniere bougie
    BOT.step(m, s, b, now)
    assert s.get("bar_done") != NOW0 and s["positions"] == {}
    info.end_ms = NOW0
    BOT.step(m, s, b, now + dt.timedelta(minutes=1))
    assert "ETH" in s["positions"]

def test_gardien_bloque_mais_sorties_permises():
    m, s, b, info, ex, now = setup("observation")
    open(C.KILL_SWITCH, "w").write("test")
    BOT.step(m, s, b, now)
    assert s["positions"] == {}

def test_stop_ligne_pose_le_kill():
    m, s, b, info, ex, now = setup("reel")
    s["start_equity"] = 300.0
    BOT.step(m, s, b, now)
    assert os.path.exists(C.KILL_SWITCH) and s["dead"] and s["positions"] == {}

# ================================================================ Fable
def test_fable_sans_cle_et_sans_influence():
    m, s, b, info, ex, now = setup("reel")
    BOT.step(m, s, b, now)
    assert "ETH" in s["positions"]
    rows = [json.loads(l) for l in open(os.path.join(C.DATA_DIR, "journal.jsonl"))]
    assert any(r["stage"] == "fable" and r["decision"] == "absent" for r in rows)

class Resp:
    def __init__(self, code, text): self.status_code, self._t = code, text
    def json(self): return {"content": [{"type": "text", "text": self._t}]}

def test_fable_avis_enregistre_meme_si_eviter():
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-cle"; os.environ["FABLE_DECIDE"] = "0"
    try:
        m, s, b, info, ex, now = setup("reel")
        calls = []
        def post(url, **k): calls.append(k); return Resp(200, 'Voici : {"avis": "eviter", "confiance": 80, "raison": "faux depart probable"}')
        BOT.step(m, s, b, now, fable_post=post)
        assert "ETH" in s["positions"]                               # l'avis « eviter » ne bloque pas l'ordre
        assert calls[0]["json"]["model"] == C.FABLE_MODEL and calls[0]["headers"]["x-api-key"] == "sk-test-cle"
        rows = [json.loads(l) for l in open(os.path.join(C.DATA_DIR, "journal.jsonl"))]
        assert any(r["stage"] == "fable" and r["decision"] == "eviter" for r in rows)
        assert not any("sk-test-cle" in json.dumps(r) for r in rows)
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); os.environ.pop("FABLE_DECIDE"); importlib.reload(C)

def test_fable_decide():
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-cle"
    try:
        m, s, b, info, ex, now = setup("reel")
        assert C.FABLE_DECIDE
        BOT.step(m, s, b, now, fable_post=lambda url, **k: Resp(200, '{"avis": "eviter", "confiance": 70, "raison": "essoufflement"}'))
        assert "ETH" not in s["positions"] and not ex.sent                         # Fable ecarte : aucun ordre
        rows = [json.loads(l) for l in open(os.path.join(C.DATA_DIR, "journal.jsonl"))]
        r = [x for x in rows if x["stage"] == "signal" and x["decision"] == "ecarte par Fable"][0]
        assert r["data"]["coin"] == "ETH" and r["data"]["bar_ts"] and r["data"]["ref"]   # mesurable plus tard
        m, s, b, info, ex, now = setup("reel")
        BOT.step(m, s, b, now, fable_post=lambda url, **k: Resp(200, '{"avis": "prendre", "confiance": 70, "raison": "ok"}'))
        assert "ETH" in s["positions"]
        m, s, b, info, ex, now = setup("reel")
        BOT.step(m, s, b, now, fable_post=lambda url, **k: Resp(500, "erreur"))
        assert "ETH" in s["positions"]                                             # avis absent : la regle M2 s'applique
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); importlib.reload(C)

def test_fable_plafond_et_erreurs():
    os.environ["ANTHROPIC_API_KEY"] = "k"
    try:
        fresh(); s = G.load()
        assert F.parse("rien") is None and F.parse('{"avis": "peut-etre"}') is None
        assert F.parse('{"avis": "prendre", "confiance": 300}')["confiance"] == 100
        boom = lambda url, **k: (_ for _ in ()).throw(TimeoutError())
        assert "erreur" in F.opinion("x", s, "2026-11-12", post=boom)["absent"]
        s["fable_calls"] = {"2026-11-12": C.FABLE_MAX_CALLS_DAY}
        assert "plafond" in F.opinion("x", s, "2026-11-12", post=boom)["absent"]
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); importlib.reload(C)

# ================================================================ divers
def test_journal_chaine_et_cles_masquees():
    m, s, b, info, ex, now = setup("reel")
    J.record("test", "x", f"cle {C.HL_AGENT_KEY}")
    ok, n, _ = J.verify(); assert ok and n >= 1
    assert C.HL_AGENT_KEY not in open(os.path.join(C.DATA_DIR, "journal.jsonl")).read()

def test_reel_refuse_compte_interdit_et_cle_absente():
    fresh("reel"); os.environ["FORBIDDEN_ACCOUNTS"] = os.environ["HL_ACCOUNT"]
    try:
        try: BOT.build(FakeInfo({}, NOW0), FakeExchange(FakeInfo({}, NOW0))); assert False
        except SystemExit as e: assert "interdit" in str(e)
    finally: os.environ.pop("FORBIDDEN_ACCOUNTS")
    os.environ["HL_AGENT_KEY"] = ""; importlib.reload(C); importlib.reload(BOT)
    try: BOT.build(FakeInfo({}, NOW0)); assert False
    except SystemExit as e: assert "HL_AGENT_KEY" in str(e)

def test_sources_propres():
    for f in sorted(os.listdir(os.path.join(ROOT, "moon"))):
        if f.endswith(".py"):
            src = open(os.path.join(ROOT, "moon", f), encoding="utf-8").read()
            assert "\u2014" not in src, f

def test_actifs_configurables_absents_et_peu_echanges_ignores():
    os.environ["COINS"] = "ETH,FANTOME,MINCE,JEUNE"; os.environ["MIN_DAY_VOLUME_USD"] = "1000000"
    try:
        fresh("observation"); importlib.reload(C); importlib.reload(BOT)
        assert C.COINS == ("ETH", "FANTOME", "MINCE", "JEUNE")
        closes = {"ETH": cross_series("long"), "MINCE": cross_series("long"), "JEUNE": np.full(1000, 100.0)}
        info = FakeInfo(closes, NOW0, 100.0, coins=("ETH", "MINCE", "JEUNE"))
        vol = {"ETH": "5e7", "MINCE": "1e5", "JEUNE": "5e7"}
        base = info.meta_and_asset_ctxs
        def ctxs():
            meta, cx = base()
            for u, x in zip(meta["universe"], cx): x["dayNtlVlm"] = vol[u["name"]]
            return [meta, cx]
        info.meta_and_asset_ctxs = ctxs
        orig = info.candles_snapshot
        def short(coin, tf, s0, e0):
            r = orig(coin, tf, s0, e0); return r[-50:] if coin == "JEUNE" else r
        info.candles_snapshot = short
        m, s, b = BOT.build(info, None)
        now = dt.datetime.fromtimestamp((NOW0 + 60_000) / 1000, dt.timezone.utc)
        BOT.step(m, s, b, now)
        fetched = {c for k, c in info.calls if k == "candles"}
        assert fetched == {"ETH", "JEUNE"} and set(s["positions"]) == {"ETH"}          # FANTOME absent, MINCE trop peu echange
        assert s.get("bar_done") == NOW0                                                # historique court : pas de boucle de nouvel essai
        n = len(info.calls); BOT.step(m, s, b, now + dt.timedelta(minutes=1))
        assert len([c for c in info.calls[n:] if c[0] == "candles"]) == 0
    finally:
        os.environ.pop("COINS"); os.environ.pop("MIN_DAY_VOLUME_USD"); importlib.reload(C); importlib.reload(BOT)

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
