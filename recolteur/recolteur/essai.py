"""Essai reseau avant lancement : API REST (meta, bougies) et 30 s de flux WebSocket sur WIF et BTC, messages passes au decodeur.
Aucune ecriture dans les donnees du Recolteur, aucun ordre.
    python3 -m recolteur.essai"""
import sys, json, time, queue
from collections import Counter
from .flux import Rest, Flux, dispatch
from . import main as MAIN

class Compteur:
    def __init__(self): self.n = Counter(); self.ex = {}
    def _k(self, k, *a): self.n[k] += 1; self.ex.setdefault(k, a)
    def on_trade(self, *a): self._k("trades", *a)
    def on_bbo(self, *a): self._k("bbo", *a)
    def on_book(self, coin, t, bids): self._k("l2Book", coin, t, len(bids), bids[:2])
    def on_candle(self, *a): self._k("candle", *a)
    def on_funding(self, *a): self._k("activeAssetCtx", *a)

def main(duree=30):
    rest = Rest(); meta = rest.meta(); names = MAIN.liste(meta)
    print(f"REST meta : {len(meta)} perps ; memecoins suivis : {len(names)} ({', '.join(names)})")
    now = int(time.time() * 1000)
    b = rest.candles("WIF", "5m", now - 20 * 300_000, now); print(f"REST bougies 5 min WIF : {len(b)} (derniere {b[-1] if b else None})")
    f = Flux(["WIF"]); f.subs = [s for s in f.subs if s.get("coin") in ("WIF", "BTC")]; f.start()
    c, t0, errors = Compteur(), time.time(), 0
    while time.time() - t0 < duree:
        try: item = f.q.get(timeout=1)
        except queue.Empty: continue
        if item[0] != "msg": continue
        try: dispatch(c, json.loads(item[2]), item[1])
        except Exception as ex: errors += 1; print("message non decode :", type(ex).__name__, item[2][:200])
    f.stop.set()
    for k in ("trades", "bbo", "l2Book", "candle", "activeAssetCtx"): print(f"{k:<15} {c.n[k]:>6} messages  exemple : {c.ex.get(k)}")
    ok = errors == 0 and all(c.n[k] > 0 for k in ("bbo", "l2Book", "candle", "activeAssetCtx"))
    print("ESSAI OK" if ok else "ESSAI EN ECHEC")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
