"""Acces au marche : API REST publique (amorcage, trous) et WebSocket public (flux temps reel). Aucune cle, aucun ordre."""
import json, time, logging, threading, queue

log = logging.getLogger("recolteur.flux")
REST = "https://api.hyperliquid.xyz/info"
WS = "wss://api.hyperliquid.xyz/ws"

class Rest:
    """POST /info avec reessais en attente exponentielle (1 a 60 s) et pause minimale entre appels."""
    def __init__(self, post=None, sleep=time.sleep, pause=0.5, essais=8):
        self._post, self.sleep, self.pause, self.essais = post, sleep, pause, essais

    def post(self, body):
        wait = 1.0
        for k in range(self.essais):
            try:
                if self._post is None:
                    import requests
                    r = requests.post(REST, json=body, timeout=20)
                    if r.status_code == 429: raise RuntimeError("limite de poids")
                    r.raise_for_status(); out = r.json()
                else:
                    out = self._post(body)
                self.sleep(self.pause); return out
            except Exception as ex:
                if k == self.essais - 1: raise
                log.warning("REST %s : %s, nouvel essai dans %.0f s", body.get("type"), type(ex).__name__, wait)
                self.sleep(wait); wait = min(60.0, wait * 2)

    def meta(self):
        meta, ctx = self.post({"type": "metaAndAssetCtxs"})
        return {u["name"]: {"szDecimals": int(u.get("szDecimals", 0)), "delist": bool(u.get("isDelisted"))} for u in meta["universe"]}

    def candles(self, coin, interval, start, end):
        raw = self.post({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": int(start), "endTime": int(end)}}) or []
        out = sorted({int(b["t"]): (int(b["t"]), float(b["o"]), float(b["h"]), float(b["l"]), float(b["c"])) for b in raw}.values())
        return out

def subscriptions(coins):
    subs = [{"type": "candle", "coin": "BTC", "interval": "5m"}]
    for c in coins:
        subs += [{"type": "trades", "coin": c}, {"type": "bbo", "coin": c}, {"type": "l2Book", "coin": c, "nSigFigs": 3},
                 {"type": "candle", "coin": c, "interval": "5m"}, {"type": "activeAssetCtx", "coin": c}]
    return subs

def dispatch(m, msg, recv_ms=None):
    """Transmet un message du WebSocket au moteur. Renvoie le canal traite."""
    ch, d = msg.get("channel"), msg.get("data")
    if ch == "trades":
        for x in d: m.on_trade(x["coin"], int(x["time"]), float(x["px"]), float(x["sz"]), x["side"], recv_ms)
    elif ch == "bbo":
        b, a = (d.get("bbo") or [None, None])[:2]
        if b and a: m.on_bbo(d["coin"], int(d["time"]), float(b["px"]), float(a["px"]))
    elif ch == "l2Book":
        m.on_book(d["coin"], int(d["time"]), [(float(l["px"]), float(l["sz"])) for l in d["levels"][0]])
    elif ch == "candle":
        m.on_candle(d["s"], int(d["t"]), float(d["o"]), float(d["h"]), float(d["l"]), float(d["c"]))
    elif ch == "activeAssetCtx":
        f = (d.get("ctx") or {}).get("funding")
        if f is not None: m.on_funding(d["coin"], float(f))
    return ch

class Flux:
    """WebSocket dans un fil a part : messages poses dans une file, reconnexion en attente exponentielle, ping toutes les 50 s.
    Chaque reconnexion pose un marqueur ("trou", heure locale ms) que la boucle principale traite."""
    def __init__(self, coins, q=None):
        self.subs, self.q = subscriptions(coins), q or queue.Queue(maxsize=200_000)
        self.ws, self.stop, self.connexions = None, threading.Event(), 0

    def _open(self, ws):
        for s in self.subs: ws.send(json.dumps({"method": "subscribe", "subscription": s}))
        self.connexions += 1
        if self.connexions > 1: self.q.put(("trou", int(time.time() * 1000)))
        log.info("WebSocket ouvert (%d abonnements)", len(self.subs))

    def _msg(self, ws, raw):
        try: self.q.put_nowait(("msg", int(time.time() * 1000), raw))
        except queue.Full: self.q.put(("trou", int(time.time() * 1000)))

    def _ping(self):
        while not self.stop.wait(50):
            try:
                if self.ws: self.ws.send(json.dumps({"method": "ping"}))
            except Exception: pass

    def _run(self):
        import websocket
        wait = 1.0
        while not self.stop.is_set():
            t0 = time.time()
            self.ws = websocket.WebSocketApp(WS, on_open=self._open, on_message=self._msg)
            try: self.ws.run_forever(ping_interval=0)
            except Exception as ex: log.warning("WebSocket : %s", type(ex).__name__)
            if time.time() - t0 > 120: wait = 1.0
            log.warning("WebSocket ferme, reconnexion dans %.0f s", wait)
            self.stop.wait(wait); wait = min(60.0, wait * 2)

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._ping, daemon=True).start()

    def kick(self):
        """Force une reconnexion (flux muet)."""
        try: self.ws.close()
        except Exception: pass
