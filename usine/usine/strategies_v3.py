"""Catalogue v3, ligne Chasseur : T1 a T5 (parametres figes par PREREG-usine-catalogue-v3-chasseur, 12/11/2026).
Memes regles de simulation que les v1/v2 (usine.sim) : signal sur bougie close, entree taker a l'ouverture suivante,
stop teste avant la cible, sortie sur signal a l'ouverture suivante, funding reel."""
import numpy as np
from .sim import atr, run_position
from .strategies import _flat_loop

H, H4, D = 3_600_000, 4 * 3_600_000, 24 * 3_600_000
T1 = {"entree": 55, "sortie": 20, "atr": 20, "stop_atr": 2.0}
T3 = {"rendement_bars": 42, "ema": 50, "atr": 14, "stop_atr": 3.0, "duree_bars": 42}
T4 = {"funding_seuil": 0.0005, "heures": 3, "hausse": 0.30, "hausse_bars": 72, "atr": 14, "stop_atr": 2.0, "sortie_funding": 0.0001, "duree_max": 48}
T5 = {"attente_bars": 24, "duree_bars": 72, "atr": 14, "stop_atr": 2.0}

def _donchian(coin, df, fund, strat, allow=None):
    p = T1; a = atr(df, p["atr"]).values; cl = df.close.values; ts = df.ts.values
    hh = df.high.rolling(p["entree"]).max().shift(1).values; ll = df.low.rolling(p["entree"]).min().shift(1).values
    hx = df.high.rolling(p["sortie"]).max().shift(1).values; lx = df.low.rolling(p["sortie"]).min().shift(1).values
    def sig(i):
        if np.isnan(hh[i]) or np.isnan(a[i]): return None
        side = "long" if cl[i] > hh[i] else "short" if cl[i] < ll[i] else None
        if side is None or (allow and not allow(side, int(ts[i]) + H4)): return None
        return (side, p["stop_atr"] * a[i])
    def opn(i, side, dist):
        ex = (lambda k: cl[k] < lx[k]) if side == "long" else (lambda k: cl[k] > hx[k])
        tr, k = run_position(df, i, side, dist, coin, strat, H4, fund, exit_fn=ex)
        return tr, k, bool(tr) and tr.get("issue") == "sortie signal"
    return _flat_loop(df, p["entree"], sig, opn)

def t1_tortue(coin, df, fund):
    return _donchian(coin, df, fund, "T1_tortue")

def btc_regime(btc_d):
    """Fonction (sens, t) -> autorise : long si la derniere cloture journaliere de BTC connue a t est au-dessus de sa SMA 200."""
    ts = btc_d.ts.values; cl = btc_d.close.values; sma = btc_d.close.rolling(200).mean().values
    def allow(side, t):
        k = int(np.searchsorted(ts + D, t, side="right")) - 1           # derniere bougie journaliere CLOSE a t
        if k < 0 or np.isnan(sma[k]): return False
        return (cl[k] > sma[k]) if side == "long" else (cl[k] < sma[k])
    return allow

def t2_tortue_disciplinee(coin, df, fund, allow):
    return _donchian(coin, df, fund, "T2_tortue_disciplinee", allow)

def t3_druckenmiller(bars4h, fund, t_from, t_to):
    """Chaque lundi 00:00 UTC : long du memecoin au meilleur rendement 7 jours (> 0, cloture 4 h > EMA 50), tenu 7 jours."""
    p = T3; prep = {c: (df, df.ts.values, df.close.values, atr(df, p["atr"]).values, df.close.ewm(span=p["ema"], adjust=False).mean().values)
                    for c, df in bars4h.items()}
    monday0 = 4 * D                                                          # 1970-01-05 est un lundi
    t = monday0 + ((t_from - monday0 + 7 * D - 1) // (7 * D)) * 7 * D; trades = []
    while t <= t_to:
        best = None
        for coin, (df, ts, cl, a, em) in prep.items():
            k = int(np.searchsorted(ts, t - H4))
            if k >= len(ts) or ts[k] != t - H4 or k < p["rendement_bars"] or np.isnan(a[k]): continue
            r = cl[k] / cl[k - p["rendement_bars"]] - 1
            if r > 0 and cl[k] > em[k] and (best is None or r > best[0]): best = (r, coin, k)
        if best:
            r, coin, k = best; df, ts, cl, a, em = prep[coin]
            tr, _ = run_position(df, k, "long", p["stop_atr"] * a[k], coin, "T3_druckenmiller", H4, fund.get(coin), max_bars=p["duree_bars"])
            if tr: trades.append(tr)
        t += 7 * D
    return trades

def t4_contrarien(coin, df1h, fund):
    """Short si le funding horaire depasse 0,05 % trois heures de suite ET hausse > 30 % en 72 h ; sortie funding < 0,01 % ou 48 h."""
    p = T4; ts = df1h.ts.values; cl = df1h.close.values; a = atr(df1h, p["atr"]).values
    times, rates = fund if fund is not None else (np.array([], dtype="int64"), np.array([]))
    rate_at = {int(t) // H * H: float(r) for t, r in zip(times, rates)}
    def fr(i): return rate_at.get((int(ts[i]) + H) // H * H)                # funding regle a la cloture de la bougie i
    def sig(i):
        if i < p["hausse_bars"] or np.isnan(a[i]): return None
        last = [fr(j) for j in range(i - p["heures"] + 1, i + 1)]
        if any(x is None or x <= p["funding_seuil"] for x in last): return None
        if cl[i] / cl[i - p["hausse_bars"]] - 1 <= p["hausse"]: return None
        return ("short", p["stop_atr"] * a[i])
    def opn(i, side, dist):
        ex = lambda k: (fr(k) is not None and fr(k) < p["sortie_funding"])
        tr, k = run_position(df1h, i, side, dist, coin, "T4_contrarien", H, fund, max_bars=p["duree_max"], exit_fn=ex)
        return tr, k, False
    return _flat_loop(df1h, p["hausse_bars"], sig, opn)

def t5_listings(coin, df1h, fund, listed_ms):
    """24 h apres la premiere bougie du listing : long si cloture > ouverture du listing, short sinon ; 72 h ou stop 2 ATR(14, 1 h)."""
    p = T5
    if df1h.empty or int(df1h.ts.iloc[0]) > listed_ms + H: return []
    i = int(np.searchsorted(df1h.ts.values, listed_ms + p["attente_bars"] * H - H))
    if i >= len(df1h) - 1: return []
    a = atr(df1h, p["atr"]).values[i]
    if np.isnan(a): return []
    side = "long" if df1h.close.values[i] > df1h.open.values[0] else "short"
    tr, _ = run_position(df1h, i, side, p["stop_atr"] * a, coin, "T5_listings", H, fund, max_bars=p["duree_bars"])
    return [tr] if tr else []
