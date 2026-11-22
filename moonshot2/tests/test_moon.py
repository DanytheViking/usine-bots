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
    def __init__(self, info, fill=True, lose=False, partiel=None, stop_rejete=False, stop_seul_ko=False):
        self.i, self.fill, self.lose, self.sent = info, fill, lose, []
        self.partiel, self.stop_rejete, self.stop_seul_ko, self.seuls = partiel, stop_rejete, stop_seul_ko, []
    def order(self, coin, is_buy, sz, px, order_type, reduce_only=False):
        self.seuls.append({"coin": coin, "is_buy": is_buy, "sz": sz, "px": px, "order_type": order_type, "reduce_only": reduce_only})
        if self.stop_seul_ko: return {"status": "ok", "response": {"data": {"statuses": [{"error": "Order rejected"}]}}}
        self.i.orders_[coin] = [{"coin": coin, "oid": 9, "reduceOnly": True, "isTrigger": True, "tpsl": "sl", "sz": str(sz)}]
        return {"status": "ok", "response": {"data": {"statuses": ["waitingForTrigger"]}}}
    def update_leverage(self, lev, coin, is_cross=False):
        self.i.lev[coin] = lev; return {"status": "ok"}
    def bulk_orders(self, orders, grouping=None):
        self.sent.append((orders, grouping))
        if self.lose: raise TimeoutError("perdu")
        e, sl = orders
        if not self.fill:
            self.i.orders_[e["coin"]] = [{"coin": e["coin"], "oid": 8, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"}]
            return {"status": "ok", "response": {"data": {"statuses": [{"error": "Order could not immediately match"}, {"error": "x"}]}}}
        rempli = round(e["sz"] * self.partiel, 2) if self.partiel else e["sz"]
        self.i.pos[e["coin"]] = rempli * (1 if e["is_buy"] else -1)
        if not (self.partiel or self.stop_rejete):                                            # partiel : le stop enfant part avec le reliquat
            self.i.orders_[e["coin"]] = [{"coin": e["coin"], "oid": 7, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"}]
        px = self.i.mid(e["coin"])
        self.i.fills.append({"coin": e["coin"], "time": 10**15, "px": str(px), "closedPnl": "0", "fee": "0.01", "dir": "Open"})
        sl_st = {"error": "Trigger order rejected"} if self.stop_rejete else "waitingForTrigger"
        return {"status": "ok", "response": {"data": {"statuses": [{"filled": {"avgPx": str(px), "totalSz": str(rempli)}}, sl_st]}}}
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

def setup(mode, side="long", fill=True, lose=False, equity=100.0, coin="ETH", **ex_opts):
    fresh(mode)
    now_ms = NOW0 + 60_000
    closes = {c: np.full(1000, 100.0) for c in C.COINS}; closes[coin] = cross_series(side)
    info = FakeInfo(closes, NOW0, equity)
    ex = FakeExchange(info, fill, lose, **ex_opts) if mode == "reel" else None
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
    os.environ["RISK_PER_TRADE"] = "0.08"; os.environ["LINE_STOP"] = "0.9"; os.environ["MAX_LEVERAGE"] = "20"
    try:
        importlib.reload(C); assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_LEVERAGE) == (0.05, 0.5, 5)   # Moonshot : 5 % au plus (16/11)
    finally:
        for k in ("RISK_PER_TRADE", "LINE_STOP", "MAX_LEVERAGE"): os.environ.pop(k)
        importlib.reload(C)

def test_lab_en_1h_moonshot_en_4h():
    """Lab : M2 en bougies 1 h (USINE-SPEC-M2H1) ; Moonshot reste en 4 h. Bougies cloturees et contexte de Thales suivent l'unite de temps."""
    old = os.environ.get("BOT_NAME")
    try:
        os.environ["BOT_NAME"] = "smartpeanut2"; importlib.reload(C)
        assert (C.TF, C.TF_MS, C.BARS_JOUR) == ("1h", 3_600_000, 24)
        h = 3_600_000; t0 = 1_793_404_800_000 // h * h
        df = pd.DataFrame({"ts": [t0 - 2 * h, t0 - h, t0], "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "vol": 1.0})
        assert list(SG.closed(df, t0 + 60_000).ts) == [t0 - 2 * h, t0 - h]
        c = pd.DataFrame({"close": np.linspace(100, 200, 800)})
        ev = {"ref": 200.0, "ema_rapide": 190.0, "ema_lente": 180.0, "atr": 2.0}
        txt = F.context_text("BTC", "long", ev, {}, c)
        assert "en 1h" in txt and "ATR 1h" in txt
        assert f"24 h {(200 / c.close.values[-25] - 1) * 100:+.1f} %" in txt
        os.environ["BOT_NAME"] = "moonshot2"; importlib.reload(C)
        assert (C.TF, C.TF_MS, C.BARS_JOUR) == ("4h", 14_400_000, 6)
        assert "en 4h" in F.context_text("BTC", "long", ev, {}, c)
    finally:
        if old is None: os.environ.pop("BOT_NAME", None)
        else: os.environ["BOT_NAME"] = old
        importlib.reload(C)

def test_plafonds_du_lab_palier_1():
    """Etape 2 du Lab (confirmation ecrite de Richard du 16/11/2026) : 10 % pour smartpeanut2, plafonds 20 % et -80 % ; Moonshot reste a 1 %."""
    env = {"RISK_PER_TRADE": "0.10", "LINE_STOP": "0.80", "MAX_RISK_MIN_ORDER": "0.20"}
    old = os.environ.get("BOT_NAME")
    try:
        os.environ.update(env); os.environ["BOT_NAME"] = "smartpeanut2"; importlib.reload(C)
        assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_RISK_MIN_ORDER) == (0.10, 0.80, 0.20)
        os.environ.update({"RISK_PER_TRADE": "0.50", "LINE_STOP": "0.95", "MAX_RISK_MIN_ORDER": "0.60"}); importlib.reload(C)
        assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_RISK_MIN_ORDER) == (0.20, 0.80, 0.20)
        os.environ.update(env); os.environ["BOT_NAME"] = "moonshot2"; importlib.reload(C)
        assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_RISK_MIN_ORDER) == (0.05, 0.50, 0.015)
        for k in env: os.environ.pop(k)
        importlib.reload(C); assert (C.RISK_PER_TRADE, C.LINE_STOP, C.MAX_RISK_MIN_ORDER) == (0.01, 0.50, 0.015)
    finally:
        for k in env: os.environ.pop(k, None)
        if old is None: os.environ.pop("BOT_NAME", None)
        else: os.environ["BOT_NAME"] = old
        importlib.reload(C)

def test_moonshot_5_pourcent_et_garde_fou_10R():
    """Confirmation ecrite de Richard du 16/11/2026 (23 h 08 UTC) : 5 % pour moonshot2, -50 % et garde-fou de 10 R inchanges."""
    old = os.environ.get("BOT_NAME")
    try:
        os.environ["BOT_NAME"] = "moonshot2"; os.environ["RISK_PER_TRADE"] = "0.05"; importlib.reload(C); importlib.reload(G)
        assert (C.RISK_PER_TRADE, C.LINE_STOP, C.STOP_DD_R, C.STOP_LOSS_STREAK, C.GARDE_DD_R, C.GARDE_RISK) == (0.05, 0.50, 30, 20, 10.0, 0.01)
        s = {"r_ledger": [3.0] + [-1.0] * 9}
        assert G.risque_par_trade(s) == 0.05 and not s.get("garde_risque")                  # 9 R de baisse : 5 %
        s["r_ledger"].append(-1.0)
        assert G.risque_par_trade(s) == 0.01 and s["garde_risque"]                          # 10 R : retour a 1 %
        s["r_ledger"] += [4.0] * 5
        s["r_ledger"] = [5.0]; assert G.risque_par_trade(s) == 0.01                            # le drapeau reste leve, meme sans baisse
        ctx = {"sz_dec": 3, "max_lev": 20}
        a = G.taille("long", 100.0, 1.0, 1000.0, ctx, {}); b = G.taille("long", 100.0, 1.0, 1000.0, ctx, {}, risque=0.01)
        assert abs(a["risk_target"] - 50.0) < 1e-9 and abs(b["risk_target"] - 10.0) < 1e-9
        assert abs(G.taille("long", 100.0, 1.0, 1000.0, ctx, {}, risque=0.30)["risk_target"] - 50.0) < 1e-9   # jamais au-dela du plafond
        os.environ["BOT_NAME"] = "smartpeanut2"; os.environ["RISK_PER_TRADE"] = "0.10"; importlib.reload(C)
        s = {"r_ledger": [-1.0] * 12}; assert G.risque_par_trade(s) == 0.10                 # le Lab garde ses propres regles
    finally:
        os.environ.pop("RISK_PER_TRADE", None)
        if old is None: os.environ.pop("BOT_NAME", None)
        else: os.environ["BOT_NAME"] = old
        importlib.reload(C); importlib.reload(G)

def test_reel_garde_fou_ramene_l_ordre_a_1_pourcent():
    os.environ["RISK_PER_TRADE"] = "0.05"
    try:
        m, s, b, info, ex, now = setup("reel")
        s["r_ledger"] = [2.0] + [-1.0] * 10                                                   # 10 R de baisse depuis le sommet
        BOT.step(m, s, b, now)
        assert C.RISK_PER_TRADE == 0.05 and s["garde_risque"] and abs(s["positions"]["ETH"]["risk_usd"] - 1.0) < 0.05
        m, s, b, info, ex, now = setup("reel")
        BOT.step(m, s, b, now)
        assert not s.get("garde_risque") and abs(s["positions"]["ETH"]["risk_usd"] - 5.0) < 0.1  # sans baisse : 5 % de 100 USDC
    finally:
        os.environ.pop("RISK_PER_TRADE", None); fresh("observation")

def test_env_moonshot2_5_pourcent():
    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(racine, "deploy", "env", "moonshot2.json")
    if os.path.exists(p): assert json.load(open(p)) == {"RISK_PER_TRADE": "0.05"}

def test_env_peanut2_m2_1h_2_pourcent():
    """Choix de Richard du 18/11/2026 : M2 en 1 h a 2 % sur les 13 actifs de Moonshot, filtre de volume a 2 M$."""
    racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    p = os.path.join(racine, "deploy", "env", "peanut2.json")
    if os.path.exists(p):
        assert json.load(open(p)) == {"RISK_PER_TRADE": "0.02", "LINE_STOP": "0.80", "MAX_RISK_MIN_ORDER": "0.20",
                                      "COINS": ",".join(C.COINS_DEFAUT), "MIN_DAY_VOLUME_USD": "2000000"}

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

def test_reel_remplissage_partiel_stop_seul_a_la_taille_reelle():
    """P0b : IOC rempli a 40 %, stop du lot annule avec le reliquat -> stop seul reduce-only a la taille reelle, position gardee."""
    m, s, b, info, ex, now = setup("reel", partiel=0.4)
    BOT.step(m, s, b, now)
    demande = ex.sent[0][0][0]["sz"]; p = s["positions"]["ETH"]
    assert len(ex.seuls) == 1 and ex.seuls[0]["reduce_only"] and ex.seuls[0]["order_type"]["trigger"]["tpsl"] == "sl"
    assert ex.seuls[0]["sz"] == p["sz"] == abs(info.pos["ETH"]) < demande and not ex.seuls[0]["is_buy"]
    assert ex.seuls[0]["px"] == ex.sent[0][0][1]["limit_px"] == p["stop"]                       # meme prix de stop, jamais deplace
    assert abs(p["risk_usd"] - 0.4 * 1.0) < 0.05 and not os.path.exists(C.KILL_SWITCH)           # risque reel au prorata

def test_reel_stop_du_lot_rejete_stop_seul():
    m, s, b, info, ex, now = setup("reel", stop_rejete=True)
    BOT.step(m, s, b, now)
    assert "ETH" in s["positions"] and len(ex.seuls) == 1 and ex.seuls[0]["sz"] == s["positions"]["ETH"]["sz"]
    assert any(B.is_stop(o) for o in info.orders_["ETH"])

def test_reel_stop_seul_refuse_sortie_sure():
    m, s, b, info, ex, now = setup("reel", partiel=0.4, stop_seul_ko=True)
    BOT.step(m, s, b, now)
    assert len(ex.seuls) == 2 and "ETH" not in info.pos and "ETH" not in s["positions"]           # deux essais puis position fermee

def test_reel_ancien_stop_annule_avant_l_entree():
    """P0b, ancien stop present : il est annule avant le lot et ne peut pas passer pour le stop du nouveau trade."""
    m, s, b, info, ex, now = setup("reel")
    info.orders_["ETH"] = [{"coin": "ETH", "oid": 3, "reduceOnly": True, "isTrigger": True, "tpsl": "sl", "triggerPx": "1.0"}]
    BOT.step(m, s, b, now)
    assert "ETH" in s["positions"] and all(o["oid"] != 3 for o in info.orders_["ETH"])

def test_reel_ancien_stop_ne_vaut_pas_stop_du_trade():
    assert not B.stop_du_trade({"reduceOnly": True, "isTrigger": True, "tpsl": "sl", "triggerPx": "1.0"}, 90.0)
    assert B.stop_du_trade({"reduceOnly": True, "isTrigger": True, "tpsl": "sl", "triggerPx": "90.0"}, 90.0)
    assert not B.stop_du_trade({"reduceOnly": False, "isTrigger": True, "tpsl": "sl", "triggerPx": "90.0"}, 90.0)

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

# ================================================================ Lab v5 : entree en tendance (choix ecrit de Richard du 22/11/2026)
def tendance(m, s, b, info):
    C.ENTREE_TENDANCE = True; C.COINS = ("ETH", "BTC")
    info.closes["BTC"] = np.linspace(200, 100, 1000)                         # baisse continue : tendance short, aucun croisement

def test_tendance_reservee_au_lab():
    fresh("observation"); assert C.NAME == "moonshot2" and not C.ENTREE_TENDANCE
    old = os.environ.get("BOT_NAME")
    try:
        os.environ["BOT_NAME"] = "smartpeanut2"; importlib.reload(C); assert C.ENTREE_TENDANCE and C.VERSION == "2.7.0"
    finally:
        if old is None: os.environ.pop("BOT_NAME", None)
        else: os.environ["BOT_NAME"] = old
        importlib.reload(C)

def test_tendance_entre_sans_croisement_puis_reentre_apres_stop():
    m, s, b, info, ex, now = setup("reel"); tendance(m, s, b, info)
    BOT.step(m, s, b, now)
    assert s["positions"]["BTC"]["side"] == "short" and s["positions"]["ETH"]["side"] == "long" and len(ex.sent) == 2
    assert s["positions"]["BTC"]["stop"] > s["positions"]["BTC"]["entry"]                   # stop au-dessus pour un short
    rows = [json.loads(l) for l in open(J.PATH)]
    assert any(r["stage"] == "signal" and r["decision"] == "tendance short" for r in rows)
    info.end_ms = NOW0 + TF; BOT.step(m, s, b, now + dt.timedelta(hours=4))
    assert len(ex.sent) == 2                                                                 # deja en position : rien de plus
    info.pos.pop("BTC"); info.orders_.pop("BTC", None)
    info.fills.append({"coin": "BTC", "time": 10**15 + 5, "px": "110", "closedPnl": "-1", "fee": "0.01", "dir": "Close Short"})
    BOT.step(m, s, b, now + dt.timedelta(hours=4, minutes=1))
    assert "BTC" not in s["positions"] and "BTC" not in s["tendance_tentee"]
    info.end_ms = NOW0 + 2 * TF; BOT.step(m, s, b, now + dt.timedelta(hours=8))
    assert s["positions"]["BTC"]["side"] == "short" and len(ex.sent) == 3                    # tendance rejointe a la cloture suivante

def test_tendance_un_seul_avis_de_thales_par_tendance():
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-cle"
    try:
        m, s, b, info, ex, now = setup("reel"); tendance(m, s, b, info); appels = []
        def post(url, **k):
            appels.append(k["json"]["messages"][0]["content"]); return Resp(200, '{"avis": "eviter", "confiance": 70, "raison": "rebond"}')
        BOT.step(m, s, b, now, fable_post=post)
        assert "BTC" not in s["positions"] and sum("BTC" in a for a in appels) == 1
        assert any("sans croisement" in a for a in appels if "BTC" in a)
        info.end_ms = NOW0 + TF; BOT.step(m, s, b, now + dt.timedelta(hours=4), fable_post=post)
        assert sum("BTC" in a for a in appels) == 1 and not ex.sent                           # meme tendance : pas de nouvel appel
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); importlib.reload(C)

def plafond_lab(m, s, b, info, coins):
    C.ENTREE_TENDANCE = True; C.MAX_POSITIONS = 2; C.COINS = coins
    for c in coins: info.closes[c] = np.linspace(200, 100, 1000)                # toutes en tendance short, aucun croisement

def test_plafond_deux_positions_puis_place_liberee():
    m, s, b, info, ex, now = setup("reel"); coins = tuple(C.COINS_DEFAUT)
    info.coins = coins; plafond_lab(m, s, b, info, coins)
    BOT.step(m, s, b, now)
    assert len(ex.sent) == 2 and list(s["positions"]) == list(coins[:2])                 # priorite : ordre de COINS
    assert all(c not in s["tendance_tentee"] for c in coins[2:])                         # refus du plafond : tendance non marquee
    info.end_ms = NOW0 + TF; BOT.step(m, s, b, now + dt.timedelta(hours=4))
    assert len(ex.sent) == 2
    c0 = coins[0]; info.pos.pop(c0); info.orders_.pop(c0, None)
    info.fills.append({"coin": c0, "time": 10**15 + 5, "px": "110", "closedPnl": "-1", "fee": "0.01", "dir": "Close Short"})
    BOT.step(m, s, b, now + dt.timedelta(hours=4, minutes=1))
    info.end_ms = NOW0 + 2 * TF; BOT.step(m, s, b, now + dt.timedelta(hours=8))
    assert len(ex.sent) == 3 and len(s["positions"]) == 2 and c0 in s["positions"]       # une place liberee : une seule nouvelle entree

def test_plafond_aussi_sur_les_croisements():
    m, s, b, info, ex, now = setup("reel"); C.MAX_POSITIONS = 0
    BOT.step(m, s, b, now)
    assert s["positions"] == {} and not ex.sent
    assert {r["coin"]: r["code"] for r in parcours()}["ETH"] == "POSITION_LIMIT"

def test_moonshot_sans_plafond_de_deux():
    fresh("observation"); assert C.NAME == "moonshot2" and C.MAX_POSITIONS == len(C.COINS)
    old = os.environ.get("BOT_NAME")
    try:
        os.environ["BOT_NAME"] = "smartpeanut2"; importlib.reload(C); assert C.MAX_POSITIONS == 2
    finally:
        if old is None: os.environ.pop("BOT_NAME", None)
        else: os.environ["BOT_NAME"] = old
        importlib.reload(C)

def test_tendance_bloquee_par_le_gardien():
    m, s, b, info, ex, now = setup("observation"); tendance(m, s, b, info)
    open(C.KILL_SWITCH, "w").write("test"); BOT.step(m, s, b, now)
    assert s["positions"] == {} and not s.get("tendance_tentee")

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

def test_thales_fable_d_abord_puis_secours():
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-cle"; importlib.reload(C)
    try:
        vus = []
        def ok(url, **k): vus.append(k["json"]["model"]); return Resp(200, '{"avis": "prendre", "confiance": 70, "raison": "tendance"}')
        op = F.opinion("p", {"fable_calls": {}}, "d", post=ok)
        assert vus == [C.FABLE_MODEL] and op["modele"] == C.FABLE_MODEL and op["avis"] == "prendre"   # Fable de preference
        vus.clear()
        def surcharge(url, **k):
            vus.append(k["json"]["model"])
            return Resp(529, "") if k["json"]["model"] == C.FABLE_MODEL else Resp(200, '{"avis": "eviter", "confiance": 60, "raison": "x"}')
        s = {"fable_calls": {}}
        op = F.opinion("p", s, "d", post=surcharge)
        assert vus == [C.FABLE_MODEL, C.THALES_SECOURS] and op["modele"] == C.THALES_SECOURS and op["avis"] == "eviter"
        assert s["fable_calls"]["d"] == 1                                   # un seul appel compte par signal
        def panne(url, **k): return Resp(503, "")
        assert F.opinion("p", {"fable_calls": {}}, "d", post=panne)["absent"] == "API 503 puis API 503"
        os.environ["THALES_SECOURS"] = ""; importlib.reload(C); vus.clear()
        assert "absent" in F.opinion("p", {"fable_calls": {}}, "d", post=surcharge) and vus == [C.FABLE_MODEL]   # sans secours
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); os.environ.pop("THALES_SECOURS", None); importlib.reload(C)

def test_fable_reponses_tolerees():
    from moon import fable as F
    assert F.parse('{"avis": "\u00e9viter", "confiance": 70, "raison": "x"}')["avis"] == "eviter"           # accent
    assert F.parse('```json\n{"avis":"prendre","confiance":"80"}\n```') == {"avis": "prendre", "confiance": 80, "raison": ""}
    assert F.parse('Analyse du contexte. {"avis": "Prendre", "raison": "ok"} Fin.')["avis"] == "prendre"
    assert F.parse('{"note": 1} puis {"avis": "eviter"}')["avis"] == "eviter"
    assert F.parse("rien de lisible") is None and F.parse('{"avis": "peut-etre"}') is None
    old = F.C.ANTHROPIC_API_KEY; F.C.ANTHROPIC_API_KEY = "sk-test"
    try: r = F.opinion("p", {"fable_calls": {}}, "d", post=lambda url, **k: Resp(200, "pas de json ici"))
    finally: F.C.ANTHROPIC_API_KEY = old
    assert r == {"absent": "reponse illisible", "apercu": "pas de json ici", "modele": C.FABLE_MODEL} and len(F.apercu("x " * 500)) == 160

def test_fable_decide():
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-cle"
    try:
        m, s, b, info, ex, now = setup("reel")
        assert C.FABLE_DECIDE
        BOT.step(m, s, b, now, fable_post=lambda url, **k: Resp(200, '{"avis": "eviter", "confiance": 70, "raison": "essoufflement"}'))
        assert "ETH" not in s["positions"] and not ex.sent                         # Fable ecarte : aucun ordre
        rows = [json.loads(l) for l in open(os.path.join(C.DATA_DIR, "journal.jsonl"))]
        r = [x for x in rows if x["stage"] == "signal" and x["decision"] == "ecarte par Thales"][0]
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
        codes = {r["coin"]: r["code"] for r in parcours()}
        assert codes == {"ETH": "EXECUTED", "FANTOME": "META_ABSENT", "MINCE": "VOLUME_FILTER", "JEUNE": "SHORT_HISTORY"}
        assert len(parcours()) == 4                                                       # une ligne par actif et par cloture, pas de doublon
        vol["ETH"] = "1e5"; m._ctx_t = 0; info.closes["ETH"] = cross_series("short"); info.end_ms = NOW0 + TF   # ETH sort du filtre mais porte une position
        BOT.step(m, s, b, now + dt.timedelta(hours=4))
        assert "ETH" not in s["positions"] and s["closed"][-1]["issue"].startswith("sortie signal")   # suivi jusqu'a la sortie, sans retournement
        assert [r["code"] for r in parcours() if r["coin"] == "ETH"][1:] == ["EXIT", "VOLUME_FILTER"]
    finally:
        os.environ.pop("COINS"); os.environ.pop("MIN_DAY_VOLUME_USD"); importlib.reload(C); importlib.reload(BOT)

def parcours():
    return [json.loads(l) for l in open(J.PARCOURS, encoding="utf-8")] if os.path.exists(J.PARCOURS) else []

def lab(risque=0.20):
    """Bornes du Lab Smart Peanut (20 % par trade, 20 % au minimum d'ordre), posees sur le module charge : config.py reste a 1 %."""
    fresh(); C.RISK_PER_TRADE = risque; C.MAX_RISK_MIN_ORDER = 0.20
    return {"sz_dec": 0, "max_lev": 5}

def test_lab_garde_de_marge_reduit_sans_bouger_le_stop():
    ctx = lab(); eq = 74.41
    t = G.taille("long", 1.0, 0.05 / 3, eq, ctx, {})                       # stop 5 % : 297 $ au levier 5, marge 59,4 $ < 66,97 $
    assert t["code"] == "" and t["sz"] == 297 and t["lev"] == 5 and abs(t["risk"] - 14.85) < 1e-6 and abs(t["marge"] - 59.4) < 1e-6
    assert abs(t["risk_target"] - 14.882) < 1e-3 and abs(t["dist_stop"] - 0.05) < 1e-6 and t["dist_liq"] >= 2 * 0.05
    t = G.taille("long", 1.0, 0.03 / 3, eq, ctx, {})                       # stop 3 % : 496 $ demandes, la marge plafonne a 334 $
    assert t["code"] == "MARGIN" and t["sz"] == 334 and t["lev"] == 5 and abs(t["risk"] - 10.02) < 1e-6 and t["marge"] <= eq * 0.90
    assert t["why"] == "" and abs(t["dist_stop"] - 0.03) < 1e-6                    # le stop reste a 3 %, seule la taille baisse
    sz, lev, notional, risk, why = G.size("long", 1.0, 0.03 / 3, eq, ctx, {})
    assert (sz, lev, risk, why) == (334, 5, t["risk"], "")

def test_lab_deux_positions_et_risque_ouvert_40_pourcent():
    ctx = lab(); eq = 74.41
    p1 = {"A": {"notional": 297.0, "lev": 5, "risk_usd": 14.85}}             # premiere position a 20 %, stop 5 %
    t = G.taille("long", 1.0, 0.05 / 3, eq, ctx, p1)                        # seconde : 7,57 $ de marge libre -> 37 $ seulement
    assert t["code"] == "MARGIN" and t["sz"] == 37 and abs(t["risk"] - 1.85) < 1e-6
    ouvert = {c: {"notional": 20.0, "lev": 5, "risk_usd": 7.441} for c in "ABC"}   # 30 % deja ouverts a 10 %, peu de marge
    t = G.taille("long", 1.0, 0.05 / 3, eq, ctx, ouvert)
    assert t["code"] == "RISK_LIMIT" and abs(t["risk"] - (eq * 0.40 - 3 * 7.441)) < 0.06 and t["why"] == ""
    ouvert["D"] = {"notional": 20.0, "lev": 5, "risk_usd": 7.441}
    t = G.taille("long", 1.0, 0.05 / 3, eq, ctx, ouvert)                    # 40 % atteints : refus
    assert t["code"] == "RISK_LIMIT" and t["sz"] == 0 and "plafond 40%" in t["why"]
    t = G.taille("long", 1.0, 0.09 / 3, eq, ctx, {})                       # stop 9 % : levier 3 (liquidation a 25,9 %), 165 $, marge 55 $
    assert t["code"] == "" and t["lev"] == 3 and t["sz"] == 165 and abs(t["marge"] - 55.0) < 1e-6
    t = G.taille("long", 1.0, 0.09 / 3, eq, ctx, {"A": {"notional": 165.0, "lev": 3, "risk_usd": 14.85}})
    assert t["code"] == "MARGIN" and t["sz"] == 35                           # deux pleines positions a 20 % ne tiennent pas dans 90 % de marge
    t = G.taille("short", 1.0, 0.45 / 3, eq, ctx, {})                      # stop 45 % en short : liquidation a 81,8 % au levier 1, moins de 2 fois
    assert t["code"] == "LIQ_GUARD" and t["sz"] == 0 and "liquidation" in t["why"]
    assert G.plafonds()["risque_ouvert_max"] == 0.40 and G.plafonds()["reserve_liquidation"] == 2.0

def test_lab_minimum_d_ordre_20_pourcent():
    ctx = lab(); eq = 74.41
    t = G.taille("long", 100.0, 1.0, eq, ctx, {})                          # stop 3 % sur un actif a 100 $ : 496 $ -> 4 coins, marge ok
    assert t["code"] in ("", "MARGIN") and t["sz"] >= 1
    C.RISK_PER_TRADE = 0.01
    t = G.taille("long", 11.0, 1.0, 20.0, ctx, {})                         # equity 20 $, 1 % vise, stop 27 % : le minimum (1 coin) impose 15 %, accepte au Lab
    assert t["code"] == "" and t["sz"] == 1 and abs(t["risk"] / 20.0 - 0.15) < 1e-9
    C.MAX_RISK_MIN_ORDER = 0.015
    t = G.taille("long", 11.0, 1.0, 20.0, ctx, {})                         # a 1,5 % le meme minimum est refuse
    assert t["code"] == "MIN_ORDER" and t["sz"] == 0 and "minimum" in t["why"]

def test_parcours_codes_et_bilan():
    m, s, b, info, ex, now = setup("reel")
    BOT.step(m, s, b, now)
    codes = {r["coin"]: r["code"] for r in parcours()}
    assert codes["ETH"] == "EXECUTED" and set(codes.values()) == {"EXECUTED", "NO_SIGNAL"} and len(codes) == len(C.COINS)
    e = next(r for r in parcours() if r["code"] == "EXECUTED")
    assert e["risk_target"] == 1.0 and e["risk"] <= 1.0 and e["risk_frais"] > e["risk"] and e["plafonds"]["risque_par_trade"] == 0.01
    assert e["sz_brut"] >= e["sz"] and e["marge"] > 0 and e["ema_rapide"] and e["ema_lente"] and e["sz_rempli"] == e["sz"]
    bilan = J.bilan_parcours()
    assert bilan["signaux"] == 1 and bilan["ordres"] == 1 and bilan["executions"] == 1 and bilan["exclusions"] == 0
    assert bilan["codes"]["NO_SIGNAL"] == len(C.COINS) - 1
    assert any(r["stage"] == "risque" and r["data"].get("risk_target") == 1.0 for r in map(json.loads, open(J.PATH)))
    m, s, b, info, ex, now = setup("reel", fill=False)
    BOT.step(m, s, b, now)
    assert {r["coin"]: r["code"] for r in parcours()}["ETH"] == "NOT_FILLED"
    m, s, b, info, ex, now = setup("reel", lose=True)
    BOT.step(m, s, b, now)
    assert {r["coin"]: r["code"] for r in parcours()}["ETH"] == "ORDER_REJECTED"
    m, s, b, info, ex, now = setup("observation")
    open(C.KILL_SWITCH, "w").write("test"); BOT.step(m, s, b, now)
    assert {r["coin"]: r["code"] for r in parcours()}["ETH"] == "BLOCKED"
    m, s, b, info, ex, now = setup("observation")
    BOT.step(m, s, b, now + dt.timedelta(hours=1))
    assert {r["coin"]: r["code"] for r in parcours()}["ETH"] == "STALE_SIGNAL"
    m, s, b, info, ex, now = setup("observation")
    info.end_ms = NOW0 - TF
    BOT.step(m, s, b, now); BOT.step(m, s, b, now + dt.timedelta(minutes=2))
    assert parcours() == []                                                 # bougie en retard de 2 min : on attend sans rien ecrire
    BOT.step(m, s, b, now + dt.timedelta(minutes=6)); BOT.step(m, s, b, now + dt.timedelta(minutes=7))
    assert [r["code"] for r in parcours()].count("STALE_DATA") == len(C.COINS)   # 6 min de retard : une ligne par actif, une seule
    info.end_ms = NOW0; BOT.step(m, s, b, now + dt.timedelta(minutes=8))
    assert {r["coin"]: r["code"] for r in parcours() if r["code"] != "STALE_DATA"}["ETH"] == "EXECUTED"
    try: J.trace("INCONNU", "ETH", 0); assert False
    except AssertionError: pass

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
