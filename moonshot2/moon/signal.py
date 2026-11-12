"""Signal M2 : croisement EMA 50 / EMA 200 sur bougies 4 h CLOTUREES, stop initial a 3 ATR(14).
Formules identiques a celles du Testeur (usine.strategies.m2_croisement_ema, usine.sim.atr) : EMA classique sans correction
de demarrage, ATR = moyenne simple du true range. Le signal lu a la cloture de la bougie i se joue a l'ouverture de i+1."""
import numpy as np
import pandas as pd
from . import config as C

def atr(df, n=C.ATR_N):
    prev = df.close.shift(1)
    tr = np.maximum(df.high - df.low, np.maximum((df.high - prev).abs(), (df.low - prev).abs()))
    return tr.rolling(n, min_periods=n).mean()

def closed(df: pd.DataFrame, now_ms: int) -> pd.DataFrame:
    """Ne garde que les bougies cloturees a now_ms (la bougie en cours est retiree)."""
    return df[df.ts + C.TF_MS <= now_ms].reset_index(drop=True)

def evaluate(df: pd.DataFrame) -> dict:
    """Etat de la derniere bougie cloturee : croisement ("long", "short" ou None), tendance, ATR, reference de prix."""
    if len(df) < C.EMA_SLOW + 2: return {"cross": None, "trend": None, "atr": None, "ref": None, "bar_ts": None, "raison": "historique insuffisant"}
    f = df.close.ewm(span=C.EMA_FAST, adjust=False).mean().values
    s = df.close.ewm(span=C.EMA_SLOW, adjust=False).mean().values
    a = atr(df).values; i = len(df) - 1
    cross = "long" if f[i] > s[i] and f[i - 1] <= s[i - 1] else "short" if f[i] < s[i] and f[i - 1] >= s[i - 1] else None
    return {"cross": cross, "trend": "long" if f[i] > s[i] else "short", "atr": float(a[i]), "ref": float(df.close.iloc[i]),
            "bar_ts": int(df.ts.iloc[i]), "ema_rapide": float(f[i]), "ema_lente": float(s[i]), "raison": ""}
