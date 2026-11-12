"""Tests hors ligne du chien de garde et de Fable Chercheur (aucun reseau).
    PYTHONPATH=. python3 -B tests/test_garde_chercheur.py"""
import os, sys, json, tempfile, importlib, datetime as dt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
os.environ["DATA_DIR"] = tempfile.mkdtemp(); os.environ["HL_ACCOUNT"] = "0x" + "b" * 40
from moon import config as C, garde as GD, chercheur as CH, guard as G, journal as J

def fresh():
    os.environ["DATA_DIR"] = tempfile.mkdtemp()
    for m in (C, J, G, GD, CH): importlib.reload(m)

def write_status(age_s, now):
    ts = dt.datetime.fromtimestamp(now - age_s, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(C.DATA_DIR, exist_ok=True); json.dump({"ts": ts}, open(os.path.join(C.DATA_DIR, "status.json"), "w"))

class Clock:
    def __init__(self, t): self.t = t
    def __call__(self): return self.t

def api(pos=(), stops=()):
    def post(body):
        if body["type"] == "clearinghouseState":
            return {"assetPositions": [{"position": {"coin": c, "szi": "1"}} for c in pos]}
        return [{"coin": c, "reduceOnly": True, "isTrigger": True, "tpsl": "sl"} for c in stops]
    return post

def test_silence_alerte_une_fois_puis_retour():
    fresh(); now = 1_800_000_000.0; sent = []; clk = Clock(now)
    g = GD.Garde(post=api(), send=sent.append, clock=clk)
    write_status(60, now); g.tick(); assert sent == []
    write_status(20 * 60, now); g.tick(); g.tick()
    assert len(sent) == 1 and "signe de vie" in sent[0]
    write_status(30, now); g.tick()
    assert len(sent) == 2 and sent[1].startswith("✅")

def test_status_absent_alerte():
    fresh(); sent = []
    GD.Garde(post=api(), send=sent.append, clock=Clock(1_800_000_000.0)).tick()
    assert sent and "signe de vie" in sent[0]

def test_kill_alerte():
    fresh(); now = 1_800_000_000.0; sent = []; write_status(10, now)
    g = GD.Garde(post=api(), send=sent.append, clock=Clock(now))
    open(C.KILL_SWITCH, "w").write("raison du test"); g.tick(); g.tick()
    assert sum("KILL" in s for s in sent) == 1 and "raison du test" in sent[0]

def test_position_sans_stop_alerte_et_fin():
    fresh(); now = 1_800_000_000.0; sent = []; write_status(10, now); clk = Clock(now)
    g = GD.Garde(post=api(pos=("ETH", "BTC"), stops=("BTC",)), send=sent.append, clock=clk)
    g.tick()
    assert any("SANS STOP" in s and "ETH" in s and "BTC" not in s.split(":")[1] for s in sent)
    g.post = api(pos=("BTC",), stops=("BTC",)); clk.t += 400; g.tick()
    assert sent[-1].startswith("✅") and "ETH" in sent[-1]

def test_garde_sans_cle_dans_compose():
    y = open(os.path.join(ROOT, "docker-compose.yml")).read()
    blocks = y.split("\n  garde:")[1].split("\n  chercheur:")
    assert "HL_AGENT_KEY" not in blocks[0] and "env_file" not in blocks[0] and ":ro" in blocks[0]
    assert "HL_AGENT_KEY" not in blocks[1] and "env_file" not in blocks[1]

def seed(rows, closed):
    fresh()
    for r in rows: J.record(r["stage"], r["decision"], "x", **r["data"])
    s = G.load(); s["closed"] = closed; s["r_ledger"] = [c["R"] for c in closed]; G.save(s)

def test_score_de_fable_apparie_par_bougie():
    now = dt.datetime(2026, 11, 22, 17, 5, tzinfo=dt.timezone.utc)
    rows = [{"stage": "fable", "decision": "prendre", "data": {"coin": "ETH", "bar_ts": 1, "avis": "prendre"}},
            {"stage": "fable", "decision": "eviter", "data": {"coin": "BTC", "bar_ts": 2, "avis": "eviter"}},
            {"stage": "fable", "decision": "eviter", "data": {"coin": "SOL", "bar_ts": 9, "avis": "eviter"}}]
    closed = [{"ts": "2026-11-20T10:00:00Z", "coin": "ETH", "bar_ts": 1, "R": 2.0, "pnl": 4.0, "side": "long", "issue": "x"},
              {"ts": "2026-11-21T10:00:00Z", "coin": "BTC", "bar_ts": 2, "R": -1.0, "pnl": -2.0, "side": "short", "issue": "x"},
              {"ts": "2026-11-21T11:00:00Z", "coin": "SOL", "bar_ts": 3, "R": -1.0, "pnl": -2.0, "side": "long", "issue": "x"}]
    seed(rows, closed)
    st = CH.week_stats(G.load(), CH.read_journal(), now)
    assert st["fable_depuis_le_debut"]["prendre"] == {"trades": 1, "R_moyen": 2.0, "gagnants": 1.0}
    assert st["fable_depuis_le_debut"]["eviter"]["trades"] == 1                      # SOL : bougie differente, non apparie
    assert st["trades_fermes"] == 3 and st["R_cumule"] == 0.0

class Resp:
    status_code = 200
    def json(self): return {"content": [{"type": "text", "text": "Lecture du marche. Proposition 1 : ..."}]}

def test_bilan_ecrit_envoye_et_non_repete():
    seed([], [])
    now = dt.datetime(2026, 11, 22, 17, 5, tzinfo=dt.timezone.utc); sent = []
    assert CH.due(now) and not CH.due(now.replace(hour=16)) and not CH.due(now - dt.timedelta(days=1))
    os.environ["ANTHROPIC_API_KEY"] = "k"; importlib.reload(C)
    try:
        calls = []
        path, _ = CH.report(now, post=lambda url, **k: (calls.append(k), Resp())[1], send=sent.append)
        assert os.path.exists(path) and "Proposition 1" in open(path).read() and sent and "a pre-enregistrer" in sent[0]
        assert calls[0]["json"]["model"] == C.FABLE_MODEL
        assert not CH.due(now + dt.timedelta(hours=1))                                 # redemarrage : pas de second envoi
    finally:
        os.environ.pop("ANTHROPIC_API_KEY"); importlib.reload(C)

def test_bilan_sans_cle():
    seed([], []); sent = []
    path, _ = CH.report(dt.datetime(2026, 11, 22, 17, 5, tzinfo=dt.timezone.utc), send=sent.append)
    assert "Fable absent" in open(path).read()

def test_sources_propres():
    for f in ("garde.py", "chercheur.py"):
        assert "\u2014" not in open(os.path.join(ROOT, "moon", f), encoding="utf-8").read()

if __name__ == "__main__":
    only = sys.argv[1:]; tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and (not only or n in only)]
    bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
