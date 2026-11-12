"""Faux Hyperliquid DÉTERMINISTE pour les tests de l'extension (a)/(b) : sert meta, candleSnapshot (1h, 5m, 15m) et fundingHistory.
Actifs construits pour vérifier la règle d'univers :
  BTC, ETH, SOL : très liquides, peu volatils (toujours inclus par la règle)
  HOT           : liquide ; calme pendant la première moitié de la fenêtre, très volatil ensuite → n'entre qu'en seconde moitié
  THIN          : très volatil mais volume < 5 M$ → jamais
  DEAD          : délisté au milieu de la fenêtre (plus de bougies) → sort de l'univers
  NEW           : coté au milieu de la fenêtre → absent tant qu'il n'a pas 24 bougies 1 h
  F00 … F13     : liquides, volatilité croissante avec l'indice → les plus volatils remplissent l'univers
  xyz:TSLA      : HIP-3 → jamais téléchargé"""
import math, hashlib
import numpy as np

def _seed(*parts): return int(hashlib.sha256('|'.join(map(str, parts)).encode()).hexdigest()[:8], 16)

H, M15, M5 = 3_600_000, 900_000, 300_000
END = 1_793_404_800_000                      # 31/10/2026 00:00 UTC
W0 = END - 5000 * M15
MID = W0 + (END - W0) // 2
FILLERS = [f"F{k:02d}" for k in range(14)]
COINS = ["BTC", "ETH", "SOL", "HOT", "THIN", "DEAD", "NEW"] + FILLERS

def meta():
    u = [{"name": c, "szDecimals": 2, "maxLeverage": 10} for c in COINS]
    u.append({"name": "DEAD2", "szDecimals": 2, "maxLeverage": 3, "isDelisted": True})       # délisté sans historique
    u.append({"name": "xyz:TSLA", "szDecimals": 2, "maxLeverage": 10})
    return {"universe": u}

def sigma_1h(coin, t):
    if coin in ("BTC", "ETH", "SOL"): return 0.002
    if coin == "HOT": return 0.002 if t < MID else 0.05
    if coin == "THIN": return 0.08
    if coin in ("DEAD", "NEW"): return 0.04
    return 0.004 + 0.0015 * int(coin[1:])

def vol_1h(coin):
    return 10.0 if coin == "THIN" else 1e6

def listed(coin, t):
    if coin == "DEAD": return t < MID
    if coin == "NEW": return t >= MID
    if coin == "DEAD2": return False
    return True

def _walk(coin, tf, step, sig_fn, t_from, t_to):
    """Marche aléatoire déterministe : la bougie qui commence à t dépend seulement de (actif, unité, t)."""
    out = []; t = (t_from // step) * step
    while t <= t_to:
        if listed(coin, t):
            rng = np.random.default_rng(_seed(coin, tf, t // step))
            base = 100 * math.exp(0.0001 * ((t // step) % 997)); r = rng.normal(0, sig_fn(t))
            o, c = base, base * math.exp(r)
            out.append({"t": t, "T": t + step - 1, "s": coin, "i": tf, "o": f"{o:.6f}", "c": f"{c:.6f}",
                        "h": f"{max(o, c) * 1.0005:.6f}", "l": f"{min(o, c) * 0.9995:.6f}", "v": f"{vol_1h(coin) if tf == '1h' else 1000:.4f}", "n": 5})
        t += step
    return out

NB_FAST = 260                                # bougies 5 m / 15 m servies par le faux (tests rapides ; le vrai en sert 5000)

def _shocked(coin, tf, step, t_from, t_to):
    """5 m / 15 m : marche + chocs réguliers (signaux rebond_flush / retour_vwap), sur les NB_FAST dernières bougies seulement."""
    n1 = t_to // step; n0 = max(t_from // step, n1 - NB_FAST + 1)
    rng = np.random.default_rng(_seed(coin, tf, "fast"))
    p = 100 * np.exp(np.cumsum(rng.normal(0, 0.002, n1 - n0 + 1)))
    for k in range(130, len(p), 45): p[k:] *= (0.94 if (k // 45) % 2 else 1.07)
    out, prev = [], p[0]
    for j, x in enumerate(p):
        t = (n0 + j) * step
        if not listed(coin, t): prev = x; continue
        out.append({"t": t, "T": t + step - 1, "s": coin, "i": tf, "o": f"{prev:.6f}", "c": f"{x:.6f}",
                    "h": f"{max(prev, x) * 1.001:.6f}", "l": f"{min(prev, x) * 0.999:.6f}", "v": "1000", "n": 5}); prev = x
    return out

class FakeHL:
    def __init__(self, fail_after=None):
        self.calls, self.fail_after = [], fail_after
    def __call__(self, body):
        if self.fail_after is not None and len(self.calls) >= self.fail_after: raise ConnectionError("coupure simulée")
        self.calls.append(body)
        if body["type"] == "meta": return meta()
        if body["type"] == "candleSnapshot":
            q = body["req"]; tf = q["interval"]; step = {"1h": H, "5m": M5, "15m": M15}[tf]
            start = max(q["startTime"], q["endTime"] - 5000 * step)
            if tf == "1h": rows = _walk(q["coin"], tf, step, lambda t, c=q["coin"]: sigma_1h(c, t), start, q["endTime"])
            else: rows = _shocked(q["coin"], tf, step, start, q["endTime"])
            return rows[-5000:]
        if body["type"] == "fundingHistory":
            t = (body["startTime"] + H - 1) // H * H; out = []
            while t <= body["endTime"] and len(out) < 500:
                rate = "0.0001" if body["coin"] in ("F10", "F11", "F12", "F13") else "0.0000125"     # ≈ 88 %/an : funding_contre peut se déclencher
                if listed(body["coin"], t): out.append({"coin": body["coin"], "fundingRate": rate, "premium": "0", "time": t})
                t += H
            return out
        raise ValueError(body)

def build(out, budget=600):
    """Construit un jeu complet via le VRAI script de téléchargement, avec le faux Hyperliquid et une horloge simulée."""
    from peanut import replay_pit_fetch as F
    clk = [END / 1000 + 30]
    def sleep(s): clk[0] += s
    fake = FakeHL()
    F.main(["--out", out, "--budget", str(budget)], post=fake, clock=lambda: clk[0], sleep=sleep)
    return fake
