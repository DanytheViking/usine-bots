"""Tests hors ligne du Controleur (faux Hyperliquid).
    PYTHONPATH=<sp-replay>:. python3 -B tests/test_controle.py"""
import os, sys, json, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
from usine import controle as K

T0 = 1_794_000_000_000 // (4 * 3_600_000) * (4 * 3_600_000)

def journal(lines):
    p = os.path.join(tempfile.mkdtemp(), "journal.jsonl")
    with open(p, "w") as f:
        for ts, reason in lines: f.write(json.dumps({"ts": ts, "stage": "execution", "decision": "ouvert", "reason": reason}) + "\n")
        f.write("ligne cassee\n")
    return p

def iso(ms): return K.dt.datetime.fromtimestamp(ms / 1000, K.dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-4] + "Z"

def fake(fills, opens, funding=()):
    calls = []
    def post(body):
        calls.append(body["type"])
        if body["type"] == "userFillsByTime": return fills
        if body["type"] == "candleSnapshot": return [{"o": str(opens[body["req"]["coin"]])}]
        if body["type"] == "userFunding": return [{"delta": {"usdc": str(x)}} for x in funding]
    return post, calls

def test_ecart_frais_funding_et_essai_ignore():
    t = T0 + 60_000
    j = journal([(iso(t), "ETH long 0.1 a 3010, stop 2900, risque 2.00 USDC, levier 3")])
    fills = [{"coin": "ETH", "dir": "Open Long", "time": t + 2000, "px": "3010", "sz": "0.06", "fee": "0.0813"},
             {"coin": "ETH", "dir": "Open Long", "time": t + 2500, "px": "3020", "sz": "0.04", "fee": "0.0544"},
             {"coin": "BTC", "dir": "Open Long", "time": t - 9_000_000, "px": "71612", "sz": "0.00016", "fee": "0.005"}]   # essai : ignore
    post, calls = fake(fills, {"ETH": 3000.0}, funding=(-0.12, 0.02))
    b = K.analyser("moonshot2", "0x" + "a" * 40, j, T0 - 86_400_000, T0 + 86_400_000, post)
    assert b["entrees"] == 1 and abs(b["trades"][0]["prix"] - 3014.0) < 1e-9
    assert abs(b["ecart_entree_moyen"] - (3014 / 3000 - 1)) < 1e-12 and abs(b["taux_frais_moyen"] - 0.1357 / 301.4) < 1e-12
    assert abs(b["funding_usdc"] + 0.10) < 1e-9

def test_short_ecart_signe():
    t = T0 + 30_000
    j = journal([(iso(t), "SOL short 1 a 149, stop 160")])
    post, _ = fake([{"coin": "SOL", "dir": "Open Short", "time": t, "px": "149", "sz": "1", "fee": "0.067"}], {"SOL": 150.0})
    b = K.analyser("x", "0x" + "a" * 40, j, 0, T0 + 1, post)
    assert b["ecart_entree_moyen"] > 0                                             # vendre plus bas que l'ouverture : ecart defavorable, positif
    assert abs(b["ecart_entree_moyen"] - (149 / 150 - 1) * -1) < 1e-12

def test_verdicts_et_rapport():
    out = tempfile.mkdtemp(); t = T0 + 60_000
    j = journal([(iso(t), "ETH long 0.1 a 3100, stop 2900")])
    post, _ = fake([{"coin": "ETH", "dir": "Open Long", "time": t, "px": "3030", "sz": "0.1", "fee": "0.136"}], {"ETH": 3000.0})
    rep = K.run([f"moonshot2:0x{'a' * 40}:{j}"], out, poster=post, maintenant_ms=T0 + 86_400_000)
    assert rep["verdict"] == "ECART" and "entree moyenne +1.00 %" in rep["resume"]
    assert json.load(open(os.path.join(out, "controle.json")))["verdict"] == "ECART" and "| moonshot2 | 1 |" in open(os.path.join(out, "controle.md")).read()
    post, calls = fake([], {})
    rep = K.run([f"peanut2:0x{'c' * 40}:{journal([])}"], tempfile.mkdtemp(), poster=post, maintenant_ms=T0)
    assert rep["verdict"] == "AUCUN TRADE" and calls == []                         # aucun appel si aucune entree
    post, _ = fake([{"coin": "ETH", "dir": "Open Long", "time": t, "px": "3003", "sz": "0.1", "fee": "0.135"}], {"ETH": 3000.0})
    assert K.run([f"m:0x{'a' * 40}:{j}"], tempfile.mkdtemp(), poster=post, maintenant_ms=T0 + 86_400_000)["verdict"] == "CONFORME"

def test_source_propre():
    src = open(os.path.join(ROOT, "usine", "controle.py"), encoding="utf-8").read()
    assert "\u2014" not in src and "exchange" not in src.lower().replace("hyperliquid", "")

if __name__ == "__main__":
    import io, contextlib
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]; bad = 0
    for n, f in tests:
        try:
            with contextlib.redirect_stdout(io.StringIO()): f()
            print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
