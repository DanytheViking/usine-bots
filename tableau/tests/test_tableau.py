"""Tests hors ligne du tableau de bord (faux fichiers de bots, faux Hyperliquid, aucun reseau).
    PYTHONPATH=. python3 -B tests/test_tableau.py"""
import os, sys, json, tempfile, importlib, threading, urllib.request, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)

def build():
    d = tempfile.mkdtemp(); m = os.path.join(d, "moonshot"); p = os.path.join(d, "peanut"); u = os.path.join(d, "usine-v2")
    for x in (m, p, u, os.path.join(m, "chercheur")): os.makedirs(x)
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump({"ts": now, "mode": "reel", "note": "entrees permises"}, open(os.path.join(m, "status.json"), "w"))
    json.dump({"positions": {"ETH": {"side": "long"}}, "start_equity": 200.0, "r_ledger": [2.0, -1.0, -1.0],
               "closed": [{"ts": now, "coin": "ETH", "bar_ts": 7, "R": 2.0, "pnl": 4.0, "side": "long", "issue": "sortie signal"},
                          {"ts": now, "coin": "BTC", "bar_ts": 8, "R": -1.0, "pnl": -2.0, "side": "short", "issue": "STOP"}]},
              open(os.path.join(m, "state.json"), "w"))
    with open(os.path.join(m, "journal.jsonl"), "w") as f:
        for r in ({"stage": "fable", "decision": "prendre", "reason": "x", "data": {"coin": "ETH", "bar_ts": 7, "avis": "prendre"}, "ts": now},
                  {"stage": "fable", "decision": "eviter", "reason": "x", "data": {"coin": "BTC", "bar_ts": 8, "avis": "eviter"}, "ts": now},
                  {"stage": "signal", "decision": "long", "reason": "ETH : croisement", "data": {}, "ts": now}):
            f.write(json.dumps(r) + "\n")
        f.write("ligne cassee\n")
    with open(os.path.join(m, "equity.jsonl"), "w") as f:
        for i in range(1000): f.write(json.dumps({"t": 1_800_000_000 + i * 60, "eq": 200 + i * 0.01, "open": 1}) + "\n")
    open(os.path.join(m, "chercheur", "bilan-2026-11-15.md"), "w").write("x")
    json.dump({"ts": "2026-10-31T20:22:00Z", "version": "0.1.3"}, open(os.path.join(p, "status.json"), "w"))
    json.dump({"closed": [{"pnl": -1.0, "issue": "STOP"}, {"pnl": 0.5, "issue": "CIBLE"}, {"pnl": 0.0, "issue": "annulé (non rempli)"}]}, open(os.path.join(p, "state.json"), "w"))
    open(os.path.join(p, "KILL"), "w").write("pause demandee")
    json.dump({"specification": "USINE-SPEC-v2", "candidats": {"M2_etendu": {"verdict": "PAS D'AVANTAGE", "evaluation_frais_doubles": {"global": {"trades": 103, "profit_factor": 1.216, "esperance_R": 0.147}}}}},
              open(os.path.join(u, "verdicts.json"), "w"))
    p2 = os.path.join(d, "peanut2"); os.makedirs(p2)
    json.dump({"ts": now, "mode": "observation"}, open(os.path.join(p2, "status.json"), "w"))
    json.dump({"positions": {}, "start_equity": 74.41, "r_ledger": [-1.0], "closed": [{"ts": now, "coin": "WIF", "R": -1.0, "pnl": -0.74, "side": "long", "issue": "STOP"}]},
              open(os.path.join(p2, "state.json"), "w"))
    open(os.path.join(d, ".env"), "w").write("HL_AGENT_KEY=0x" + "1" * 64)
    os.environ.update(DATA_ROOT=d, MOON_ACCOUNT="0x" + "a" * 40, LABO_ACCOUNT="0x" + "c" * 40)
    from tableau import server as S
    importlib.reload(S)
    return d, S

def fake_post(calls, fail=False):
    def post(body):
        calls.append(body["type"])
        if fail: raise ConnectionError("hors ligne")
        if body["type"] == "allMids": return {"ETH": "3000", "BTC": "90000"}
        if body["type"] == "clearinghouseState":
            pos = [{"position": {"coin": "ETH", "szi": "0.1", "entryPx": "2900", "unrealizedPnl": "10", "liquidationPx": "2000"}},
                   {"position": {"coin": "SOL", "szi": "-1", "entryPx": "150", "unrealizedPnl": "-1", "liquidationPx": None}}] if body["user"].startswith("0xaaa") else []
            return {"marginSummary": {"accountValue": "210.5" if body["user"].startswith("0xaaa") else "74.41"}, "assetPositions": pos}
        return [{"coin": "ETH", "reduceOnly": True, "isTrigger": True, "tpsl": "sl"}] if body["user"].startswith("0xaaa") else []
    return post

def test_api_complete_et_sans_cle():
    d, S = build(); calls = []
    S.EX = S.Exchange(post=fake_post(calls))
    a = S.api(); txt = json.dumps(a, default=str)
    m = a["moonshot"]
    assert m["status"]["mode"] == "reel" and m["age_s"] is not None and m["age_s"] < 60
    assert m["r_cumule"] == 0.0 and m["baisse_R"] == 2.0 and m["pertes_affilee"] == 2 and m["line_stop"] == 100.0
    assert m["fable"]["prendre"] == {"trades": 1, "R_moyen": 2.0} and m["fable"]["eviter"] == {"trades": 1, "R_moyen": -1.0}
    assert len(m["equity"]) <= 401 and m["equity"][-1][1] == 200 + 999 * 0.01
    assert m["chercheur"] == ["bilan-2026-11-15.md"] and 0 < m["prochaine_cloture_s"] <= 4 * 3600
    assert a["peanut"]["kill"] and a["peanut"]["trades"] == 2 and a["peanut"]["pnl"] == -0.5
    assert a["peanut2"]["status"]["mode"] == "observation" and a["peanut2"]["line_stop"] == 37.2 and a["peanut2"]["closed"][0]["coin"] == "WIF"
    assert a["moonshot"]["closed"][0]["coin"] != "WIF"                               # donnees des deux bots bien separees
    assert a["verdicts"][0]["candidat"] == "M2_etendu" and a["verdicts"][0]["trades"] == 103
    c = a["exchange"]["comptes"]
    assert c["Moonshot"]["valeur"] == 210.5 and c["Smart Peanut"]["valeur"] == 74.41
    stops = {q["coin"]: q["stop"] for q in c["Moonshot"]["positions"]}
    assert stops == {"ETH": True, "SOL": False}                                      # position sans stop signalee
    assert "1111111111" not in txt and "aaaaaaaaaaaaaaaa" not in txt                  # ni cle, ni adresse complete

def test_cache_et_erreur_tolerees():
    d, S = build(); calls = []; t = [1000.0]
    ex = S.Exchange(post=fake_post(calls), clock=lambda: t[0])
    ex.get(); n = len(calls); ex.get()
    assert len(calls) == n                                                           # cache 20 s : pas de second appel
    t[0] += 30; ex.post = fake_post(calls, fail=True)
    out = ex.get()
    assert out["erreur"] and out["comptes"]["Moonshot"]["valeur"] == 210.5           # derniere valeur connue conservee

def test_serveur_lecture_seule():
    d, S = build(); S.EX = S.Exchange(post=fake_post([]))
    srv = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Handler); port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "Usine de trading" in page and "setInterval(rafraichir, 15000)" in page
        etat = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/etat").read())
        assert etat["moonshot"]["status"]["mode"] == "reel"
        for path in ("/.env", "/../.env", "/moonshot/state.json"):
            try: urllib.request.urlopen(f"http://127.0.0.1:{port}{path}"); assert False, path
            except urllib.error.HTTPError as e: assert e.code == 404
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/etat", data=b"x", method="POST")
        try: urllib.request.urlopen(req); assert False
        except urllib.error.HTTPError as e: assert e.code in (501, 405)
    finally:
        srv.shutdown()

def test_compose_local_et_lecture_seule():
    y = open(os.path.join(ROOT, "docker-compose.yml")).read()
    assert '"127.0.0.1:8090:8090"' in y and "env_file" not in y and "KEY" not in y
    vols = [l.strip() for l in y.splitlines() if l.strip().startswith("- /")]
    assert vols and all(v.endswith(":ro") for v in vols)

def test_sources_propres():
    for f in ("server.py", "page.html", "telecommande.py"):
        assert "\u2014" not in open(os.path.join(ROOT, "tableau", f), encoding="utf-8").read()

def tc_setup():
    d, S = build(); S.EX = S.Exchange(post=fake_post([]))
    os.environ["TELEGRAM_CHAT_ID"] = "4242"
    from tableau import telecommande as T
    importlib.reload(T); T.S = S
    T.BOTS = {"moonshot": ("Moonshot", S.MOON), "peanut": ("Smart Peanut v2", S.PEANUT2)}
    return d, S, T

def test_telecommande_lecture_et_inconnus_ignores():
    d, S, T = tc_setup(); t = [100.0]; tc = T.Telecommande(lambda x: None, clock=lambda: t[0])
    assert tc.handle(9999, "/kill tous") is None and tc.handle(9999, "/etat") is None    # autre expediteur : ignore
    e = tc.handle(4242, "/etat")
    assert "Moonshot : REEL" in e and "Smart Peanut v2 : OBSERVATION" in e and "210.5" in e
    p = tc.handle(4242, "/positions")
    assert "ETH long" in p and "stop OK" in p and "SOL short" in p and "SANS STOP" in p
    assert "Moonshot" in tc.handle(4242, "/pnl") and "/kill" in tc.handle(4242, "/aide")
    assert "inconnue" in tc.handle(4242, "/acheter BTC")

def test_telecommande_kill_avec_confirmation():
    d, S, T = tc_setup(); t = [100.0]; tc = T.Telecommande(lambda x: None, clock=lambda: t[0])
    k_moon, k_p2 = os.path.join(S.MOON, "KILL"), os.path.join(S.PEANUT2, "KILL")
    assert "Usage" in tc.handle(4242, "/kill apex")
    assert "/confirmer" in tc.handle(4242, "/kill moonshot") and not os.path.exists(k_moon)
    t[0] += 61; assert "delai" in tc.handle(4242, "/confirmer") and not os.path.exists(k_moon)
    tc.handle(4242, "/kill moonshot"); assert "KILL pose : Moonshot" in tc.handle(4242, "/confirmer")
    assert os.path.exists(k_moon) and not os.path.exists(k_p2) and "Telegram" in open(k_moon).read()
    tc.handle(4242, "/kill tous"); tc.handle(4242, "/confirmer")
    assert os.path.exists(k_p2)
    assert "Rien a confirmer" in tc.handle(4242, "/confirmer")                       # pas de double confirmation

def test_telecommande_ne_sait_ni_trader_ni_reprendre():
    src = open(os.path.join(ROOT, "tableau", "telecommande.py")).read()
    for interdit in ("os.remove", "unlink", "exchange", "order", "HL_AGENT_KEY", "/reprendre"):
        assert interdit not in src.split('"""', 2)[2], interdit

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
