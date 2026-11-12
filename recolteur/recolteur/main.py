"""Boucle principale du Recolteur T6 (papier). Amorcage REST, flux WebSocket, trous, statut toutes les 60 s.
    python3 -m recolteur.main"""
import os, sys, json, time, queue, hashlib, logging
from . import config as C, journal as J, notify as N
from .marche import Coin
from .papier import Moteur
from .flux import Rest, Flux, dispatch

log = logging.getLogger("recolteur")
HERE = os.path.dirname(os.path.abspath(__file__))

def empreintes():
    out = {f: hashlib.sha256(open(os.path.join(HERE, f), "rb").read()).hexdigest() for f in sorted(os.listdir(HERE)) if f.endswith(".py")}
    doc = os.path.join(os.path.dirname(HERE), "docs", "MISE-EN-OEUVRE-T6.md")
    if os.path.exists(doc): out["MISE-EN-OEUVRE-T6.md"] = hashlib.sha256(open(doc, "rb").read()).hexdigest()
    return out

def liste(meta):
    return [c for c in C.MEMES if c in meta and not meta[c]["delist"]]

def amorcer(rest, m, now_ms):
    for name, c in m.coins.items():
        c.load_bars(rest.candles(name, "5m", now_ms - 80 * 5 * C.M, now_ms // (5 * C.M) * (5 * C.M)))
    m.btc.load_bars(rest.candles("BTC", "5m", now_ms - 5000 * 5 * C.M, now_ms // (5 * C.M) * (5 * C.M)))

def write_status(m):
    p = os.path.join(C.DATA_DIR, "status.json"); tmp = p + ".tmp"
    json.dump(m.status(), open(tmp, "w"), default=str); os.replace(tmp, p)

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    os.makedirs(C.DATA_DIR, exist_ok=True)
    rest = Rest(); meta = rest.meta(); names = liste(meta)
    jr = J.Journal(); h = empreintes()
    print(f"sha256 MISE-EN-OEUVRE-T6.md : {h.get('MISE-EN-OEUVRE-T6.md')}", flush=True)
    jr.record("demarrage", None, version=C.VERSION, liste=names, empreintes=h, capital_papier=C.CAPITAL)
    m = Moteur({n: Coin(n, meta[n]["szDecimals"]) for n in names}, Coin("BTC"), jr, notify=N.send,
               fetch_1m=lambda coin, a, b: rest.candles(coin, "1m", a, b))
    now = int(time.time() * 1000)
    if m.s.get("dernier_t"): m.gap(int(m.s["dernier_t"]), now)
    amorcer(rest, m, now)
    flux = Flux(names); flux.start()
    N.send(f"Demarrage v{C.VERSION} : {len(names)} memecoins suivis, phase {m.s['phase']}, equite papier {m.s['equite']:.2f} USDC")
    last_status = last_msg = time.time()
    while True:
        try: item = flux.q.get(timeout=1)
        except queue.Empty: item = None
        if item and item[0] == "trou":
            now = item[1]; m.gap(m.clock or now, now); amorcer(rest, m, now)
        elif item:
            last_msg = time.time()
            try: dispatch(m, json.loads(item[2]), item[1])
            except Exception as ex: log.warning("message ignore : %s", type(ex).__name__)
        if time.time() - last_msg > 60:
            log.warning("flux muet depuis 60 s : reconnexion"); flux.kick(); last_msg = time.time()
        if time.time() - last_status >= 60:
            m.s["dernier_t"] = m.clock; m.save(); write_status(m); last_status = time.time()

if __name__ == "__main__":
    sys.exit(main())
