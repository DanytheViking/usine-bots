"""Les failles de marché exploitées par Smart Peanut. Chaque stratégie lit la DERNIÈRE bougie CLÔTURÉE et propose des
candidats ; ce sont les agents qui décident lesquels prendre, et le module de risque qui borne la taille.
  - rebond_flush    : liquidations en cascade sur 5 min (bougie > 2,5 ATR) → on prend le rebond
  - retour_vwap     : excès de plus de 2,5 ATR autour de la VWAP du jour (15 min) → retour vers la VWAP
  - funding_contre  : foule entassée (funding ≥ 60 %/an) dont le prix décroche (15 min) → contre la foule, funding encaissé
Entrée en ordre maker (post-only) un peu mieux que la clôture, stop et cible posés avec l'entrée."""
from dataclasses import dataclass, asdict
import numpy as np, pandas as pd

@dataclass(frozen=True)
class Candidate:
    id: str
    strat: str
    coin: str
    side: str          # long | short
    entry: float
    stop: float
    tp: float
    tf: str
    bar_ts: int
    atr_pct: float
    why: str

    @property
    def rr(self): return abs(self.tp - self.entry) / abs(self.entry - self.stop)
    def to_dict(self): d = asdict(self); d["rr"] = round(self.rr, 2); return d

def ind(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy(); c = df.close
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    tr = pd.concat([df.high - df.low, (df.high - c.shift()).abs(), (df.low - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False).mean()
    day = df.ts // 86_400_000; tp = (df.high + df.low + c) / 3
    df["vwap"] = (tp * df.vol).groupby(day).cumsum() / df.vol.groupby(day).cumsum().replace(0, np.nan)
    return df

def _cand(strat, coin, side, close, atr, k_stop, rr, tf, ts, why, tgt=None, better=0.1):
    e = close - better * atr if side == "long" else close + better * atr       # maker : un peu mieux que la clôture
    s = e - k_stop * atr if side == "long" else e + k_stop * atr
    t = tgt if tgt is not None else (e + rr * k_stop * atr if side == "long" else e - rr * k_stop * atr)
    if (side == "long" and not (s < e < t)) or (side == "short" and not (t < e < s)): return None
    return Candidate(f"{strat}:{coin}:{ts}", strat, coin, side, e, s, t, tf, int(ts), round(atr / close * 100, 3), why)

def rebond_flush(coin, df5, m=2.5):
    if len(df5) < 60: return None
    d = ind(df5); r, a = d.iloc[-2], d.atr.iloc[-3]               # -1 = bougie en cours, -2 = dernière clôturée
    body = r.close - r.open
    if a <= 0: return None
    if -body > m * a: return _cand("rebond_flush", coin, "long", r.close, a, 1.5, 1.5, "5m", r.ts, f"chute de {(-body / a):.1f} ATR en 5 min : liquidations des longs probables")
    if body > m * a:  return _cand("rebond_flush", coin, "short", r.close, a, 1.5, 1.5, "5m", r.ts, f"hausse de {(body / a):.1f} ATR en 5 min : liquidations des shorts probables")
    return None

def retour_vwap(coin, df15, z=2.5):
    if len(df15) < 60: return None
    d = ind(df15); r = d.iloc[-2]
    if not r.atr or np.isnan(r.vwap): return None
    dev = (r.close - r.vwap) / r.atr
    if dev < -z: return _cand("retour_vwap", coin, "long", r.close, r.atr, 1.5, None, "15m", r.ts, f"{dev:.1f} ATR sous la VWAP du jour", tgt=r.vwap)
    if dev > z:  return _cand("retour_vwap", coin, "short", r.close, r.atr, 1.5, None, "15m", r.ts, f"{dev:+.1f} ATR au-dessus de la VWAP du jour", tgt=r.vwap)
    return None

def funding_contre(coin, df15, funding_an, thr=0.60):
    if len(df15) < 60: return None
    d = ind(df15); r, p = d.iloc[-2], d.iloc[-3]
    if funding_an >= thr and r.close < r.ema20 <= p.close:      # longs entassés et le prix casse sous l'EMA 20
        return _cand("funding_contre", coin, "short", r.close, r.atr, 2.0, 2.0, "15m", r.ts, f"funding {funding_an*100:+.0f} %/an payé par les longs, cassure sous EMA20")
    if funding_an <= -thr and r.close > r.ema20 >= p.close:
        return _cand("funding_contre", coin, "long", r.close, r.atr, 2.0, 2.0, "15m", r.ts, f"funding {funding_an*100:+.0f} %/an payé par les shorts, cassure au-dessus d'EMA20")
    return None

def scan(market, coins) -> list:
    ctx = market.contexts(); out = []
    for coin in coins:
        try:
            d5, d15 = market.candles(coin, "5m", 120), market.candles(coin, "15m", 120)
            for c in (rebond_flush(coin, d5), retour_vwap(coin, d15), funding_contre(coin, d15, ctx[coin]["funding_an"])):
                if c: out.append(c)
        except Exception:
            continue
    return out
