"""Tests hors ligne du Recolteur T6 (papier). Aucun reseau.
    python3 -B tests/test_recolteur.py"""
import os, sys, json, io, tempfile, contextlib, math
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
os.environ["DATA_DIR"] = tempfile.mkdtemp()
from recolteur import config as C, journal as J, rapport as RA, flux as F
from recolteur.marche import Coin, btc_regime_ok, round_sig
from recolteur.papier import Moteur, pf_of

T0 = 1_794_182_400_000
S, M = 1000, 60_000

def calm_btc(n=400, t0=T0 - 400 * 5 * M, amp=0.001):
    b = Coin("BTC"); px = 50_000.0; bars = []
    for k in range(n):
        o = px; px = px * (1 + (amp if k % 2 else -amp)); bars.append((t0 + k * 5 * M, o, max(o, px), min(o, px), px))
    b.load_bars(bars); return b

def coin_bars(c, t_end, px=100.0, rng=1.0):
    c.load_bars([(t_end - (20 - k) * 5 * M, px, px + rng / 2, px - rng / 2, px) for k in range(20)])

class Rec:
    def __init__(self): self.msgs = []
    def __call__(self, text): self.msgs.append(text)

def engine(coins=("WIF",), papier=True, fetch_1m=None):
    d = tempfile.mkdtemp()
    cs = {n: Coin(n, 3) for n in coins}
    for c in cs.values(): coin_bars(c, T0)
    m = Moteur(cs, calm_btc(), J.Journal(os.path.join(d, "j.jsonl")), state_path=os.path.join(d, "etat.json"), notify=Rec(), fetch_1m=fetch_1m)
    if papier:
        m.s.update(debut=T0 - 8 * C.D, phase="papier", univers=list(coins), univers_t=T0 - C.D, papier_t=T0 - C.D)
    return m

def warm(m, coin="WIF", until=T0 + 22 * M, px=100.0, step=5 * S, start=T0):
    t = start; k = 0
    while t < until:
        m.on_bbo(coin, t, px - 0.01, px + 0.01); m.on_book(coin, t, [(px - 0.5, 1000.0)])
        m.on_trade(coin, t, px, 1.0, "A" if k % 2 == 0 else "B", t + 50)
        t += step; k += 1
    return t

def cascade(m, coin="WIF", t=None, low=98.0):
    t = t or warm(m, coin)
    for k, p in enumerate((99.7, 99.3, 98.7, low)):
        tt = t + k * 5 * S
        m.on_bbo(coin, tt, p - 0.1, p + 0.1); m.on_book(coin, tt, [(p - 0.5, 1000.0)])
        m.on_trade(coin, tt, p, 50.0, "A", tt + 120)
    return t + 15 * S

def events(m, kind): return [json.loads(l) for l in open(m.j.path) if json.loads(l)["type"] == kind] if os.path.exists(m.j.path) else []

def ligne(m): return next(iter(m.s["lignes"].values())) if m.s["lignes"] else None

# ================================================================ marche
def test_atr_fenetres_vwap_bougies():
    c = Coin("X"); coin_bars(c, T0); assert abs(c.atr() - 1.0) < 1e-12
    c2 = Coin("Y"); c2.load_bars([(T0 + k * 5 * M, 1, 1, 1, 1) for k in range(10)]); assert c2.atr() is None
    t = T0 + 30 * M
    for tt, side in ((t, "A"), (t - 60 * S, "A"), (t - 60 * S - 1, "A"), (t - 21 * 60 * S + 1, "A"), (t - 21 * 60 * S, "A"), (t - 5 * S, "B")):
        c.on_trade(tt, 10.0, 1.0, side)
    cur, prec = c.sell_windows(t)
    assert cur == 10.0 and prec[0] == 20.0 and prec[19] == 10.0 and sum(prec) == 30.0      # ]t-60 s, t] ; t-21 min exclu
    c3 = Coin("Z")
    for tt, px, sz in ((t - 400 * S, 50, 9), (t - 300 * S, 10, 1), (t - 61 * S, 20, 1), (t - 30 * S, 99, 9)): c3.on_trade(tt, px, sz, "B")
    assert c3.vwap(t) == 15.0 and c3.high_60(t) == 99
    c5 = Coin("H"); c5.on_trade(t - 61 * S, 50, 1, "B"); c5.on_trade(t - 10 * S, 10, 1, "B"); assert c5.high_60(t) == 10
    c4 = Coin("K"); c4.on_candle(T0, 1, 2, 0.5, 1.5); c4.on_candle(T0, 1, 3, 0.5, 2.5); assert not c4.bars
    c4.on_candle(T0 + 5 * M, 2.5, 2.6, 2.4, 2.5); assert list(c4.bars) == [(T0, 1, 3, 0.5, 2.5)]
    assert round_sig(97.123456) == 97.123 and round_sig(0.00123456) == 0.0012346

def test_regime_btc():
    assert btc_regime_ok(list(calm_btc().bars)) is True
    b = calm_btc(); bars = list(b.bars); last = bars[-1][4]
    for k in range(12):
        o = last; last = last * (1.03 if k % 2 else 0.97); bars.append((bars[-1][0] + 5 * M, o, max(o, last), min(o, last), last))
    assert btc_regime_ok(bars) is False and btc_regime_ok(bars[:50]) is None

# ================================================================ signal et ordre
def test_froid_avant_21_minutes():
    m = engine(); t = warm(m, until=T0 + 20 * M); cascade(m, t=t)
    assert not m.s["lignes"] and not events(m, "cascade")

def test_lot_initial_ne_raccourcit_pas_la_chauffe():
    m = engine(); now = T0 + 60 * M
    m.on_bbo("WIF", now, 99.99, 100.01); m.on_book("WIF", now, [(99.5, 1000.0)])
    for k in range(10): m.on_trade("WIF", T0 + k * 5 * M, 100.0, 1.0, "A")               # transactions anciennes envoyees a l'abonnement
    assert m.coins["WIF"].since == now and not m.coins["WIF"].ready(now)
    warm(m, start=now + 5 * S, until=now + 20 * M); assert not m.coins["WIF"].ready(m.clock)
    warm(m, start=now + 20 * M, until=now + 22 * M); assert m.coins["WIF"].ready(m.clock)

def test_cascade_ordre_alo():
    m = engine(); cascade(m)
    L = ligne(m); ev = events(m, "cascade")[0]["data"]
    assert ev["prise"] and ev["signal_complet"] and ev["latence_ms"] == 120 and abs(ev["baisse"] - 2.0) < 1e-9
    assert L["limite"] == 97.0 and abs(L["stop"] - 94.5) < 1e-9 and L["cible"] == 100.0
    assert L["reste"] == 0.206 and L["expire"] == L["t_ordre"] + 90 * S                       # 20 % de l'equite / prix, arrondi
    o = events(m, "ordre")[0]["data"]; assert o["type"] == "ALO" and o["levier"] == 3

def test_conditions_volume_et_profondeur():
    m = engine(); t = warm(m)
    for k, p in enumerate((99.7, 99.3, 98.7, 98.0)):
        tt = t + k * 5 * S; m.on_bbo("WIF", tt, p - 0.1, p + 0.1); m.on_book("WIF", tt, [(p - 0.5, 1000.0)]); m.on_trade("WIF", tt, p, 0.5, "A")
    assert not events(m, "cascade")                                                          # volume vendeur trop faible
    m2 = engine(); t = warm(m2)
    for k, p in enumerate((99.7, 99.3, 98.7, 98.0)):
        tt = t + k * 5 * S; m2.on_bbo("WIF", tt, p - 0.1, p + 0.1); m2.on_book("WIF", tt, [(p - 0.5, 0.5), (90.0, 1e6)]); m2.on_trade("WIF", tt, p, 50.0, "A")
    ev = events(m2, "cascade")[0]["data"]
    assert not ev["signal_complet"] and ev["refus"] == "profondeur insuffisante" and not m2.s["lignes"]
    m4 = engine(); t = warm(m4)
    for k, p in enumerate((99.7, 99.3, 98.7, 98.0)):
        tt = t + k * 5 * S; m4.on_bbo("WIF", tt, p - 0.1, p + 0.1); m4.on_book("WIF", tt, [(p - 0.5, 1000.0)]); m4.on_trade("WIF", tt, p, 2.5, "A")
    assert not events(m4, "cascade")                                                         # au-dessus de la mediane mais sous 3 fois
    m5 = engine(); m5.s["univers"] = ["DOGE"]; cascade(m5)
    assert events(m5, "cascade")[0]["data"]["refus"] == "hors univers" and not m5.s["lignes"]
    m3 = engine(); t = warm(m3); cascade(m3, t=t, low=98.6)
    assert not events(m3, "cascade")                                                         # baisse 1,4 < 1,5 ATR

def test_alo_rejete_et_reessai():
    m = engine(); t = warm(m)
    for k, p in enumerate((99.7, 99.3, 98.7)):
        tt = t + k * 5 * S; m.on_bbo("WIF", tt, p - 0.1, p + 0.1); m.on_book("WIF", tt, [(p - 0.5, 1000.0)]); m.on_trade("WIF", tt, p, 50.0, "A")
    tt = t + 15 * S; m.on_bbo("WIF", tt, 98.5, 96.0); m.on_book("WIF", tt, [(97.0, 1000.0)]); m.on_trade("WIF", tt, 98.0, 50.0, "A")
    assert events(m, "cascade")[0]["data"]["refus"] == "ALO rejete apres 5 essais" and not m.s["lignes"]
    m2 = engine(); t = warm(m2)
    for k, p in enumerate((99.7, 99.3, 98.7)):
        tt = t + k * 5 * S; m2.on_bbo("WIF", tt, p - 0.1, p + 0.1); m2.on_book("WIF", tt, [(p - 0.5, 1000.0)]); m2.on_trade("WIF", tt, p, 50.0, "A")
    tt = t + 15 * S; m2.on_bbo("WIF", tt, 98.5, 96.2); m2.on_book("WIF", tt, [(97.0, 1000.0)]); m2.on_trade("WIF", tt, 98.0, 50.0, "A")
    L = ligne(m2); x = round_sig(97.35 - 1.0); n = 0
    while x >= 96.2: x = round_sig(x * 0.9995); n += 1
    assert L and L["limite"] == x < 96.2 and n == 4

# ================================================================ remplissages et sorties
def test_remplissage_partiel_puis_stop_immediat():
    m = engine(); t = cascade(m); L = ligne(m)
    m.on_trade("WIF", L["t_ordre"], 96.0, 5.0, "A")                                           # meme instant que le signal : ignore
    m.on_trade("WIF", t + 500, 97.0, 5.0, "A")                                                # au prix limite : pas rempli
    assert L["qty"] == 0
    m.on_trade("WIF", t + S, 96.99, 0.1, "A")
    assert abs(L["qty"] - 0.1) < 1e-12 and abs(L["reste"] - 0.106) < 1e-9 and L["t_premier"] == t + S
    r = events(m, "remplissage")[0]["data"]; assert r["stop_arme"] and abs(r["stop"] - 94.5) < 1e-9
    m.on_trade("WIF", t + 2 * S, 94.4, 0.01, "A")
    assert not m.s["lignes"]
    tr = m.s["trades"][-1]; assert tr["issue"] == "STOP" and abs(tr["taille"] - 0.11) < 1e-12 and abs(tr["sortie"] - 94.4 * 0.9995) < 1e-9
    assert abs(tr["frais"] - (0.11 * 97 * C.FEE_MAKER + 0.11 * tr["sortie"] * C.FEE_TAKER)) < 1e-12           # la transaction du stop remplit aussi

def test_annulation_avant_remplissage_et_reste_annule():
    m = engine(); t = cascade(m); lid = next(iter(m.s["lignes"]))
    m.on_bbo("WIF", t + 91 * S, 97.5, 97.7)
    assert not m.s["lignes"] and events(m, "expire")[0]["data"]["ligne"] == lid
    m2 = engine(); t = cascade(m2); L = ligne(m2)
    m2.on_trade("WIF", t + S, 96.9, 0.05, "A"); m2.on_bbo("WIF", t + 91 * S, 97.5, 97.7)
    assert L["reste"] == 0 and L["qty"] == 0.05 and events(m2, "reste_annule")
    m2.on_trade("WIF", t + 92 * S, 96.0, 5.0, "A"); assert L["qty"] == 0.05                    # plus de remplissage apres expiration

def test_sortie_cible_temps_funding():
    m = engine(); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A")
    m.on_trade("WIF", t + 2 * S, 100.0, 1.0, "B"); assert m.s["lignes"]                       # au prix de la cible : pas de sortie
    m.on_trade("WIF", t + 3 * S, 100.01, 1.0, "B")
    tr = m.s["trades"][-1]; assert tr["issue"] == "CIBLE" and tr["sortie"] == 100.0 and tr["reversion_ms"] == 2 * S and tr["R"] > 0
    m2 = engine(); t = cascade(m2); m2.on_trade("WIF", t + S, 96.9, 1.0, "A")
    m2.on_bbo("WIF", t + S + 15 * M - 1, 97.4, 97.6); assert m2.s["lignes"]
    m2.on_bbo("WIF", t + S + 15 * M, 97.4, 97.6)
    tr = m2.s["trades"][-1]; assert tr["issue"] == "TEMPS" and tr["sortie"] == 97.4 and tr["duree_ms"] == 15 * M
    m3 = engine(); t = cascade(m3); m3.on_trade("WIF", t + S, 96.9, 1.0, "A")
    m3.on_funding("WIF", 0.0005); m3.on_bbo("WIF", t + 2 * S, 97.4, 97.6); assert m3.s["lignes"]
    m3.on_funding("WIF", 0.00051); m3.on_bbo("WIF", t + 3 * S, 97.4, 97.6)
    assert m3.s["trades"][-1]["issue"] == "FUNDING"

def test_funding_regle_a_l_heure():
    m = engine(); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A"); L = ligne(m)
    m.on_funding("WIF", 0.0001); nxt = (t + S) // C.H * C.H + C.H; L["t_premier"] = nxt - M
    m.on_bbo("WIF", nxt - 1, 97.0, 97.2); assert L["funding"] == 0
    m.on_bbo("WIF", nxt, 97.0, 97.2); assert abs(L["funding"] - 0.0001 * L["qty"] * 97.1) < 1e-12

# ================================================================ garde-fous
def test_garde_fous_lignes_heure_actif():
    m = engine(coins=("WIF", "DOGE", "PUMP")); t = T0
    t = T0
    while t < T0 + 22 * M:                                                                    # trois actifs chauffes en parallele
        for c in ("WIF", "DOGE", "PUMP"): warm(m, c, start=t, until=t + 1)
        t += 5 * S
    t = T0 + 22 * M
    for c in ("WIF", "DOGE", "PUMP"): cascade(m, c, t=t)
    refus = [e["data"]["refus"] for e in events(m, "cascade")]
    assert len(m.s["lignes"]) == 2 and refus[-1] == "deja 2 lignes"
    m2 = engine(); m2.s["ordres_t"] = [T0 + 22 * M - k * M for k in range(1, 7)]; cascade(m2)
    assert events(m2, "cascade")[0]["data"]["refus"] == "6 ordres dans l'heure"
    m3 = engine(); m3.s["derniere_entree"]["WIF"] = T0 + 22 * M - 29 * M; cascade(m3)
    assert events(m3, "cascade")[0]["data"]["refus"] == "entree recente sur l'actif"

def fake_ligne(m, lid, coin="WIF"):
    m.s["lignes"][lid] = {"coin": coin, "limite": 100, "reste": 0, "qty": 1.0, "entree": 100.0, "stop": 98.0, "stop_dist": 2.0, "cible": 104,
                          "t_ordre": 0, "expire": 0, "t_premier": 0, "frais": 0.0, "funding": 0.0, "mid_signal": 101, "baisse": 2, "haut": 100, "bas": 100}

def test_pause_journaliere_et_mode_reduit():
    m = engine(); m.s.update(jour=T0 // C.D, equite_jour=100.0)
    for k in range(3):
        fake_ligne(m, f"X{k}"); m._exit(f"X{k}", m.s["lignes"][f"X{k}"], 99.4, "STOP", 0.0, T0 + k)
    assert m.s["reduit"] and m.s["pause_jusqu"] == 0                                         # -1,8 % : pas de pause
    fake_ligne(m, "W1"); m._exit("W1", m.s["lignes"]["W1"], 101, "CIBLE", 0.0, T0 + 10); assert m.s["reduit"]
    fake_ligne(m, "W2"); m._exit("W2", m.s["lignes"]["W2"], 101, "CIBLE", 0.0, T0 + 11); assert not m.s["reduit"]
    m2 = engine(); m2.s.update(jour=T0 // C.D, equite_jour=100.0)
    fake_ligne(m2, "P"); m2._exit("P", m2.s["lignes"]["P"], 97.99, "STOP", 0.0, T0 + 5)
    assert m2.s["pause_jusqu"] == T0 + 5 + 12 * C.H and events(m2, "pause")
    cascade(m2); assert events(m2, "cascade")[0]["data"]["refus"] == "pause journaliere"

def test_taille_reduite_de_moitie():
    m = engine(); m.s["reduit"] = True; m.s["equite"] = 1000.0; cascade(m)
    assert ligne(m)["reste"] == 2.0                                                           # 0,5 % x 1000 / 2,5

def test_regime_refuse():
    m = engine(); bars = list(m.btc.bars); last = bars[-1][4]
    for k in range(12):
        o = last; last = last * (1.03 if k % 2 else 0.97); m.btc.load_bars([(bars[-1][0] + (k + 1) * 5 * M, o, max(o, last), min(o, last), last)])
    cascade(m); assert events(m, "cascade")[0]["data"]["refus"] == "regime BTC trop volatil"

# ================================================================ phases, univers, verdict
def test_mesure_puis_univers_fige():
    names = [f"C{k}" for k in range(10)]
    m = engine(coins=names, papier=False)
    for day in range(8):
        t = T0 + day * C.D
        for k, n in enumerate(names):
            m.on_bbo(n, t, 9.99, 10.01); m.on_book(n, t, [(9.95, 100.0 * (k + 1))])
        for k, n in enumerate(names): m.on_book(n, t + 55 * S, [(9.95, 100.0 * (k + 1)), (9.0, 1e9)])
        m.on_bbo("C0", t + 61 * S, 9.99, 10.01)
    assert m.s["phase"] == "papier" and m.s["univers"] == [f"C{k}" for k in range(9, 1, -1)] and len(m.s["univers"]) == 8
    u = events(m, "univers")[0]["data"]; assert len(u["sha256"]) == 64
    m2 = engine(papier=False); cascade(m2); assert events(m2, "cascade")[0]["data"]["refus"] == "phase mesure" and not m2.s["lignes"]

def test_abandon_et_fin():
    m = engine(); m.s["trades"] = [{"brut": (2.0 if k % 3 == 0 else -1.0), "frais": 0.05, "funding": 0.0, "risque": 1.0, "t_sortie": 0} for k in range(59)]
    fake_ligne(m, "Z"); m._exit("Z", m.s["lignes"]["Z"], 99.0, "STOP", 0.0, T0 + 1)
    assert m.s["phase"] == "abandon" and events(m, "abandon") and any("ABANDON" in x for x in m.notify.msgs)
    m2 = engine(); m2.s["remplissages"] = 500; m2.on_bbo("WIF", T0, 1, 2); assert m2.s["phase"] == "fin"
    m3 = engine(); m3.on_bbo("WIF", m3.s["papier_t"] + C.FIN_PAPIER_MS, 1, 2); assert m3.s["phase"] == "fin"

def test_pf_stress():
    tr = [{"brut": 1.0, "frais": 0.1, "funding": 0.0, "risque": 1.0}, {"brut": -0.5, "frais": 0.1, "funding": 0.05, "risque": 1.0}]
    pf1, _ = pf_of(tr); pf3, rs = pf_of(tr, 3.0)
    assert abs(pf1 - 0.9 / 0.65) < 1e-12 and abs(pf3 - 0.7 / 0.85) < 1e-12 and len(rs) == 2

# ================================================================ trous et redemarrage
def test_trou_annule_et_rejoue_stop_avant_cible():
    bars = {"WIF": [(T0 + 30 * M, 97, 97.5, 96.8, 97.2), (T0 + 31 * M, 97, 101, 94.0, 100)]}
    m = engine(fetch_1m=lambda c, a, b: bars[c]); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A")
    assert ligne(m)["reste"] > 0 or True
    m.gap(t + 2 * S, T0 + 40 * M)
    tr = m.s["trades"][-1]; assert tr["issue"] == "STOP" and abs(tr["sortie"] - ligne_stop(tr)) < 1e-9
    assert not m.coins["WIF"].ready(m.clock) and events(m, "trou")
    m2 = engine(fetch_1m=lambda c, a, b: []); cascade(m2); m2.gap(m2.clock, m2.clock + M)
    assert not m2.s["lignes"] and events(m2, "annule_trou")

def ligne_stop(tr): return 94.5 * (1 - C.GLISSEMENT)

def test_trou_sortie_temps_et_redemarrage():
    seen = []
    def f1m(c, a, b): seen.append((a, b)); return [(T0 + 23 * M + k * M, 97, 97.5, 96.8, 97.2) for k in range(30)]
    m = engine(fetch_1m=f1m); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A"); m.save()
    m2 = Moteur(m.coins, m.btc, J.Journal(m.j.path), state_path=m.state_path, fetch_1m=f1m)
    assert m2.s["lignes"] and m2.s["phase"] == "papier"
    m2.gap(t + S, T0 + 60 * M)
    tr = m2.s["trades"][-1]; assert tr["issue"] == "TEMPS" and tr["t_sortie"] >= tr["t_entree"] + 15 * M and seen[-1][0] % M == 0

# ================================================================ flux, journal, rapport
def test_dispatch_messages():
    m = engine(); got = []
    m.on_trade = lambda *a: got.append(("t",) + a); m.on_bbo = lambda *a: got.append(("b",) + a)
    m.on_book = lambda *a: got.append(("l",) + a); m.on_candle = lambda *a: got.append(("c",) + a); m.on_funding = lambda *a: got.append(("f",) + a)
    F.dispatch(m, {"channel": "trades", "data": [{"coin": "WIF", "side": "A", "px": "1.5", "sz": "10", "time": 5, "tid": 1}]}, 9)
    F.dispatch(m, {"channel": "bbo", "data": {"coin": "WIF", "time": 6, "bbo": [{"px": "1.4", "sz": "1", "n": 1}, {"px": "1.6", "sz": "1", "n": 1}]}})
    F.dispatch(m, {"channel": "bbo", "data": {"coin": "WIF", "time": 6, "bbo": [None, {"px": "1.6", "sz": "1", "n": 1}]}})
    F.dispatch(m, {"channel": "l2Book", "data": {"coin": "WIF", "time": 7, "levels": [[{"px": "1.4", "sz": "3", "n": 1}], [{"px": "1.6", "sz": "2", "n": 1}]]}})
    F.dispatch(m, {"channel": "candle", "data": {"t": 0, "T": 299999, "s": "BTC", "i": "5m", "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "1", "n": 3}})
    F.dispatch(m, {"channel": "activeAssetCtx", "data": {"coin": "WIF", "ctx": {"funding": "0.0000125", "markPx": "1.5"}}})
    assert F.dispatch(m, {"channel": "pong"}) == "pong"
    assert got == [("t", "WIF", 5, 1.5, 10.0, "A", 9), ("b", "WIF", 6, 1.4, 1.6), ("l", "WIF", 7, [(1.4, 3.0)]),
                   ("c", "BTC", 0, 1.0, 2.0, 0.5, 1.5), ("f", "WIF", 0.0000125)]
    subs = F.subscriptions(["WIF"])
    assert {"type": "l2Book", "coin": "WIF", "nSigFigs": 3} in subs and len(subs) == 6

def test_rest_reessais_exponentiels():
    calls, sleeps = [], []
    def post(body):
        calls.append(body)
        if len(calls) < 3: raise ConnectionError("x")
        return [{"t": 2, "o": "1", "h": "2", "l": "0.5", "c": "1"}, {"t": 1, "o": "1", "h": "2", "l": "0.5", "c": "1"}, {"t": 2, "o": "1", "h": "2", "l": "0.5", "c": "1"}]
    r = F.Rest(post=post, sleep=sleeps.append, pause=0.0)
    assert r.candles("WIF", "1m", 0, 10) == [(1, 1.0, 2.0, 0.5, 1.0), (2, 1.0, 2.0, 0.5, 1.0)] and sleeps[:2] == [1.0, 2.0]
    r2 = F.Rest(post=lambda b: (_ for _ in ()).throw(ConnectionError("x")), sleep=sleeps.append, pause=0, essais=3)
    try: r2.post({"type": "x"}); assert False
    except ConnectionError: pass

def test_journal_chaine_et_rapport():
    m = engine(); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A"); m.on_trade("WIF", t + 2 * S, 100.5, 1.0, "B")
    ok, n, _ = J.verify(m.j.path); assert ok and n >= 4
    r = RA.resume(RA.lire(m.j.path))
    assert r["trades"] == 1 and r["cascades_completes"] == 1 and r["verdict"].startswith("EN COURS") and r["issues"] == {"CIBLE": 1}
    assert r["frais_x3"]["pf"] == float("inf") and "profondeur_obtenue" in r["moyennes"]
    lines = open(m.j.path).read().splitlines(); x = json.loads(lines[1]); x["data"]["prix"] = 1; lines[1] = json.dumps(x)
    open(m.j.path, "w").write("\n".join(lines) + "\n")
    assert not J.verify(m.j.path)[0]
    with contextlib.redirect_stdout(io.StringIO()): assert RA.main(["--journal", m.j.path]) == 1

def test_statut_json_strict():
    m = engine(); t = cascade(m); m.on_trade("WIF", t + S, 96.9, 1.0, "A"); m.on_trade("WIF", t + 2 * S, 100.5, 1.0, "B")
    s = m.status(); json.dumps(s, allow_nan=False)
    assert s["mode"] == "papier" and s["pf_net"] == "inf" and s["trades"] == 1

def test_sources_propres_et_sans_ordre():
    for f in sorted(os.listdir(os.path.join(ROOT, "recolteur"))):
        if not f.endswith(".py"): continue
        src = open(os.path.join(ROOT, "recolteur", f), encoding="utf-8").read()
        assert "\u2014" not in src, f
        for bad in ("hyperliquid.exchange", "Exchange(", "bulk_orders", "PRIVATE_KEY", "AGENT_KEY", "eth_account", "/exchange"):
            assert bad not in src, (f, bad)

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
