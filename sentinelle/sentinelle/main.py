"""La Sentinelle : surveille la plateforme Hyperliquid pour l'equipe, toutes les 15 minutes, en lecture seule (API publique).
  - regles des actifs suivis : delisting, disparition, levier maximum, decimales, isole impose ;
  - positions des deux comptes : funding extreme contre la position, position sans stop au carnet ;
  - cles d'agent : expiration a moins de 30 jours ;
  - API injoignable trois fois de suite.
Chaque alerte part sur Telegram une seule fois par periode et s'inscrit dans data/alertes.jsonl. Aucune cle de trading.
    python3 -m sentinelle.main"""
import os, json, time, logging, datetime as dt

log = logging.getLogger("sentinelle")
INFO = "https://api.hyperliquid.xyz/info"
DATA = os.getenv("DATA_DIR", "/app/data")
COMPTES = {"Moonshot": os.getenv("MOON_ACCOUNT", ""), "Smart Peanut": os.getenv("LABO_ACCOUNT", "")}
SUIVIS = ("BTC", "ETH", "SOL", "ZEC", "HYPE", "NEAR", "kPEPE", "XRP", "PUMP", "XMR", "LIT", "UNI", "AVAX",
          "kBONK", "kSHIB", "kFLOKI", "kNEIRO", "kDOGS", "DOGE", "WIF", "POPCAT", "FARTCOIN", "TRUMP", "MELANIA", "PENGU", "MOODENG",
          "GOAT", "PNUT", "SPX", "MEW", "BRETT", "TURBO", "CHILLGUY", "USELESS", "MEME", "BOME", "MYRO", "GRIFFAIN", "AI16Z", "VINE", "HPOS")
PERIODE_S = 15 * 60
FUNDING_EXTREME = 0.001            # 0,1 % par heure contre la position
CLE_JOURS = 30
RAPPEL_S = {"api": 6 * 3600, "regle": 10 ** 9, "funding": 6 * 3600, "stop": 3600, "cle": 86400}

def is_stop(o):
    return bool(o.get("reduceOnly") and ((o.get("isTrigger") and o.get("tpsl") == "sl") or "stop" in str(o.get("orderType", "")).lower()))

class Sentinelle:
    def __init__(self, post=None, send=None, clock=time.time, data=DATA):
        self._post, self.send, self.clock, self.data = post, send or (lambda t: None), clock, data
        self.etat = self._load()

    def _load(self):
        try: return json.load(open(os.path.join(self.data, "etat.json")))
        except Exception: return {"meta": {}, "envoyees": {}, "erreurs_api": 0, "cles": {}}

    def _save(self):
        os.makedirs(self.data, exist_ok=True); p = os.path.join(self.data, "etat.json")
        json.dump(self.etat, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)

    def post(self, body):
        if self._post: return self._post(body)
        import requests
        r = requests.post(INFO, json=body, timeout=15); r.raise_for_status(); return r.json()

    def alerte(self, cle, texte):
        now = self.clock(); fam = cle.split(":")[0]
        if now - self.etat["envoyees"].get(cle, 0) < RAPPEL_S.get(fam, 3600): return False
        self.etat["envoyees"][cle] = now
        with open(os.path.join(self.data, "alertes.jsonl"), "a") as f:
            f.write(json.dumps({"t": int(now), "cle": cle, "texte": texte}, ensure_ascii=False) + "\n")
        self.send("🔥 Heraclite, la Sentinelle\n" + texte)
        return True

    def verifier(self):
        actives = []
        try:
            meta, ctxs = self.post({"type": "metaAndAssetCtxs"}); self.etat["erreurs_api"] = 0
        except Exception as ex:
            self.etat["erreurs_api"] += 1
            if self.etat["erreurs_api"] >= 3:
                self.alerte("api", f"API Hyperliquid injoignable depuis {self.etat['erreurs_api']} controles ({type(ex).__name__})"); actives.append("api")
            return actives
        univ = {u["name"]: (u, c) for u, c in zip(meta["universe"], ctxs)}
        avant = self.etat["meta"]; apres = {}
        for coin in SUIVIS:
            if coin not in univ:
                if coin in avant and not avant[coin].get("absent"):
                    self.alerte(f"regle:{coin}:absent", f"{coin} a disparu de la liste des perps Hyperliquid"); actives.append(f"{coin} absent")
                apres[coin] = {"absent": True}; continue
            u, c = univ[coin]
            r = {"levier": int(u.get("maxLeverage") or 0), "decimales": int(u.get("szDecimals") or 0), "delist": bool(u.get("isDelisted")),
                 "isole": bool(u.get("onlyIsolated")), "funding": float(c.get("funding") or 0)}
            a = avant.get(coin)
            if a and not a.get("absent"):
                if r["delist"] and not a.get("delist"): self.alerte(f"regle:{coin}:delist", f"{coin} est DELISTE sur Hyperliquid"); actives.append(f"{coin} deliste")
                if r["levier"] != a.get("levier"): self.alerte(f"regle:{coin}:levier:{r['levier']}", f"{coin} : levier maximum {a.get('levier')}x -> {r['levier']}x")
                if r["decimales"] != a.get("decimales"): self.alerte(f"regle:{coin}:dec:{r['decimales']}", f"{coin} : decimales de taille {a.get('decimales')} -> {r['decimales']}")
                if r["isole"] and not a.get("isole"): self.alerte(f"regle:{coin}:isole", f"{coin} : marge isolee desormais imposee")
            apres[coin] = r
        self.etat["meta"] = apres
        for nom, adr in COMPTES.items():
            if not adr: continue
            try:
                st = self.post({"type": "clearinghouseState", "user": adr}); ordres = self.post({"type": "frontendOpenOrders", "user": adr})
            except Exception: continue
            stops = {o["coin"] for o in ordres if is_stop(o)}
            for ap in st.get("assetPositions", []):
                q = ap["position"]; sz = float(q["szi"])
                if sz == 0: continue
                coin = q["coin"]; f = (apres.get(coin) or {}).get("funding")
                if f is None and coin in univ: f = float(univ[coin][1].get("funding") or 0)
                contre = (f or 0) * (1 if sz > 0 else -1)
                if contre > FUNDING_EXTREME:
                    self.alerte(f"funding:{nom}:{coin}", f"{nom} {coin} : funding {f * 100:+.3f} %/h contre la position"); actives.append(f"funding {coin}")
                if coin not in stops:
                    self.alerte(f"stop:{nom}:{coin}", f"{nom} {coin} : position SANS STOP au carnet"); actives.append(f"{coin} sans stop")
        if self.clock() - self.etat.get("cles_t", 0) >= 6 * 3600:
            self.etat["cles_t"] = self.clock()
            for nom, adr in COMPTES.items():
                if not adr: continue
                try: rows = self.post({"type": "extraAgents", "user": adr}) or []
                except Exception: continue
                fins = [int(r.get("validUntil") or 0) for r in rows if r.get("validUntil")]
                if not fins: continue
                jours = (max(fins) / 1000 - self.clock()) / 86400; self.etat["cles"][nom] = round(jours, 1)
                if jours < CLE_JOURS:
                    self.alerte(f"cle:{nom}", f"{nom} : la cle d'agent expire dans {jours:.0f} jours. A renouveler sur app.hyperliquid.xyz (API).")
        return actives

    def passage(self):
        actives = self.verifier(); self.etat["dernier_controle"] = int(self.clock()); self.etat["actives"] = actives
        self._save(); self.statut()
        return actives

    def statut(self):
        st = {"ts": int(self.clock()), "dernier_controle": self.etat.get("dernier_controle"), "actives": self.etat.get("actives", []),
              "api_ok": self.etat.get("erreurs_api", 0) == 0, "cles_jours": self.etat.get("cles", {}), "suivis": len(SUIVIS)}
        p = os.path.join(self.data, "status.json"); json.dump(st, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)

def telegram(texte):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not (tok and chat): return
    try:
        import requests
        requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": texte[:4000]}, timeout=10)
    except Exception as ex: log.warning("telegram : %s", type(ex).__name__)

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    s = Sentinelle(send=telegram); prochain = 0
    while True:
        if time.time() >= prochain:
            try: log.info("controle : %s", s.passage() or "rien a signaler")
            except Exception as ex: log.warning("controle : %s", type(ex).__name__)
            prochain = time.time() + PERIODE_S
        s.statut(); time.sleep(60)

if __name__ == "__main__":
    main()
