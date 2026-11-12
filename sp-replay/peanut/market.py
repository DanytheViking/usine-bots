"""Données de marché Hyperliquid (API publique, lecture seule) : univers volatil, bougies, funding.
v0.1.3 (P1-7) : compteur de poids API sur 60 s glissantes, bougies en cache jusqu'à la clôture de la bougie suivante,
mise à jour de l'univers étalée sur plusieurs passages.
Barème officiel (docs Hyperliquid, « Rate limits and user limits ») : 1200 de poids / minute / IP ; info = 20, sauf
l2Book, allMids, clearinghouseState, orderStatus, spotClearinghouseState, exchangeStatus = 2 et userRole = 60 ;
candleSnapshot = 20 + un supplément par tranche de 60 bougies renvoyées ; exchange = 1 + floor(taille du lot / 40)."""
import time, math, collections
import numpy as np, pandas as pd
from . import config as C

TF_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000}
W_INFO, W_LIGHT = 20, 2

class Budget(Exception):
    """Plafond de poids atteint pour un appel discrétionnaire : réessayé au passage suivant."""

class Meter:
    def __init__(self, clock):
        self.clock, self.ev = clock, collections.deque()
    def used(self):
        now = self.clock()
        while self.ev and self.ev[0][0] <= now - 60: self.ev.popleft()
        return sum(w for _, w in self.ev)
    def spend(self, w): self.ev.append((self.clock(), w))
    def allows(self, w): return self.used() + w <= C.API_WEIGHT_PER_MIN

class WeighedInfo:
    """Enveloppe du client Info : compte le poids de CHAQUE appel (y compris ceux du broker). Ne bloque jamais rien ici."""
    LIGHT = {"user_state", "all_mids", "l2_snapshot", "query_order_by_oid", "spot_user_state"}
    def __init__(self, info, meter):
        self._i, self._m = info, meter
    def __getattr__(self, name):
        f = getattr(self._i, name)
        if not callable(f): return f
        def call(*a, **k):
            r = f(*a, **k)
            w = W_LIGHT if name in self.LIGHT else W_INFO
            if name == "candles_snapshot" and isinstance(r, list): w += len(r) // 60
            self._m.spend(w); return r
        return call
    def __setattr__(self, k, v):
        if k in ("_i", "_m"): object.__setattr__(self, k, v)
        else: setattr(self._i, k, v)

class Market:
    def __init__(self, info, clock=time.time):
        if hasattr(info, "timeout"): info.timeout = C.HTTP_TIMEOUT_S
        self.clock, self.meter = clock, Meter(clock)
        self.info = WeighedInfo(info, self.meter)
        self._meta_t, self._ctx, self._cc, self._uni = 0.0, {}, {}, {}

    def contexts(self, max_age_s=60) -> dict:
        """{coin: {mark, funding_h, funding_an, oi_usd, vol_usd, max_lev, sz_dec}} — perps validateurs seulement."""
        if self.clock() - self._meta_t > max_age_s or not self._ctx:
            meta, ctxs = self.info.meta_and_asset_ctxs()
            out = {}
            for u, x in zip(meta["universe"], ctxs):
                if u.get("isDelisted") or ":" in u["name"]: continue           # « dex:COIN » = HIP-3 : exclu
                try:
                    mark = float(x["markPx"]); f = float(x.get("funding") or 0)
                    out[u["name"]] = {"mark": mark, "funding_h": f, "funding_an": f * 24 * 365, "oi_usd": float(x.get("openInterest") or 0) * mark,
                                      "vol_usd": float(x.get("dayNtlVlm") or 0), "max_lev": int(u.get("maxLeverage") or 1),
                                      "sz_dec": int(u.get("szDecimals") or 0), "prev": float(x.get("prevDayPx") or mark)}
                except Exception:
                    continue
            self._ctx, self._meta_t = out, self.clock()
        return self._ctx

    def _fetch(self, coin, tf, n) -> pd.DataFrame:
        end = int(self.clock() * 1000); start = end - n * TF_MS[tf]
        raw = self.info.candles_snapshot(coin, tf, start, end)
        df = pd.DataFrame(raw).rename(columns={"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "vol"})
        if df.empty: return df
        for c in ("open", "high", "low", "close", "vol"): df[c] = df[c].astype(float)
        return df[["ts", "open", "high", "low", "close", "vol"]].sort_values("ts").reset_index(drop=True)

    def candles(self, coin, tf, n=300, discretionary=True) -> pd.DataFrame:
        """En cache tant que la bougie en cours n'est pas clôturée (et au plus une fois / 60 s). Appel discrétionnaire :
        refusé (exception Budget) si le plafond de poids est atteint — le cache, même ancien, reste servi s'il existe."""
        key, now = (coin, tf, n), self.clock()
        hit = self._cc.get(key)
        if hit:
            df, t_fetch = hit
            last = int(df.ts.iloc[-1]) if len(df) else 0
            if now * 1000 < last + TF_MS[tf] or now - t_fetch < 60: return df
        if discretionary and not self.meter.allows(W_INFO + n // 60):
            if hit: return hit[0]
            raise Budget(f"plafond de {C.API_WEIGHT_PER_MIN} de poids/min atteint ({coin} {tf})")
        df = self._fetch(coin, tf, n); self._cc[key] = (df, now); return df

    def universe(self, max_fetch=None) -> list:
        """Les actifs liquides les plus volatils (volatilité 1 h sur ~2 jours), BTC/ETH/SOL toujours inclus.
        Étalé : au plus `max_fetch` actifs re-mesurés par appel ; les scores ont 1 h de validité."""
        max_fetch = C.UNIVERSE_FETCH_PER_PASS if max_fetch is None else max_fetch
        ctx = self.contexts(); now = self.clock()
        liq = sorted([c for c, x in ctx.items() if x["vol_usd"] >= C.MIN_DAY_VOLUME_USD and c not in C.EXCLUDE],
                     key=lambda c: -ctx[c]["vol_usd"])[:40]
        todo = [c for c in liq if now - self._uni.get(c, (None, -1e18))[1] >= 3600][:max_fetch]
        for c in todo:
            if not self.meter.allows(W_INFO): break
            try:
                df = self._fetch(c, "1h", 48)
                score = float(np.diff(np.log(df.close.values)).std() * math.sqrt(24)) if len(df) >= 24 else None
                self._uni[c] = (score, now)
            except Exception:
                self._uni[c] = (None, now)
        scored = [(self._uni[c][0], c) for c in liq if c in self._uni and self._uni[c][0] is not None]
        top = [c for _, c in sorted(scored, reverse=True)[: C.UNIVERSE_SIZE]]
        for base in ("BTC", "ETH", "SOL"):
            if base in ctx and base not in top and base not in C.EXCLUDE: top.append(base)
        return top

    def universe_complete(self) -> bool:
        ctx = self.contexts(); now = self.clock()
        liq = [c for c, x in ctx.items() if x["vol_usd"] >= C.MIN_DAY_VOLUME_USD and c not in C.EXCLUDE]
        liq = sorted(liq, key=lambda c: -ctx[c]["vol_usd"])[:40]
        return all(now - self._uni.get(c, (None, -1e18))[1] < 3600 for c in liq)

    def round_px(self, px: float, coin: str) -> float:
        """Prix Hyperliquid : 5 chiffres significatifs et au plus 6 − szDecimals décimales."""
        d = max(0, 6 - self.contexts()[coin]["sz_dec"])
        return float(f"{float(f'{px:.5g}'):.{d}f}")

    def round_sz(self, sz: float, coin: str) -> float:
        d = self.contexts()[coin]["sz_dec"]; return math.floor(sz * 10 ** d + 1e-9) / 10 ** d
