"""Tests hors ligne du Lab v9 (Duel).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab9.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_duel as VD, collecte_duel as KD, sim
from tests.test_usine import clk, bars, no_fund
from tests.test_lab4 import NOW

H, H4 = 3_600_000, 4 * 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB9.json")

def serie(c, vol=1e6):
    df = bars(np.asarray(c, float), step=H4); df.loc[:, "vol"] = vol / df.close; return df

def marche(n=700, seed=1):
    """Marche commune (BTC) : bruit fort, sans tendance propre."""
    rng = np.random.default_rng(seed)
    return 50000 * np.exp(np.cumsum(rng.normal(0, 0.01, n)))

def relatif(n=700, bascule=350, pente=0.004):
    """Force relative : l'actif perd du terrain face a BTC, puis en regagne."""
    return np.exp(np.concatenate([-pente * np.arange(bascule), -pente * bascule + pente * np.arange(1, n - bascule + 1)]))

def test_paire_alignee_sur_les_bougies_communes():
    b = serie(marche()); x = serie(marche() * 0.001).iloc[5:].reset_index(drop=True)
    m = VD.paire(x, b)
    assert len(m) == len(b) - 5 and m.ts.iloc[0] == b.ts.iloc[5]
    assert abs(m.q.iloc[10] - x.close.iloc[10] / b.close.iloc[15]) < 1e-15 and abs(m.qo.iloc[10] - x.open.iloc[10] / b.open.iloc[15]) < 1e-15

def test_duel_suit_la_force_relative_pas_le_marche():
    b = marche(); x = b * 0.001 * relatif()
    t = VD.duel("X", serie(x), serie(b), no_fund(), no_fund())
    assert t and t[0]["side"] == "long" and t[0]["signal_ts"] > serie(b).ts.values[350]     # un seul croisement, apres la bascule
    assert all(tr["strat"] == "DUEL_4h" for tr in t)
    # le meme actif sans force relative (copie de BTC) ne donne aucun duel, quelle que soit la tendance du marche
    assert VD.duel("X", serie(b * 0.001), serie(b), no_fund(), no_fund()) == []

def test_marche_neutre_le_resultat_ne_depend_pas_de_btc():
    rel = relatif(); a = VD.duel("X", serie(marche(seed=1) * 0.001 * rel), serie(marche(seed=1)), no_fund(), no_fund())
    c = VD.duel("X", serie(marche(seed=7) * 0.001 * rel), serie(marche(seed=7)), no_fund(), no_fund())
    assert len(a) == len(c) and all(x["side"] == y["side"] and x["signal_ts"] == y["signal_ts"] for x, y in zip(a, c))

def test_entree_bougie_suivante_et_quatre_frais():
    b = np.full(1100, 50000.0); x = b * 0.001 * trois_phases()
    dx, db = serie(x), serie(b); t = VD.duel("X", dx, db, no_fund(), no_fund())[0]
    i = int(np.searchsorted(dx.ts.values, t["fill_ts"]))
    assert t["signal_ts"] == t["fill_ts"] and abs(t["entry"] - dx.open[i] / db.open[i]) < 1e-15   # ouverture qui suit la cloture du signal
    d = abs(t["entry"] - t["stop"]) / t["entry"]; k = int(np.searchsorted(dx.ts.values, t["exit_ts"]))
    assert abs(t["fees_R"] - sim.FEE_TAKER * (2 + dx.open[k] / dx.open[i] + 1.0) / d) < 1e-9       # deux entrees et deux sorties
    assert abs(t["R"] - (t["gross_R"] - t["fees_R"] + t["funding_R"])) < 1e-9
    assert abs(t["gross_R"] - (dx.open[k] / dx.open[i] - 1) / d) < 1e-9                             # BTC immobile : le gain est celui de X

def test_stop_lu_a_la_cloture_et_perte_reelle_comptee():
    rel = relatif(n=700, bascule=350); rel[500:] = rel[499] * 0.80                     # chute de 20 % du rapport apres l'entree acheteuse
    b = np.full(700, 50000.0); dx, db = serie(b * 0.001 * rel), serie(b)
    t = [tr for tr in VD.duel("X", dx, db, no_fund(), no_fund()) if tr["side"] == "long"][0]
    assert t["fill_ts"] < dx.ts.values[500] and t["issue"] == "STOP" and t["exit_ts"] == dx.ts.values[501]   # cloture de 500 sous le stop, sortie a l'ouverture de 501
    assert t["gross_R"] < -1.0                                                          # le trou est compte, pas un remplissage au prix du stop

def test_sortie_au_croisement_inverse_puis_duel_inverse():
    b = np.full(1100, 50000.0); t = VD.duel("X", serie(b * 0.001 * trois_phases()), serie(b), no_fund(), no_fund())
    assert [x["side"] for x in t[:2]] == ["long", "short"] and t[0]["issue"] == "sortie signal"
    assert t[1]["fill_ts"] == t[0]["exit_ts"] and t[0]["gross_R"] > 0

def test_filtre_de_volume_sur_l_actif():
    b = marche(); x = b * 0.001 * relatif()
    assert VD.duel("X", serie(x, vol=5e4), serie(b), no_fund(), no_fund()) == []

def trois_phases(n=1100):
    return np.exp(np.concatenate([-0.004 * np.arange(350), -1.4 + 0.004 * np.arange(1, 401), 0.2 - 0.004 * np.arange(1, n - 749)]))

def test_funding_des_deux_jambes():
    b = np.full(1100, 50000.0); dx, db = serie(b * 0.001 * trois_phases()), serie(b)
    f = lambda df, r: (df.ts.values + H4, np.full(len(df), r))
    base = VD.duel("X", dx, db, no_fund(), no_fund())[0]
    paye = VD.duel("X", dx, db, f(dx, 0.0001), no_fund())[0]                            # acheteur de X : paie le funding positif de X
    recu = VD.duel("X", dx, db, no_fund(), f(db, 0.0001))[0]                            # vendeur de BTC : recoit le funding positif de BTC
    assert base["funding_R"] == 0 and paye["funding_R"] < 0 < recu["funding_R"]

def test_correlation_journaliere():
    D = 86_400_000
    a = [{"R": float(k % 3 - 1), "signal_ts": k * D, "exit_ts": k * D + 1} for k in range(40)]
    assert VD.correlation_journaliere(a, a, 0) == 1.0
    assert VD.correlation_journaliere(a, [dict(t, R=-t["R"]) for t in a], 0) == -1.0
    assert VD.correlation_journaliere(a[:5], a[:5], 0) is None

def test_regle_de_decision():
    spec = json.load(open(SPEC))
    def row(v, e, n=60, tr=0.1, s3=0.1):
        return {"verdict": v, "evaluation_frais_doubles": {"esperance_R": e, "trades": n}, "entrainement_frais_doubles": {"esperance_R": tr},
                "esperance_sans_3_meilleurs_R": s3}
    assert VD.decide(row("PASSE LA VOIE RAPIDE", 0.3), spec).startswith("NIVEAU REEL")
    assert VD.decide(row("PASSE LA VOIE RAPIDE", 0.3, tr=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VD.decide(row("PASSE LA VOIE RAPIDE", 0.3, s3=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VD.decide(row("NE PASSE PAS : x", 0.5, n=12), spec).startswith("NON CONCLUANT")
    assert VD.decide(row("NE PASSE PAS : x", -0.1), spec).startswith("ESPERANCE NEGATIVE")
    assert VD.decide(row("NE PASSE PAS : x", 0.05), spec).startswith("NE PASSE PAS")

class Fake:
    """API factice : bougies 4 h en marche au hasard par actif, avec une derive relative propre a chaque actif."""
    def __call__(self, body):
        t = body["type"]
        if t == "metaAndAssetCtxs":
            noms = ["BTC", "ETH", "kPEPE", "DOGE", "WIF", "xyz:TSLA", "INCONNU"]
            return [{"universe": [{"name": c} for c in noms]}, [{} for _ in noms]]
        if t == "candleSnapshot":
            r = body["req"]; assert r["interval"] == "4h"; s, e = r["startTime"], r["endTime"]
            ts = list(range((s + H4 - 1) // H4 * H4, e, H4))
            rng = np.random.default_rng(int(hashlib.sha256(r["coin"].encode()).hexdigest()[:6], 16))
            x = 100 * np.exp(np.cumsum(rng.normal(0, 0.012, len(ts)) + 0.004 * np.sin(np.arange(len(ts)) / (40 + len(r["coin"]) * 7))))
            o = np.concatenate([[x[0]], x[:-1]])
            return [{"t": a, "o": f"{b:.6f}", "c": f"{c:.6f}", "h": f"{max(b, c) * 1.003:.6f}", "l": f"{min(b, c) * 0.997:.6f}", "v": f"{1e6 / c:.4f}"}
                    for a, b, c in zip(ts, o, x)]
        if t == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        raise ValueError(t)

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KD.main(["--out", d], post=Fake(), clock=now, sleep=sl)

def test_collecte_4h_reference_et_refus_d_ecraser():
    assert len(KD.ACTIFS) == len(set(KD.ACTIFS)) and {"kPEPE", "PUMP", "BTC", "DOGE", "XMR"} <= set(KD.ACTIFS)
    d = tempfile.mkdtemp(); man = collect(d)
    assert sorted(man["coins"]) == ["BTC", "DOGE", "ETH", "WIF", "kPEPE"] and man["jeu"] == "duel" and man["reference"] == "BTC"
    assert man["debut_4h_ms"] == man["end_ms"] - 5000 * H4 and "funding/DOGE.json" in man["files"] and "candles/WIF_4h.json" in man["files"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VD.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VD.CANDIDATS) and rep["decision"]
    assert all("5 %" in r["croissance_ln"] and "funding_R_moyen" in r and "pire_trade_R" in r for r in rep["candidats"].values())
    assert rep["candidats"]["DUEL_4h"]["evaluation_sans_plafond_frais_doubles"]["trades"] > 0
    assert "BTC" not in rep["candidats"]["DUEL_4h"]["par_actif"] and rep["notes"]["reference"] == "BTC"
    assert rep["decision"] in open(os.path.join(out, "verdicts.md")).read()
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VD.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab9-duel.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.02 and s["max_positions"] == 2 and s["volume_min_usd"] == 2000000 and s["decisif"] == "DUEL_4h" and s["reference"] == "BTC"
    assert s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10}
    assert VD.DU == {"rapide": 50, "lente": 200, "vol": 14, "stop_x": 6.0}
    bad = dict(s, max_positions=3); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VD.load_spec(p); assert False
    except Exception as e: assert "deux positions" in str(e)
    bad = dict(s, reference="ETH"); json.dump(bad, open(p, "w"))
    try: VD.load_spec(p); assert False
    except Exception as e: assert "BTC" in str(e)

def test_source_propre():
    for f in ("verif_duel.py", "collecte_duel.py"):
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
