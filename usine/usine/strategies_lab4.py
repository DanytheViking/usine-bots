"""Lab v4 « furie » : strategies actives de Smart Peanut (parametres figes par PREREG-lab4-furie, 16/11/2026).
Memes regles de simulation que le reste de l'usine (usine.sim)."""
import datetime as dt
import numpy as np
from .sim import atr, run_position
from .strategies import _flat_loop

M15, H, D = 900_000, 3_600_000, 86_400_000
LIQUIDITE_MIN = 1_000_000.0
L1 = {"boite": 12, "historique": 200, "quantile": 0.20, "atr": 14, "stop_atr_min": 1.0, "cible_R": 2.0, "duree_max": 24}
L1B = {"asie_fin_h": 8, "atr": 14, "stop_atr_min": 1.0, "marge_fin_h": 1}
L2 = {"fenetre": 24, "volume_x": 3.0, "atr": 14, "stop_atr": 1.5, "duree_max": 6}

def liquidite(df, tf_ms):
    """Volume en dollars des 24 h closes a la cloture de chaque bougie."""
    n = D // tf_ms
    return (df.vol * df.close).rolling(n, min_periods=n).sum().values

def _ok_liq(v, i): return not np.isnan(v[i]) and v[i] >= LIQUIDITE_MIN

# ------------------------------------------------------------------ L1 : cassure apres compression
def l1_compression(coin, df, fund, tf_ms, strat):
    p = L1; a = atr(df, p["atr"]).values; cl = df.close.values; liq = liquidite(df, tf_ms)
    hi = df.high.rolling(p["boite"]).max().shift(1); lo = df.low.rolling(p["boite"]).min().shift(1)
    larg = (hi - lo) / df.close.shift(1)
    seuil = larg.rolling(p["historique"], min_periods=p["historique"]).quantile(p["quantile"]).shift(1).values
    hi, lo, larg = hi.values, lo.values, larg.values
    def sig(i):
        if np.isnan(seuil[i]) or np.isnan(a[i]) or larg[i] > seuil[i] or not _ok_liq(liq, i): return None
        if cl[i] > hi[i]: return ("long", max(cl[i] - lo[i], p["stop_atr_min"] * a[i]))
        if cl[i] < lo[i]: return ("short", max(hi[i] - cl[i], p["stop_atr_min"] * a[i]))
        return None
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, strat, tf_ms, fund, target_dist=p["cible_R"] * dist, max_bars=p["duree_max"])
        return tr, k, False
    return _flat_loop(df, p["boite"] + p["historique"], sig, opn)

# ------------------------------------------------------------------ L1b : plage asiatique, cassure pendant la seance americaine
def _dimanche(annee, mois, rang):
    d = dt.date(annee, mois, 1); d += dt.timedelta(days=(6 - d.weekday()) % 7)
    return d + dt.timedelta(weeks=rang - 1)

def heure_ete_us(jour):
    """Heure d'ete americaine : du deuxieme dimanche de mars au premier dimanche de novembre (exclu)."""
    return _dimanche(jour.year, 3, 2) <= jour < _dimanche(jour.year, 11, 1)

def seance_us(jour_ms):
    """(ouverture, fin) de la seance americaine en ms UTC pour le jour UTC qui commence a jour_ms."""
    ete = heure_ete_us(dt.datetime.fromtimestamp(jour_ms / 1000, dt.timezone.utc).date())
    return jour_ms + (13 * H + H // 2 if ete else 14 * H + H // 2), jour_ms + (20 * H if ete else 21 * H)

def l1b_asie_us(coin, df, fund, strat="L1b_asie_us_15m"):
    p = L1B; ts, cl, hi, lo = df.ts.values, df.close.values, df.high.values, df.low.values
    a = atr(df, p["atr"]).values; liq = liquidite(df, M15); trades = []
    if not len(df): return trades
    jour = int(ts[0]) // D * D
    while jour <= int(ts[-1]):
        i0, i8 = np.searchsorted(ts, jour), np.searchsorted(ts, jour + p["asie_fin_h"] * H)
        ouv, fin = seance_us(jour)
        if i8 - i0 == p["asie_fin_h"] * 4:
            ph, pb = float(hi[i0:i8].max()), float(lo[i0:i8].min()); mil = (ph + pb) / 2
            for i in range(int(np.searchsorted(ts, ouv)), int(np.searchsorted(ts, fin - p["marge_fin_h"] * H - M15, side="right"))):
                if np.isnan(a[i]) or not _ok_liq(liq, i): continue
                side = "long" if cl[i] > ph else "short" if cl[i] < pb else None
                if side is None: continue
                if i + 1 >= len(df): break
                nb = int((fin - ts[i + 1]) // M15)
                if nb < 1: break
                dist = max(abs(cl[i] - mil), p["stop_atr_min"] * a[i])
                tr, _ = run_position(df, i, side, dist, coin, strat, M15, fund, max_bars=nb)
                if tr: trades.append(tr)
                break
        jour += D
    return trades

# ------------------------------------------------------------------ L2 : top movers, cassure 24 h avec volume x 3
def l2_top_movers(coin, df, fund, tf_ms=H, strat="L2_top_movers_1h"):
    p = L2; a = atr(df, p["atr"]).values; cl = df.close.values; v = df.vol.values; liq = liquidite(df, tf_ms)
    hh = df.high.rolling(p["fenetre"]).max().shift(1).values; ll = df.low.rolling(p["fenetre"]).min().shift(1).values
    vm = df.vol.rolling(p["fenetre"]).mean().shift(1).values
    def sig(i):
        if np.isnan(hh[i]) or np.isnan(a[i]) or np.isnan(vm[i]) or not _ok_liq(liq, i): return None
        if v[i] < p["volume_x"] * vm[i]: return None
        if cl[i] > hh[i]: return ("long", p["stop_atr"] * a[i])
        if cl[i] < ll[i]: return ("short", p["stop_atr"] * a[i])
        return None
    def opn(i, side, dist):
        tr, k = run_position(df, i, side, dist, coin, strat, tf_ms, fund, max_bars=p["duree_max"])
        return tr, k, False
    return _flat_loop(df, p["fenetre"], sig, opn)

# ------------------------------------------------------------------ capacite du compte
def capacite(trades, max_pos=2):
    """Garde les trades dans l'ordre des entrees tant qu'au plus max_pos positions sont ouvertes en meme temps."""
    pris, ouverts = [], []
    for t in sorted((t for t in trades if "R" in t), key=lambda t: (t["fill_ts"], t["coin"])):
        ouverts = [x for x in ouverts if x > t["fill_ts"]]
        if len(ouverts) < max_pos: pris.append(t); ouverts.append(t["exit_ts"])
    return pris

def croissance(rs, f):
    """Moyenne de ln(1 + f x R) : croissance composee par trade au risque f. -inf si un trade ruine le compte."""
    if not len(rs): return None
    x = 1 + f * np.asarray(rs, float)
    return float("-inf") if (x <= 0).any() else float(np.mean(np.log(x)))
