"""Le Controleur : reel contre simule, pour chaque bot en argent reel.
Pour chaque entree ouverte par le bot (journal « execution / ouvert ») :
  - ecart d'entree : prix moyen rempli contre l'ouverture de la bougie 4 h suivant le signal (hypothese du Testeur) ;
  - frais reels contre le modele (0,045 % taker) ;
  - funding reel sur les positions (API publique userFunding).
Les remplissages qui ne correspondent a aucune entree du bot (essai d'execution, autre) sont ignores.
    python3 -m usine.controle --out /out --bot moonshot2:0x...:/b/moonshot2/journal.jsonl [--bot ...]"""
import os, sys, json, time, argparse, datetime as dt

INFO = "https://api.hyperliquid.xyz/info"
H4 = 4 * 3_600_000
FEE_MODELE = 0.00045
SEUIL_ECART = 0.003                 # 0,3 % d'ecart moyen a l'entree : alerte
SEUIL_FRAIS = 0.0006                # taux de frais moyen au-dela de 0,06 % : alerte
FENETRE_MS = 180_000

def post(body, poster=None):
    if poster: return poster(body)
    import requests
    r = requests.post(INFO, json=body, timeout=20); r.raise_for_status(); time.sleep(0.5); return r.json()

def iso_ms(ts):
    return int(dt.datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)

def entrees(journal_path):
    out = []
    if not os.path.exists(journal_path): return out
    for l in open(journal_path, encoding="utf-8"):
        try: r = json.loads(l)
        except ValueError: continue
        if r.get("stage") == "execution" and r.get("decision") == "ouvert":
            parts = (r.get("reason") or "").split()
            if len(parts) >= 2: out.append({"t": iso_ms(r["ts"]), "coin": parts[0], "side": parts[1]})
    return out

def analyser(nom, adresse, journal_path, depuis_ms, maintenant_ms, poster=None):
    ents = entrees(journal_path)
    fills = post({"type": "userFillsByTime", "user": adresse, "startTime": depuis_ms, "endTime": maintenant_ms}, poster) if ents else []
    trades = []
    for e in ents:
        fs = [f for f in fills if f.get("coin") == e["coin"] and str(f.get("dir", "")).startswith("Open") and abs(int(f["time"]) - e["t"]) <= FENETRE_MS]
        if not fs: continue
        sz = sum(float(f["sz"]) for f in fs); px = sum(float(f["px"]) * float(f["sz"]) for f in fs) / sz
        fee = sum(float(f.get("fee", 0)) for f in fs); t0 = min(int(f["time"]) for f in fs)
        bar = t0 // H4 * H4
        c = post({"type": "candleSnapshot", "req": {"coin": e["coin"], "interval": "4h", "startTime": bar, "endTime": bar + H4}}, poster)
        ouv = float(c[0]["o"]) if c else None
        sgn = 1 if e["side"] == "long" else -1
        ecart = (px / ouv - 1) * sgn if ouv else None
        trades.append({"coin": e["coin"], "side": e["side"], "t": t0, "prix": px, "ouverture_4h": ouv, "ecart_entree": ecart,
                       "taux_frais": fee / (px * sz) if px * sz else None})
    fund = post({"type": "userFunding", "user": adresse, "startTime": depuis_ms, "endTime": maintenant_ms}, poster) if trades else []
    funding = sum(float((f.get("delta") or {}).get("usdc", 0)) for f in fund)
    moy = lambda k: (sum(t[k] for t in trades if t[k] is not None) / max(1, sum(1 for t in trades if t[k] is not None))) if trades else None
    return {"bot": nom, "entrees": len(trades), "ecart_entree_moyen": moy("ecart_entree"), "taux_frais_moyen": moy("taux_frais"),
            "funding_usdc": round(funding, 6), "trades": trades}

def verdict(bots):
    alertes = []
    for b in bots:
        if b["entrees"] == 0: continue
        if b["ecart_entree_moyen"] is not None and b["ecart_entree_moyen"] > SEUIL_ECART:
            alertes.append(f"{b['bot']} : entree moyenne {b['ecart_entree_moyen'] * 100:+.2f} % contre l'hypothese du Testeur")
        if b["taux_frais_moyen"] is not None and b["taux_frais_moyen"] > SEUIL_FRAIS:
            alertes.append(f"{b['bot']} : frais moyens {b['taux_frais_moyen'] * 100:.3f} % contre {FEE_MODELE * 100:.3f} % prevus")
    n = sum(b["entrees"] for b in bots)
    if n == 0: return "AUCUN TRADE", "aucun trade reel sur la periode, rien a comparer", alertes
    if alertes: return "ECART", "; ".join(alertes), alertes
    parts = [f"{b['bot']} {b['entrees']} entree(s), ecart {b['ecart_entree_moyen'] * 100:+.2f} %" for b in bots if b["entrees"]]
    return "CONFORME", "reel conforme au simule : " + ", ".join(parts), alertes

def run(bots_spec, out, poster=None, maintenant_ms=None, jours=7):
    now = maintenant_ms or int(time.time() * 1000); depuis = now - jours * 86_400_000
    bots = [analyser(*spec.split(":", 2), depuis, now, poster) for spec in bots_spec]
    v, resume, alertes = verdict(bots)
    rep = {"ts": dt.datetime.fromtimestamp(now / 1000, dt.timezone.utc).isoformat()[:19] + "Z", "periode_jours": jours, "verdict": v,
           "resume": resume, "alertes": alertes, "seuils": {"ecart_entree": SEUIL_ECART, "taux_frais": SEUIL_FRAIS}, "bots": bots}
    os.makedirs(out, exist_ok=True)
    json.dump(rep, open(os.path.join(out, "controle.json"), "w"), indent=1)
    L = [f"# Controle reel contre simule ({rep['ts']}, {jours} jours)", "", f"**{v}** : {resume}", "",
         "| bot | entrees | ecart d'entree moyen | frais moyens | funding (USDC) |", "|---|---|---|---|---|"]
    f = lambda x, k=100, d=3: "–" if x is None else f"{x * k:+.{d}f} %"
    for b in bots: L.append(f"| {b['bot']} | {b['entrees']} | {f(b['ecart_entree_moyen'])} | {f(b['taux_frais_moyen'])} | {b['funding_usdc']:+.4f} |")
    open(os.path.join(out, "controle.md"), "w").write("\n".join(L) + "\n")
    print(f"{v} : {resume}")
    return rep

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--bot", action="append", default=[])
    ap.add_argument("--jours", type=int, default=7)
    a = ap.parse_args(argv)
    run(a.bot, a.out, jours=a.jours)

if __name__ == "__main__":
    main()
