"""Tests hors ligne du Lab v7 (Portage).
    PYTHONPATH=<dossier sp-replay>:. python3 -B tests/test_lab7.py"""
import os, sys, json, io, tempfile, hashlib, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, ROOT)
import numpy as np
from usine import verif_portage as VP, collecte_portage as KP
from tests.test_usine import clk, bars, no_fund
from tests.test_lab4 import FakeAPI, NOW

H = 3_600_000
SPEC = os.path.join(ROOT, "specs", "USINE-SPEC-LAB7.json")
FORT, BASE = 0.0001, 0.00001

def serie(c, vol=1e6):
    df = bars(np.asarray(c, float), step=H); df.loc[:, "vol"] = vol / df.close; return df

def fund(df, taux):
    """Un taux par bougie, date a la cloture de la bougie."""
    return (df.ts.values + H, np.asarray(taux, float))

def montee_puis_repli(n=400, sommet=250):
    """Hausse reguliere puis baisse lente : le prix repasse sous l'EMA 50 quelques bougies apres le sommet."""
    return np.concatenate([100 * np.exp(0.002 * np.arange(sommet)), 100 * np.exp(0.002 * sommet) * np.exp(-0.002 * np.arange(1, n - sommet + 1))])

def test_funding_24h_moyenne_sans_regard_en_avant():
    df = serie(np.full(60, 100.0)); t = np.arange(60) * 1e-6
    f = VP.funding_24h(df, fund(df, t))
    assert np.isnan(f[:19]).all() and abs(f[19] - t[:20].mean()) < 1e-15           # au moins 20 taux
    assert abs(f[40] - t[17:41].mean()) < 1e-15                                     # les 24 taux jusqu'a la cloture de la bougie, pas au-dela
    assert np.isnan(VP.funding_24h(df, no_fund())).all()

def test_short_quand_les_acheteurs_entasses_lachent():
    df = serie(montee_puis_repli()); fd = fund(df, np.full(len(df), FORT))
    t = VP.portage("X", df, fd)
    assert t and t[0]["side"] == "short" and t[0]["signal_ts"] > df.ts.values[250]  # jamais pendant la hausse
    pur = VP.portage("X", df, fd, avec_ema=False)
    assert pur[0]["signal_ts"] < t[0]["signal_ts"] and pur[0]["strat"] == "PORTAGE_1h_sans_ema"

def test_long_symetrique():
    c = 1e4 / montee_puis_repli(); df = serie(c)
    t = VP.portage("X", df, fund(df, np.full(len(df), -FORT)))
    assert t and all(x["side"] == "long" for x in t) and t[0]["signal_ts"] > df.ts.values[250]

def test_rien_sans_funding_extreme():
    df = serie(montee_puis_repli())
    assert VP.portage("X", df, fund(df, np.full(len(df), BASE))) == []
    assert VP.portage("X", df, fund(df, np.full(len(df), 0.00004)), avec_ema=False) == []     # sous le seuil de 0,005 % par heure
    assert VP.portage("X", df, no_fund()) == []

def test_filtre_de_volume():
    df = serie(montee_puis_repli(), vol=5e4)
    assert VP.portage("X", df, fund(df, np.full(len(df), FORT))) == []

def test_sortie_quand_le_funding_revient_a_la_normale():
    df = serie(montee_puis_repli()); taux = np.full(len(df), FORT); taux[290:] = 0.0
    t = VP.portage("X", df, fund(df, taux))
    assert len(t) == 1 and t[0]["issue"] == "sortie signal" and t[0]["exit_ts"] < df.ts.values[330]

def test_duree_maximale_120_bougies():
    df = serie(montee_puis_repli(n=600)); t = VP.portage("X", df, fund(df, np.full(len(df), FORT)))
    assert t[0]["issue"] == "temps max" and t[0]["exit_ts"] - t[0]["fill_ts"] == 120 * H

def test_funding_recu_compte_dans_le_resultat():
    df = serie(montee_puis_repli(n=600)); t = VP.portage("X", df, fund(df, np.full(len(df), FORT)))[0]
    assert t["funding_R"] > 0 and abs(t["R"] - (t["gross_R"] - t["fees_R"] + t["funding_R"])) < 1e-9

def test_regle_de_decision():
    spec = json.load(open(SPEC))
    def row(v, e, n=60, tr=0.1, s3=0.1):
        return {"verdict": v, "evaluation_frais_doubles": {"esperance_R": e, "trades": n}, "entrainement_frais_doubles": {"esperance_R": tr},
                "esperance_sans_3_meilleurs_R": s3}
    assert VP.decide(row("PASSE LA VOIE RAPIDE", 0.3), spec).startswith("NIVEAU REEL")
    assert VP.decide(row("PASSE LA VOIE RAPIDE", 0.3, tr=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VP.decide(row("PASSE LA VOIE RAPIDE", 0.3, s3=-0.1), spec).startswith("NIVEAU PAPIER")
    assert VP.decide(row("NE PASSE PAS : x", 0.5, n=12), spec).startswith("NON CONCLUANT")
    assert VP.decide(row("NE PASSE PAS : x", -0.1), spec).startswith("ESPERANCE NEGATIVE")
    assert VP.decide(row("NE PASSE PAS : x", 0.05), spec).startswith("NE PASSE PAS")

class Fake(FakeAPI):
    def __call__(self, body):
        if body["type"] == "metaAndAssetCtxs":
            noms = ["BTC", "ETH", "kPEPE", "DOGE", "WIF", "xyz:TSLA", "INCONNU"]
            return [{"universe": [{"name": c} for c in noms]}, [{} for _ in noms]]
        if body["type"] == "fundingHistory":
            s, e = body["startTime"], body["endTime"]
            return [{"time": x, "fundingRate": "0.0001" if (x // H // 200) % 2 else "0.00001"} for x in range(s // H * H + H, min(e, s + 500 * H), H)]
        return super().__call__(body)

def collect(d):
    now, sl = clk(NOW)
    with contextlib.redirect_stdout(io.StringIO()): return KP.main(["--out", d], post=Fake(), clock=now, sleep=sl)

def test_collecte_memecoins_et_moonshot_sans_doublon():
    assert len(KP.ACTIFS) == len(set(KP.ACTIFS)) and {"kPEPE", "PUMP", "BTC", "DOGE", "XMR"} <= set(KP.ACTIFS)
    d = tempfile.mkdtemp(); man = collect(d)
    assert sorted(man["coins"]) == ["BTC", "DOGE", "ETH", "WIF", "kPEPE"] and man["jeu"] == "portage"
    assert "funding/DOGE.json" in man["files"] and "candles/WIF_1h.json" in man["files"]
    try: collect(d); assert False
    except SystemExit as e: assert "refus" in str(e)

def test_bout_en_bout_et_registre():
    d = tempfile.mkdtemp(); collect(d); out = tempfile.mkdtemp()
    with contextlib.redirect_stdout(io.StringIO()): rep = VP.run(SPEC, d, out)
    assert set(rep["candidats"]) == set(VP.CANDIDATS) and rep["decision"]
    assert all("5 %" in r["croissance_ln"] and "funding_R_moyen" in r for r in rep["candidats"].values())
    assert rep["candidats"]["PORTAGE_1h_sans_ema"]["evaluation_sans_plafond_frais_doubles"]["trades"] > 0
    assert rep["decision"] in open(os.path.join(out, "verdicts.md")).read()
    other = json.load(open(SPEC)); other["gel_utc"] = "x"; p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(other, open(p, "w"))
    try: VP.run(p, d, out); assert False
    except Exception as e: assert "refus" in str(e)

def test_spec_figee():
    s = json.load(open(SPEC))
    assert s["prereg_sha256"] == hashlib.sha256(open(os.path.join(ROOT, "docs", "PREREG-lab7-portage.md"), "rb").read()).hexdigest()
    assert s["palier"] == 0.02 and s["max_positions"] == 2 and s["volume_min_usd"] == 2000000 and s["decisif"] == "PORTAGE_1h"
    assert s["voie_rapide"] == {"trades_min": 40, "esperance_min_R": 0.10}
    assert VP.PT == {"seuil": 0.00005, "retour": 0.0000125, "fenetre_h": 24, "taux_min": 20, "ema": 50, "stop_atr": 3.0, "duree_max": 120}
    bad = dict(s, max_positions=3); p = os.path.join(tempfile.mkdtemp(), "s.json"); json.dump(bad, open(p, "w"))
    try: VP.load_spec(p); assert False
    except Exception as e: assert "deux positions" in str(e)

def test_source_propre():
    for f in ("verif_portage.py", "collecte_portage.py"):
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
