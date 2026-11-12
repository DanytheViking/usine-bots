"""Donnees de marche Hyperliquid (API publique, lecture seule) : contextes des perps, bougies 4 h, prix, arrondis."""
import time, math
import pandas as pd
from . import config as C

class Market:
    def __init__(self, info, clock=time.time):
        if hasattr(info, "timeout"): info.timeout = C.HTTP_TIMEOUT_S
        self.info, self.clock = info, clock
        self._ctx, self._ctx_t = {}, 0.0

    def contexts(self, max_age_s=60) -> dict:
        """{coin: {mark, max_lev, sz_dec, funding_h}} pour les perps validateurs non delistees."""
        if self._ctx and self.clock() - self._ctx_t < max_age_s: return self._ctx
        meta, ctxs = self.info.meta_and_asset_ctxs(); out = {}
        for u, x in zip(meta["universe"], ctxs):
            if u.get("isDelisted") or ":" in u["name"]: continue
            try:
                out[u["name"]] = {"mark": float(x["markPx"]), "max_lev": int(u.get("maxLeverage") or 1), "vol_usd": float(x.get("dayNtlVlm") or 0),
                                  "sz_dec": int(u.get("szDecimals") or 0), "funding_h": float(x.get("funding") or 0)}
            except (KeyError, TypeError, ValueError):
                continue
        self._ctx, self._ctx_t = out, self.clock()
        return out

    def candles(self, coin: str, n: int = C.BARS) -> pd.DataFrame:
        end = int(self.clock() * 1000); start = end - n * C.TF_MS
        raw = self.info.candles_snapshot(coin, C.TF, start, end)
        df = pd.DataFrame(raw).rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "vol"})
        if df.empty: return df
        for c in ("open", "high", "low", "close", "vol"): df[c] = df[c].astype(float)
        df["ts"] = df["ts"].astype("int64")
        return df[["ts", "open", "high", "low", "close", "vol"]].drop_duplicates("ts").sort_values("ts").reset_index(drop=True)

    def mids(self) -> dict:
        return {k: float(v) for k, v in self.info.all_mids().items()}

    def round_px(self, px: float, coin: str) -> float:
        """Prix Hyperliquid : 5 chiffres significatifs et au plus 6 - szDecimals decimales."""
        d = max(0, 6 - self.contexts()[coin]["sz_dec"])
        return float(f"{float(f'{px:.5g}'):.{d}f}")

    def round_sz(self, sz: float, coin: str) -> float:
        d = self.contexts()[coin]["sz_dec"]; return math.floor(sz * 10 ** d + 1e-9) / 10 ** d
