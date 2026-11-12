"""Tests hors ligne de l'essai d'execution (faux Hyperliquid).
    DATA_DIR=<dossier temporaire> PYTHONPATH=. python3 -B tests/test_essai.py"""
import os, sys, io, json, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from tests import test_moon as T

def go(mode="reel", fill=True, coin="BTC", notionnel=12.0, prep=None):
    T.fresh(mode)
    from moon import essai as E, bot as BOT, config as C, journal as J
    import importlib; importlib.reload(E)
    info = T.FakeInfo({c: np.full(1000, 100.0) for c in C.COINS}, T.NOW0)
    ex = T.FakeExchange(info, fill) if mode == "reel" else None
    m, s, b = BOT.build(info, ex)
    if prep: prep(info, s)
    buf = io.StringIO(); slept = []
    with contextlib.redirect_stdout(buf): rc = E.run(m, s, b, coin, notionnel, sleep=slept.append, now_ms=0)
    return rc, buf.getvalue(), info, ex, C, J, slept

def test_aller_retour_ok():
    rc, out, info, ex, C, J, slept = go()
    assert rc == 0 and "ESSAI EXECUTION OK" in out and slept[:1] == [5]
    orders, grouping = ex.sent[0]
    e, sl = orders
    assert grouping == "normalTpsl" and e["is_buy"] and e["order_type"] == {"limit": {"tif": "Ioc"}} and not e["reduce_only"]
    assert sl["reduce_only"] and sl["order_type"]["trigger"]["tpsl"] == "sl" and abs(sl["limit_px"] - 97.0) < 1e-9
    assert e["sz"] * 100 >= C.MIN_NOTIONAL_USD and e["sz"] * 100 <= 25 and info.lev["BTC"] == 2
    assert not info.pos and not info.orders_ and "cout de l'essai" in out
    recs = [json.loads(l) for l in open(J.PATH)]
    last = [r for r in recs if r["stage"] == "essai"][-1]
    assert last["decision"] == "resultat" and last["reason"] == "ESSAI EXECUTION OK" and last["data"]["stops"] == 1

def test_refus():
    assert go(mode="observation")[0] == 1
    rc, out, info, ex, *_ = go(prep=lambda i, s: i.pos.update({"ETH": 1.0}))
    assert rc == 1 and "positions ouvertes" in out and not ex.sent
    rc, out, info, ex, *_ = go(prep=lambda i, s: s["positions"].update({"SOL": {}}))
    assert rc == 1 and "le bot suit" in out and not ex.sent
    rc, out, info, ex, *_ = go(notionnel=100)
    assert rc == 1 and not ex.sent
    def kill(i, s):
        from moon import config as C
        open(C.KILL_SWITCH, "w").write("x")
    rc, out, info, ex, *_ = go(prep=kill); assert rc == 1 and not ex.sent and "refus : KILL" in out

def test_taille_minimale_relevee():
    rc, out, info, ex, *_ = go(notionnel=10.5)
    assert rc == 0 and ex.sent[0][0][0]["sz"] == 0.11                                       # 0,10 x 100 = 10 $ < 10,5 $ : releve d'un pas

def test_stop_disparu_apres_entree():
    T.fresh("reel")
    from moon import essai as E, bot as BOT, config as C
    info = T.FakeInfo({c: np.full(1000, 100.0) for c in C.COINS}, T.NOW0); ex = T.FakeExchange(info)
    m, s, b = BOT.build(info, ex); real = b.orders; n = [0]
    def orders(coin):
        n[0] += 1; return [] if n[0] == 3 else real(coin)                                   # 3e lecture : celle de l'essai apres l'entree
    b.orders = orders
    with contextlib.redirect_stdout(io.StringIO()): rc = E.run(m, s, b, "BTC", 12.0, sleep=lambda x: None, now_ms=0)
    assert rc == 1 and not info.pos

def test_ioc_non_rempli():
    rc, out, info, ex, *_ = go(fill=False)
    assert rc == 1 and "non remplie" in out and not info.pos and not info.orders_

def test_stop_absent_echec():
    T.fresh("reel")
    from moon import essai as E, bot as BOT, config as C
    info = T.FakeInfo({c: np.full(1000, 100.0) for c in C.COINS}, T.NOW0); ex = T.FakeExchange(info)
    orig = ex.bulk_orders
    def bulk(orders, grouping=None):
        r = orig(orders, grouping); info.orders_.pop(orders[0]["coin"], None); return r
    ex.bulk_orders = bulk
    m, s, b = BOT.build(info, ex)
    with contextlib.redirect_stdout(io.StringIO()) as buf: rc = E.run(m, s, b, "BTC", 12.0, sleep=lambda x: None, now_ms=0)
    assert rc == 1 and not info.pos                                                           # sortie sure si le stop manque

def test_source_propre():
    src = open(os.path.join(ROOT, "moon", "essai.py"), encoding="utf-8").read()
    assert "\u2014" not in src and "withdraw" not in src.lower() and "usd_transfer" not in src

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]; bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
