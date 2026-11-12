"""Candidat C1 : copie des gros wallets (traqueur de baleines). Hors ligne, aucun ordre.

Selection (uniquement avec les fills ANTERIEURS a la coupe) :
  - au moins 30 fills avec P&L realise sur les 28 jours qui precedent la coupe ;
  - P&L net (P&L realise - frais) positif sur au moins 3 des 4 semaines qui precedent la coupe ;
  - valeur de compte entre 10 000 et 5 000 000 USDC ;
  - teneurs de marche exclus (plus de 80 % de fills maker) ;
  - historique suffisant : le premier fill telecharge est anterieur au debut de ces 28 jours, ou l'historique est complet.
Copie (apres la coupe) : chaque nouvelle position d'un wallet retenu (passage de 0 a une position) sur un actif joue,
avec 60 s de retard approches par un prix d'entree degrade de 0,10 % et une entree taker. Sortie quand le wallet revient
a 0 (prix degrade de 0,10 %), ou stop a 2 ATR(14, 1 h). Le stop est teste des la bougie d'entree (choix pessimiste).
Une seule copie ouverte par actif a la fois."""
from collections import defaultdict
import numpy as np
from .sim import atr, close_trade

H = 3_600_000
DAY = 86_400_000
C1 = {"fills_min": 30, "semaines": 4, "semaines_pos": 3, "compte_min": 10_000, "compte_max": 5_000_000,
      "maker_max": 0.80, "retard_px": 0.001, "stop_atr": 2.0}

def _f(x): return float(x)

def events(fills):
    """Ouvertures et fermetures completes de position, par actif, a partir des fills (startPosition, sz, side B/A)."""
    out = []
    for x in sorted(fills, key=lambda x: (int(x["time"]), str(x.get("tid", "")))):
        c = x["coin"]; start = _f(x["startPosition"]); sz = _f(x["sz"]) * (1 if x["side"] == "B" else -1)
        end = start + sz; t = int(x["time"]); px = _f(x["px"])
        if start != 0 and (end == 0 or np.sign(end) != np.sign(start)):
            out.append({"type": "close", "coin": c, "time": t, "px": px})
        if end != 0 and (start == 0 or np.sign(end) != np.sign(start)):
            out.append({"type": "open", "coin": c, "time": t, "px": px, "side": "long" if end > 0 else "short"})
    return out

def select(wallets, cut):
    """wallets : {adresse: {"fills": [...], "compte": float, "complet": bool}}. Ne lit que les fills de temps < cut."""
    p = C1; t0 = cut - p["semaines"] * 7 * DAY; kept, why = [], {}
    for addr, w in sorted(wallets.items()):
        past = [x for x in w["fills"] if int(x["time"]) < cut]
        if not (p["compte_min"] <= w["compte"] <= p["compte_max"]): why[addr] = "compte hors bornes"; continue
        times = [int(x["time"]) for x in w["fills"]]
        if not w.get("complet") and (not times or min(times) > t0): why[addr] = "historique insuffisant"; continue
        win = [x for x in past if int(x["time"]) >= t0]
        if not win: why[addr] = "aucun fill"; continue
        if sum(1 for x in win if not x.get("crossed", True)) / len(win) > p["maker_max"]: why[addr] = "teneur de marche"; continue
        if sum(1 for x in win if _f(x.get("closedPnl", 0)) != 0) < p["fills_min"]: why[addr] = "trop peu de trades"; continue
        wk = defaultdict(float)
        for x in win: wk[(int(x["time"]) - t0) // (7 * DAY)] += _f(x.get("closedPnl", 0)) - _f(x.get("fee", 0))
        if sum(1 for k in range(p["semaines"]) if wk.get(k, 0) > 0) < p["semaines_pos"]: why[addr] = "pas assez de semaines gagnantes"; continue
        kept.append(addr)
    return kept, why

def copy_trades(wallets, chosen, h1, fund, playable, t_from, t_to):
    """Copie des ouvertures des wallets choisis, de t_from a t_to. playable(coin, t) : actif joue a t."""
    p = C1; evs = []
    for addr in chosen:
        for e in events(wallets[addr]["fills"]):
            if t_from <= e["time"] <= t_to or e["type"] == "close": evs.append({**e, "wallet": addr})
    evs.sort(key=lambda e: (e["time"], e["type"] != "close"))
    closes = defaultdict(list)
    for e in evs:
        if e["type"] == "close": closes[(e["wallet"], e["coin"])].append(e["time"])
    pre = {c: (df, df.ts.values, df.high.values, df.low.values, df.close.values, atr(df).values) for c, df in h1.items()}
    busy_until, trades = {}, []
    for e in evs:
        if e["type"] != "open" or not (t_from <= e["time"] <= t_to): continue
        c = e["coin"]
        if c not in pre or not playable(c, e["time"]) or busy_until.get(c, -1) >= e["time"]: continue
        df, ts, hi, lo, cl, a = pre[c]
        k0 = int(np.searchsorted(ts, e["time"], side="right")) - 1        # bougie 1 h qui contient l'entree
        if k0 < 1 or np.isnan(a[k0 - 1]): continue
        sgn = 1 if e["side"] == "long" else -1
        px = e["px"] * (1 + sgn * p["retard_px"]); dist = p["stop_atr"] * a[k0 - 1]; st = px - sgn * dist
        t_close = next((t for t in closes[(e["wallet"], c)] if t > e["time"]), None)
        base = {"coin": c, "strat": "C1_copie_baleines", "side": e["side"], "signal_ts": int(e["time"]), "stop": st, "tp": None, "wallet": e["wallet"]}
        tr = None
        for k in range(k0, len(ts)):
            hit = (lo[k] <= st) if sgn > 0 else (hi[k] >= st)
            if t_close is not None and ts[k] <= t_close < ts[k] + H and not hit:
                xpx = _px_close(c, e["wallet"], t_close, wallets) * (1 - sgn * p["retard_px"])
                tr = close_trade(base, e["side"], px, dist, xpx, "sortie wallet", e["time"], t_close, fund.get(c), ts, cl); break
            if hit:
                tr = close_trade(base, e["side"], px, dist, st, "STOP", e["time"], int(ts[k]) + H, fund.get(c), ts, cl); break
        if tr is None:
            tr = {**base, "issue": "ouvert en fin de données", "fill_ts": int(e["time"]), "entry": px}
            busy_until[c] = float("inf")
        else:
            busy_until[c] = tr["exit_ts"]
        trades.append(tr)
    return trades

def _px_close(coin, wallet, t, wallets):
    for x in wallets[wallet]["fills"]:
        if x["coin"] == coin and int(x["time"]) == t: return _f(x["px"])
    raise KeyError((coin, wallet, t))
