"""Simulation commune a tous les candidats de l'usine (hors ligne, aucun ordre, aucun reseau).

Regles, identiques pour tous les candidats :
  - le signal est lu sur la bougie CLOTUREE i ; l'entree se fait a l'ouverture de la bougie i+1, au taux taker ;
  - si le stop est deja franchi a l'ouverture d'entree, le trade est annule ;
  - dans chaque bougie, le stop est teste AVANT la cible ;
  - une sortie sur signal (lu a la cloture de k) se fait a l'ouverture de k+1 ;
  - toutes les sorties paient le taux taker, le stop subit un glissement de 0,05 % ;
  - le funding reel est compte a chaque echeance pendant la detention.
Les resultats sont en R : R = distance entre l'entree et le stop initial."""
import numpy as np

FEE_TAKER = 0.00045          # bareme de base Hyperliquid, perps, palier 0 (page Fees, consultee le 31/10/2026)
FEE_MAKER = 0.00015
STOP_SLIP = 0.0005

def atr(df, n=14):
    """ATR simple : moyenne mobile sur n bougies du true range. Valeur en i connue a la cloture de i."""
    prev = df.close.shift(1)
    tr = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    return tr.rolling(n, min_periods=n).mean()

def funding_paid(fund, t_in, t_out, sgn, ts, close):
    """Funding paye pendant ]t_in, t_out] pour 1 unite d'actif ; > 0 = paye. fund = (temps, taux)."""
    if fund is None: return 0.0
    times, rates = fund; total = 0.0
    lo, hi = np.searchsorted(times, t_in, side="right"), np.searchsorted(times, t_out, side="right")
    for t, r in zip(times[lo:hi], rates[lo:hi]):
        k = max(0, int(np.searchsorted(ts, t, side="right")) - 1)
        total += sgn * float(r) * float(close[k])
    return total

def close_trade(base, side, e, R, exit_px, issue, t_in, t_out, fund, ts, close, entry_fee=FEE_TAKER):
    sgn = 1 if side == "long" else -1
    if issue == "STOP": exit_px = exit_px * (1 - STOP_SLIP) if sgn > 0 else exit_px * (1 + STOP_SLIP)
    gross = sgn * (exit_px - e)
    fees = e * entry_fee + exit_px * FEE_TAKER
    fs = funding_paid(fund, t_in, t_out, sgn, ts, close)
    return {**base, "issue": issue, "fill_ts": int(t_in), "exit_ts": int(t_out), "entry": e, "exit": exit_px,
            "R": (gross - fees - fs) / R, "gross_R": gross / R, "fees_R": fees / R, "funding_R": -fs / R}

def run_position(df, i, side, stop_dist, coin, strat, tf_ms, fund, target_dist=None, max_bars=None, exit_fn=None):
    """Position ouverte a l'ouverture de i+1. Renvoie (trade, indice de la derniere bougie occupee) ou (None, i) si pas de bougie suivante.
    stop_dist, target_dist : distances en prix depuis l'entree. exit_fn(k) : True si la cloture de k commande la sortie."""
    n = len(df); j = i + 1
    if j >= n: return None, i
    ts, op, hi, lo, cl = df.ts.values, df.open.values, df.high.values, df.low.values, df.close.values
    sgn = 1 if side == "long" else -1
    e = float(op[j]); st = e - sgn * stop_dist
    tp = e + sgn * target_dist if target_dist else None
    base = {"coin": coin, "strat": strat, "side": side, "signal_ts": int(ts[i]) + tf_ms, "stop": st, "tp": tp}
    if stop_dist <= 0 or not np.isfinite(stop_dist): return {**base, "issue": "annule (stop invalide)"}, i
    R = abs(e - st)
    for k in range(j, n):
        if (lo[k] <= st) if sgn > 0 else (hi[k] >= st):
            return close_trade(base, side, e, R, st, "STOP", ts[j], ts[k] + tf_ms, fund, ts, cl), k
        if tp is not None and ((hi[k] >= tp) if sgn > 0 else (lo[k] <= tp)):
            return close_trade(base, side, e, R, tp, "CIBLE", ts[j], ts[k] + tf_ms, fund, ts, cl), k
        if max_bars and k - j + 1 >= max_bars:
            return close_trade(base, side, e, R, float(cl[k]), "temps max", ts[j], ts[k] + tf_ms, fund, ts, cl), k
        if exit_fn is not None and exit_fn(k):
            if k + 1 >= n: break
            return close_trade(base, side, e, R, float(op[k + 1]), "sortie signal", ts[j], ts[k + 1], fund, ts, cl), k
    return {**base, "issue": "ouvert en fin de données", "fill_ts": int(ts[j]), "entry": e}, n - 1
