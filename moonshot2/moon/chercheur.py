"""Fable Chercheur : bilan hebdomadaire automatique (dimanche 17:00 UTC). Conteneur separe, sans cle de trading.
  1. Lit le journal et l'etat du bot (lecture seule) : trades de la semaine, R, avis de Fable et resultat des trades.
  2. Mesure l'apport de Fable : resultat moyen des trades qu'il voulait « prendre » contre ceux qu'il voulait « eviter ».
  3. Demande a Fable une lecture du marche et 1 a 3 propositions de strategies, decrites en regles testables.
  4. Ecrit le rapport dans data/chercheur/ et l'envoie sur Telegram.
Les propositions ne sont JAMAIS appliquees automatiquement : elles passent par un pre-enregistrement et le Testeur.
    python3 -m moon.chercheur            boucle hebdomadaire
    python3 -m moon.chercheur --maintenant   un bilan tout de suite"""
import os, sys, json, time, argparse, logging, datetime as dt
from . import config as C, notify as N, guard as G

log = logging.getLogger("moon.chercheur")
OUT = os.path.join(C.DATA_DIR, "chercheur")
JOURNAL = os.path.join(C.DATA_DIR, "journal.jsonl")
DAY, HOUR = 6, 17                                          # dimanche, 17:00 UTC

def read_journal():
    try: return [json.loads(l) for l in open(JOURNAL, encoding="utf-8")]
    except Exception: return []

def fable_score(rows, closed):
    """Associe chaque avis de Fable au trade ferme du meme actif et de la meme bougie de signal."""
    ops = {(r["data"].get("coin"), r["data"].get("bar_ts")): r["data"] for r in rows if r.get("stage") == "fable" and r["data"].get("avis")}
    out = {"prendre": [], "eviter": []}
    for c in closed:
        if c.get("R") is None: continue
        op = ops.get((c.get("coin"), c.get("bar_ts")))
        if op: out[op["avis"]].append(c["R"])
    summ = lambda xs: {"trades": len(xs), "R_moyen": round(sum(xs) / len(xs), 3) if xs else None,
                       "gagnants": round(sum(1 for x in xs if x > 0) / len(xs), 3) if xs else None}
    return {k: summ(v) for k, v in out.items()}

def week_stats(state, rows, now):
    since = (now - dt.timedelta(days=7)).isoformat()[:19]
    week = [c for c in state.get("closed", []) if str(c.get("ts", "")) >= since]
    signals = [r for r in rows if r.get("stage") == "signal" and r.get("ts", "") >= since]
    return {"semaine_jusqu_au": now.isoformat()[:10], "trades_fermes": len(week),
            "pnl_usdc": round(sum(c.get("pnl", 0) for c in week), 4), "R_semaine": round(sum(c.get("R") or 0 for c in week), 3),
            "R_cumule": round(sum(state.get("r_ledger", [])), 3), "baisse_R": round(G.drawdown_r(state.get("r_ledger", [])), 3),
            "positions_ouvertes": {k: v.get("side") for k, v in state.get("positions", {}).items()},
            "signaux": {d: sum(1 for r in signals if r.get("decision") == d) for d in sorted({r.get("decision") for r in signals})},
            "fable_depuis_le_debut": fable_score(rows, state.get("closed", [])),
            "trades": [{k: c.get(k) for k in ("ts", "coin", "side", "issue", "pnl", "R")} for c in week]}

SYSTEM = ("Tu es le chercheur d'une petite usine de trading automatique sur Hyperliquid. La strategie en reel est M2 : "
          "croisement EMA 50/200 en 4 h sur 13 perps, stop 3 ATR, 1 % de risque par trade. Ta mission chaque semaine : "
          "1) lire le marche et le regime actuel ; 2) analyser les trades et tes propres avis de la semaine, honnetement, y compris "
          "tes erreurs ; 3) proposer 1 a 3 strategies NOUVELLES, chacune decrite en regles completes et testables (actifs, "
          "unite de temps, entree, stop, sortie, parametres fixes) ; 4) signaler les risques. Pas de promesse de gain. "
          "Reponds en francais, en texte simple, 400 mots au plus.")

def ask_fable(stats, post=None):
    if not C.ANTHROPIC_API_KEY: return "(Fable absent : pas de cle API)"
    try:
        if post is None:
            import requests
            post = requests.post
        r = post("https://api.anthropic.com/v1/messages", timeout=120,
                 headers={"x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                 json={"model": C.FABLE_MODEL, "max_tokens": 1500, "system": SYSTEM,
                       "messages": [{"role": "user", "content": "Bilan de la semaine (JSON) :\n" + json.dumps(stats, ensure_ascii=False)}]})
        if getattr(r, "status_code", 0) != 200: return f"(Fable indisponible : API {getattr(r, 'status_code', '?')})"
        return "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text").strip() or "(reponse vide)"
    except Exception as ex:
        return f"(Fable indisponible : {type(ex).__name__})"

def report(now=None, post=None, send=N.send):
    now = now or dt.datetime.now(dt.timezone.utc)
    stats = week_stats(G.load(), read_journal(), now)
    text = ask_fable(stats, post)
    fs = stats["fable_depuis_le_debut"]
    head = (f"🔬 Fable Chercheur : bilan au {stats['semaine_jusqu_au']}\n"
            f"Trades fermes : {stats['trades_fermes']} ; P&L {stats['pnl_usdc']:+.2f} USDC ; {stats['R_semaine']:+.2f} R "
            f"(cumule {stats['R_cumule']:+.2f} R, baisse {stats['baisse_R']:.1f} R)\n"
            f"Avis Fable (depuis le debut) : prendre {fs['prendre']['trades']} trades, R moyen {fs['prendre']['R_moyen']} ; "
            f"eviter {fs['eviter']['trades']} trades, R moyen {fs['eviter']['R_moyen']}\n"
            "Propositions : a pre-enregistrer et a tester avant tout usage.\n\n")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"bilan-{stats['semaine_jusqu_au']}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + text + "\n\n## Donnees\n\n```json\n" + json.dumps(stats, ensure_ascii=False, indent=1) + "\n```\n")
    send((head + text)[:3900])
    return path, stats

def due(now):
    """Dimanche apres 17:00 UTC, si le bilan du jour n'existe pas encore (un redemarrage ne le renvoie pas)."""
    return now.weekday() == DAY and now.hour >= HOUR and not os.path.exists(os.path.join(OUT, f"bilan-{now.date().isoformat()}.md"))

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--maintenant", action="store_true"); a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if a.maintenant: print(report()[0]); return
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        if due(now):
            try: report(now)
            except Exception as ex: log.warning("bilan : %s", type(ex).__name__); time.sleep(600); continue
        time.sleep(300)

if __name__ == "__main__":
    main()
