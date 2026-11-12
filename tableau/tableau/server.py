"""Tableau de bord de l'usine : LECTURE SEULE. Aucune cle, aucun bouton d'ordre, aucune ecriture.
Rassemble en une page qui se met a jour seule :
  - Moonshot v2 (fichiers du bot) : equity, positions, R, arrets, signaux, avis de Fable, chien de garde ;
  - Smart Peanut (fichiers du bot) : etat, KILL, derniers trades ;
  - Hyperliquid en direct (API publique, adresses publiques seulement) : valeur des comptes, positions, ordres, stops ;
  - le Testeur : verdicts des catalogues de l'usine.
Ecoute sur 8090 dans le conteneur, publie sur 127.0.0.1 du VPS et derriere le portail HTTPS (bouton du bot Telegram,
donnees servies seulement si la signature Telegram du compte de Richard est valide). Depuis le Mac, sans Telegram :
    ssh -N -L 8090:127.0.0.1:8090 root@<IP du VPS>      puis      http://localhost:8090"""
import os, json, time, glob, hmac, hashlib, threading, datetime as dt
from urllib.parse import parse_qsl
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

DATA = os.getenv("DATA_ROOT", "/d")
MOON = os.path.join(DATA, "moonshot")
PEANUT = os.path.join(DATA, "peanut")
PEANUT2 = os.path.join(DATA, "peanut2")
RECOLTEUR = os.path.join(DATA, "recolteur")
DEPLOYEUR = os.path.join(DATA, "deployeur")
SENTINELLE = os.path.join(DATA, "sentinelle")
TOKEN, CHAT = os.getenv("TELEGRAM_BOT_TOKEN", ""), str(os.getenv("TELEGRAM_CHAT_ID", ""))
AUTH_MAX_S = 24 * 3600
ACCOUNTS = {"Moonshot": os.getenv("MOON_ACCOUNT", ""), "Smart Peanut": os.getenv("LABO_ACCOUNT", "")}
INFO_URL = "https://api.hyperliquid.xyz/info"
CACHE_S = 20
TF_MS = 4 * 3_600_000

def _json(path, default):
    try: return json.load(open(path))
    except Exception: return default

def tail(path, n, max_bytes=600_000):
    if not os.path.exists(path): return []
    with open(path, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - max_bytes)); lines = f.read().decode("utf-8", "ignore").splitlines()
    if size > max_bytes: lines = lines[1:]
    out = []
    for l in lines[-n:]:
        try: out.append(json.loads(l))
        except ValueError: pass
    return out

def age_s(ts):
    try: return int(time.time() - dt.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())
    except Exception: return None

def downsample(points, n=400):
    if len(points) <= n: return points
    step = len(points) / n
    return [points[int(i * step)] for i in range(n)] + [points[-1]]

def fable_score(journal, closed):
    ops = {(r["data"].get("coin"), r["data"].get("bar_ts")): r["data"]["avis"] for r in journal
           if r.get("stage") == "fable" and r.get("data", {}).get("avis") in ("prendre", "eviter")}
    out = {"prendre": [], "eviter": []}
    for c in closed:
        a = ops.get((c.get("coin"), c.get("bar_ts")))
        if a and c.get("R") is not None: out[a].append(c["R"])
    return {k: {"trades": len(v), "R_moyen": round(sum(v) / len(v), 3) if v else None} for k, v in out.items()}

def moonshot(base=None):
    dossier = base or MOON
    st = _json(os.path.join(dossier, "status.json"), {}); s = _json(os.path.join(dossier, "state.json"), {})
    journal = tail(os.path.join(dossier, "journal.jsonl"), 3000)
    closed = s.get("closed", [])
    ledger = s.get("r_ledger", [])
    peak = cur = dd = 0.0
    for r in ledger: cur += r; peak = max(peak, cur); dd = max(dd, peak - cur)
    streak = 0
    for r in reversed(ledger):
        if r < 0: streak += 1
        else: break
    eq = [[p["t"], p["eq"]] for p in tail(os.path.join(dossier, "equity.jsonl"), 20000) if p.get("eq") is not None]
    now_ms = int(time.time() * 1000)
    events = [{"ts": r.get("ts", ""), "stage": r.get("stage"), "decision": r.get("decision", ""), "reason": r.get("reason", "")} for r in journal
              if r.get("stage") in ("signal", "execution", "cloture", "fable", "risque", "demarrage")][-60:][::-1]
    start = s.get("start_equity")
    return {"status": st, "age_s": age_s(st.get("ts", "")), "positions": s.get("positions", {}), "closed": closed[-30:][::-1],
            "start_equity": start, "line_stop": round(start * 0.5, 2) if start else None, "r_cumule": round(sum(ledger), 3),
            "baisse_R": round(dd, 3), "pertes_affilee": streak, "kill": os.path.exists(os.path.join(dossier, "KILL")),
            "kill_reason": open(os.path.join(dossier, "KILL")).read().strip()[:300] if os.path.exists(os.path.join(dossier, "KILL")) else "",
            "equity": downsample(eq), "events": events, "fable": fable_score(journal, closed),
            "prochaine_cloture_s": int(((now_ms // TF_MS + 1) * TF_MS - now_ms) / 1000),
            "chercheur": sorted(os.path.basename(p) for p in glob.glob(os.path.join(dossier, "chercheur", "bilan-*.md")))[-5:]}

def peanut():
    st = _json(os.path.join(PEANUT, "status.json"), {}); s = _json(os.path.join(PEANUT, "state.json"), {})
    k = os.path.join(PEANUT, "KILL")
    closed = [c for c in s.get("closed", []) if c.get("issue") != "annulé (non rempli)"]
    return {"version": st.get("version"), "age_s": age_s(st.get("ts", "")[:19] + "Z") if st.get("ts") else None,
            "kill": os.path.exists(k), "kill_reason": open(k).read().strip()[:300] if os.path.exists(k) else "",
            "trades": len(closed), "pnl": round(sum(float(c.get("pnl") or 0) for c in closed), 4),
            "gagnants": sum(1 for c in closed if float(c.get("pnl") or 0) > 0), "derniers": closed[-10:][::-1]}

def verdicts():
    out = []
    for p in sorted(glob.glob(os.path.join(DATA, "usine-*", "verdicts.json"))):
        rep = _json(p, {})
        for name, r in rep.get("candidats", {}).items():
            ev = (r.get("evaluation_frais_doubles") or {}).get("global", {})
            out.append({"catalogue": rep.get("specification", "?"), "candidat": name, "verdict": r.get("verdict", "?"),
                        "trades": ev.get("trades"), "pf": ev.get("profit_factor"), "esperance_R": ev.get("esperance_R")})
    return out

def recolteur():
    st = _json(os.path.join(RECOLTEUR, "status.json"), {})
    j = tail(os.path.join(RECOLTEUR, "journal.jsonl"), 4000)
    cas = [r for r in j if r.get("type") == "cascade"]
    sorties = [r["data"] for r in j if r.get("type") == "sortie"]
    return {"status": st, "age_s": int(time.time() - st["ts"]) if st.get("ts") else None,
            "cascades": len(cas), "cascades_completes": sum(1 for r in cas if r["data"].get("signal_complet")),
            "dernieres_cascades": [{"t": r.get("t_hl"), "coin": r["data"].get("coin"), "baisse": r["data"].get("baisse"),
                                    "complet": r["data"].get("signal_complet"), "refus": r["data"].get("refus")} for r in cas[-12:]][::-1],
            "derniers_trades": [{k: t.get(k) for k in ("coin", "issue", "R", "t_sortie", "duree_ms")} for t in sorties[-10:]][::-1],
            "debut": next((r.get("t_hl") for r in j if r.get("type") == "demarrage_mesure"), None)}

def deployeur():
    d = _json(os.path.join(DEPLOYEUR, "etat.json"), {})
    return d or {"absent": True}

def sentinelle():
    st = _json(os.path.join(SENTINELLE, "status.json"), {})
    al = []
    p = os.path.join(SENTINELLE, "alertes.jsonl")
    if os.path.exists(p):
        for l in open(p, encoding="utf-8").read().splitlines()[-15:]:
            try: al.append(json.loads(l))
            except ValueError: pass
    return {"status": st, "age_s": int(time.time() - st["ts"]) if st.get("ts") else None, "alertes": al[::-1]}

def chercheur(base):
    fs = sorted(glob.glob(os.path.join(base, "chercheur", "bilan-*.md")))
    if not fs: return None
    return {"fichier": os.path.basename(fs[-1]), "texte": open(fs[-1], encoding="utf-8", errors="ignore").read()[:4000]}

def visionnaire(base, n=8):
    out = []
    for r in tail(os.path.join(base, "journal.jsonl"), 3000):
        if r.get("stage") == "fable" and r.get("data", {}).get("avis"):
            out.append({"ts": r.get("ts"), "coin": r["data"].get("coin"), "avis": r["data"]["avis"], "raison": (r.get("reason") or "")[:240]})
    return out[-n:][::-1]

def propre(x):
    """JSON strict pour le navigateur : un nombre infini ou indefini devient une chaine (« inf ») ou null."""
    if isinstance(x, float) and x != x: return None
    if isinstance(x, float) and x in (float("inf"), float("-inf")): return "inf" if x > 0 else "-inf"
    if isinstance(x, dict): return {k: propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [propre(v) for v in x]
    return x

def verify_init(init, token=None, chat=None, now=None):
    """Signature Telegram d'une page ouverte depuis le bot : seul le compte de Richard (TELEGRAM_CHAT_ID) est accepte."""
    token, chat = token if token is not None else TOKEN, chat if chat is not None else CHAT
    if not (init and token and chat): return False
    try: data = dict(parse_qsl(init, keep_blank_values=True, strict_parsing=True))
    except ValueError: return False
    h = data.pop("hash", "")
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h): return False
    try:
        if (now or time.time()) - int(data.get("auth_date", "0")) > AUTH_MAX_S: return False
        return str(json.loads(data.get("user", "{}")).get("id")) == chat
    except (ValueError, TypeError): return False

class Exchange:
    """Lecture publique Hyperliquid, mise en cache 20 s pour menager la limite de poids de l'IP (partagee avec les bots)."""
    def __init__(self, post=None, clock=time.time):
        self.post, self.clock, self.t, self.data, self.lock = post, clock, 0.0, {}, threading.Lock()

    def _post(self, body):
        if self.post: return self.post(body)
        import requests
        r = requests.post(INFO_URL, json=body, timeout=10); r.raise_for_status(); return r.json()

    def get(self):
        with self.lock:
            if self.data and self.clock() - self.t < CACHE_S: return self.data
            out = {"comptes": {}, "erreur": None}
            try:
                mids = {k: float(v) for k, v in self._post({"type": "allMids"}).items()}
                for name, addr in ACCOUNTS.items():
                    if not addr: continue
                    st = self._post({"type": "clearinghouseState", "user": addr})
                    orders = self._post({"type": "frontendOpenOrders", "user": addr})
                    stops = {o["coin"] for o in orders if o.get("reduceOnly") and (o.get("isTrigger") and o.get("tpsl") == "sl" or "stop" in str(o.get("orderType", "")).lower())}
                    pos = []
                    for a in st.get("assetPositions", []):
                        q = a["position"]; sz = float(q["szi"])
                        if sz == 0: continue
                        pos.append({"coin": q["coin"], "sens": "long" if sz > 0 else "short", "taille": abs(sz), "entree": float(q.get("entryPx") or 0),
                                    "prix": mids.get(q["coin"]), "pnl": float(q.get("unrealizedPnl") or 0),
                                    "liquidation": float(q["liquidationPx"]) if q.get("liquidationPx") else None, "stop": q["coin"] in stops})
                    out["comptes"][name] = {"adresse": addr[:6] + "..." + addr[-4:], "valeur": float(st["marginSummary"]["accountValue"]),
                                            "positions": pos, "ordres": len(orders)}
                out["prix"] = {c: mids.get(c) for c in ("BTC", "ETH", "SOL", "HYPE", "kPEPE")}
            except Exception as ex:
                out["erreur"] = f"Hyperliquid illisible ({type(ex).__name__})"
                if self.data: out = {**self.data, "erreur": out["erreur"]}
            self.data, self.t = out, self.clock()
            return out

EX = Exchange()

def api():
    p2 = moonshot(PEANUT2) if os.path.exists(os.path.join(PEANUT2, "status.json")) else None
    return {"maintenant": int(time.time()), "moonshot": moonshot(), "peanut": peanut(), "peanut2": p2, "exchange": EX.get(), "verdicts": verdicts(),
            "recolteur": recolteur(), "deployeur": deployeur(), "sentinelle": sentinelle(),
            "controle": _json(os.path.join(DEPLOYEUR, "controle.json"), None),
            "agents": {"chercheur": chercheur(MOON), "visionnaire": visionnaire(MOON) + (visionnaire(PEANUT2) if p2 else [])}}

PAGE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "page.html"), "rb").read()

class Handler(BaseHTTPRequestHandler):
    def autorise(self):
        """En local (tunnel SSH, port 127.0.0.1) : libre. Via le portail HTTPS (en-tete X-Forwarded-For) : signature Telegram exigee."""
        if not self.headers.get("X-Forwarded-For"): return True
        return verify_init(self.headers.get("X-Telegram-Init", ""))

    def do_GET(self):
        if self.path.startswith("/api/") and not self.autorise():
            self.send_response(403); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(b'{"erreur": "acces reserve"}'); return
        if self.path.startswith("/api/etat"):
            body = json.dumps(propre(api()), default=str, allow_nan=False).encode(); ctype = "application/json"
        elif self.path in ("/", "/index.html"):
            body, ctype = PAGE, "text/html; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' https://telegram.org; frame-ancestors https://web.telegram.org 'self'")
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

def main():
    ThreadingHTTPServer(("0.0.0.0", 8090), Handler).serve_forever()

if __name__ == "__main__":
    main()
