"""Tests hors ligne de la Sentinelle (faux Hyperliquid, faux Telegram).
    PYTHONPATH=. python3 -B tests/test_sentinelle.py"""
import os, sys, json, tempfile, importlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
A, L = "0x" + "a" * 40, "0x" + "c" * 40
os.environ.update(MOON_ACCOUNT=A, LABO_ACCOUNT=L)
from sentinelle import main as M
importlib.reload(M)

class Fake:
    def __init__(self):
        self.lev = {"ETH": 25, "WIF": 10}; self.delist = set(); self.absent = set(); self.funding = {"ETH": 0.00001, "WIF": 0.00001}
        self.pos = {A: [], L: []}; self.stops = {A: [], L: []}; self.fail = False; self.agents = {A: 2_000_000_000_000, L: 2_000_000_000_000}
    def __call__(self, body):
        if self.fail: raise ConnectionError("hors ligne")
        t = body["type"]
        if t == "metaAndAssetCtxs":
            names = [c for c in ("ETH", "WIF", "BTC") if c not in self.absent]
            return [{"universe": [{"name": c, "maxLeverage": self.lev.get(c, 40), "szDecimals": 2, **({"isDelisted": True} if c in self.delist else {})} for c in names]},
                    [{"funding": str(self.funding.get(c, 0))} for c in names]]
        if t == "clearinghouseState": return {"assetPositions": [{"position": {"coin": c, "szi": str(s)}} for c, s in self.pos[body["user"]]]}
        if t == "frontendOpenOrders": return [{"coin": c, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"} for c in self.stops[body["user"]]]
        if t == "extraAgents": return [{"address": "0x1", "validUntil": self.agents[body["user"]]}]

def setup():
    f = Fake(); sent = []; t = [1_794_000_000.0]
    s = M.Sentinelle(post=f, send=sent.append, clock=lambda: t[0], data=tempfile.mkdtemp())
    s.passage(); return s, f, sent, t

def test_premier_passage_silencieux_et_statut():
    s, f, sent, t = setup()
    assert sent == [] and json.load(open(os.path.join(s.data, "status.json")))["api_ok"]

def test_regles_des_actifs():
    s, f, sent, t = setup()
    f.lev["ETH"] = 10; f.delist.add("WIF"); f.absent.add("BTC"); t[0] += 900; s.passage()
    txt = "\n".join(sent)
    assert "ETH : levier maximum 25x -> 10x" in txt and "WIF est DELISTE" in txt and "BTC a disparu" in txt
    n = len(sent); t[0] += 900; s.passage(); assert len(sent) == n                    # pas de repetition
    assert len(open(os.path.join(s.data, "alertes.jsonl")).read().splitlines()) == n

def test_positions_funding_et_stop():
    s, f, sent, t = setup()
    f.pos[A] = [("ETH", 0.1)]; f.stops[A] = []; f.funding["ETH"] = 0.0015; t[0] += 900; s.passage()
    assert any("funding +0.150 %/h contre la position" in m for m in sent) and any("ETH : position SANS STOP" in m for m in sent)
    sent.clear(); f.pos[L] = [("WIF", -100)]; f.stops[L] = ["WIF"]; f.funding["WIF"] = 0.0015; t[0] += 900; s.passage()
    assert not any("WIF" in m for m in sent)                                           # short qui recoit le funding, stop present
    f.funding["WIF"] = -0.002; t[0] += 900; s.passage(); assert any("Smart Peanut WIF : funding" in m for m in sent)

def test_api_injoignable_apres_trois_echecs():
    s, f, sent, t = setup(); f.fail = True
    for _ in range(2): t[0] += 900; s.passage()
    assert sent == []
    t[0] += 900; s.passage(); assert any("injoignable" in m for m in sent)
    assert not json.load(open(os.path.join(s.data, "status.json")))["api_ok"]

def test_cle_d_agent_proche_de_l_expiration():
    s, f, sent, t = setup()
    f.agents[L] = int((t[0] + 10 * 86400) * 1000); t[0] += 7 * 3600; s.passage()
    assert any("Smart Peanut : la cle d'agent expire dans 10 jours" in m for m in sent)
    assert json.load(open(os.path.join(s.data, "status.json")))["cles_jours"]["Moonshot"] > 30

def test_lecture_seule_et_propre():
    src = open(os.path.join(ROOT, "sentinelle", "main.py"), encoding="utf-8").read()
    assert "\u2014" not in src and "exchange" not in src.lower() and "AGENT_KEY" not in src

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]; bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
