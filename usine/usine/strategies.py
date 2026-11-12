"""Catalogue v1 de l'usine : candidats M1, M2 (ligne Moonshot) et P1, P2 (ligne Smart Peanut).
Parametres figes par le pre-enregistrement PREREG-usine-catalogue-v1 (09/11/2026). Aucune optimisation."""
import numpy as np
from .sim import atr, run_position

H = 3_600_000
H4 = 4 * H

# ------------------------------------------------------------------ parametres figes
M1 = {"entree": 20, "sortie": 10, "stop_atr": 2.0}
M2 = {"rapide": 50, "lente": 200, "stop_atr": 3.0}
P1 = {"canal": 24, "volume_x": 2.0, "stop_atr": 1.5, "cible_atr": 3.0, "duree_max": 24}
P2 = {"rendement": 24, "ema": 50, "nb": 2, "stop_atr": 2.0, "duree": 4, "pas_h": 4}

def _flat_loop(df, start, signal_at, open_at):
    """Boucle commune : une seule position par actif. signal_at(i) -> (sens, distance stop) ou None ;
    open_at(i, sens, dist) -> (trade, k_fin, fin_sur_signal)."""
    trades, i, n = [], start, len(df)
    while i < n - 1:
        s = signal_at(i)
        if not s: i += 1; continue
        tr, k, on_signal = open_at(i, *s)
        if tr is None: break
        trades.append(tr)
        i = k if on_signal else k + 1
    return trades

# ------------------------------------------------------------------ M1 : cassure de canal de Donchian, 4 h
def m1_cassure_donchian(coin, df, fund, tf_ms=H4):
    p = M1; a = atr(df).values; cl = df.close.values
    hh = df.high.rolling(p["entree"]).max().shift(1).values; ll = df.low.rolling(p["entree"]).min().shift(1).values
    hx = df.high.rolling(p["sortie"]).max().shift(1).values; lx = df.low.rolling(p["sortie"]).min().shift(1).values
    def sig(i):
        if np.isnan(hh[i]) or np.isnan(a[i]): return None
        if cl[i] > hh[i]: return ("long", p["stop_atr"] * a[i])
        if cl[i] < ll[i]: return ("short", p["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        ex = (lambda k: cl[k] < lx[k]) if side == "long" else (lambda k: cl[k] > hx[k])
        tr, k = run_position(df, i, side, dist, coin, "M1_cassure_donchian_4h", tf_ms, fund, exit_fn=ex)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return _flat_loop(df, p["entree"], sig, opn)

# ------------------------------------------------------------------ M2 : croisement EMA 50 / 200, 4 h
def m2_croisement_ema(coin, df, fund, tf_ms=H4):
    p = M2; a = atr(df).values
    f = df.close.ewm(span=p["rapide"], adjust=False).mean().values
    s = df.close.ewm(span=p["lente"], adjust=False).mean().values
    up = lambda i: f[i] > s[i] and f[i - 1] <= s[i - 1]
    dn = lambda i: f[i] < s[i] and f[i - 1] >= s[i - 1]
    def sig(i):
        if np.isnan(a[i]): return None
        if up(i): return ("long", p["stop_atr"] * a[i])
        if dn(i): return ("short", p["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, "M2_croisement_ema_4h", tf_ms, fund, exit_fn=dn if side == "long" else up)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return _flat_loop(df, p["lente"], sig, opn)

# ------------------------------------------------------------------ P1 : cassure 1 h avec pic de volume, univers point dans le temps
def p1_cassure_volume(coin, df, fund, is_member, t_from, tf_ms=H):
    """is_member(coin, t_scan) : appartenance a l'univers au moment du scan (cloture de la bougie i)."""
    p = P1; a = atr(df).values; cl = df.close.values; v = df.vol.values; ts = df.ts.values
    hh = df.high.rolling(p["canal"]).max().shift(1).values; ll = df.low.rolling(p["canal"]).min().shift(1).values
    vm = df.vol.rolling(p["canal"]).mean().shift(1).values
    def sig(i):
        t_scan = int(ts[i]) + tf_ms
        if t_scan < t_from or np.isnan(hh[i]) or np.isnan(a[i]) or np.isnan(vm[i]): return None
        if v[i] <= p["volume_x"] * vm[i]: return None
        side = "long" if cl[i] > hh[i] else "short" if cl[i] < ll[i] else None
        if side is None or not is_member(coin, t_scan): return None
        return (side, p["stop_atr"] * a[i])
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, "P1_cassure_volume_1h", tf_ms, fund,
                             target_dist=p["cible_atr"] * dist / p["stop_atr"], max_bars=p["duree_max"])
        return tr, k, False
    return _flat_loop(df, p["canal"], sig, opn)

# ------------------------------------------------------------------ P2 : rotation sur les plus forts, toutes les 4 h
def p2_rotation_momentum(h1, fund, universe_at, t_from, t_to, tf_ms=H):
    """h1 : {actif: bougies 1 h}. universe_at(h) : univers calcule a l'heure pleine h. Rebalancement aux heures multiples de 4 h UTC."""
    p = P2; prep = {}
    for coin, df in h1.items():
        prep[coin] = (df, df.ts.values, df.close.values, atr(df).values, df.close.ewm(span=p["ema"], adjust=False).mean().values)
    trades = []; h = ((t_from + H4 - 1) // H4) * H4
    while h <= t_to:
        cands = []
        for coin in universe_at(h):
            if coin not in prep: continue
            df, ts, cl, a, em = prep[coin]
            k = int(np.searchsorted(ts, h - tf_ms))
            if k >= len(ts) or ts[k] != h - tf_ms or k < p["rendement"] or np.isnan(a[k]): continue
            r = cl[k] / cl[k - p["rendement"]] - 1
            if r > 0 and cl[k] > em[k]: cands.append((r, coin, k))
        for r, coin, k in sorted(cands, reverse=True)[:p["nb"]]:
            df, ts, cl, a, em = prep[coin]
            tr, _ = run_position(df, k, "long", p["stop_atr"] * a[k], coin, "P2_rotation_momentum_4h", tf_ms, fund.get(coin), max_bars=p["duree"])
            if tr: trades.append(tr)
        h += p["pas_h"] * H
    return trades
