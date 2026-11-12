"""Execution : LiveBroker (Hyperliquid reel) et ObservationBroker (positions virtuelles, aucun ordre), meme interface.
Regles reprises des bots precedents :
  - levier envoye puis RELU avant l'entree, sinon aucun ordre ;
  - entree (IOC) et stop (declencheur reduce-only, au marche) envoyes dans le MEME lot ;
  - reponse du lot perdue : KILL ; positions illisibles : jamais consideree a plat ;
  - sortie sure : fermer d'abord, annuler ensuite ; si la position reste inconnue : KILL, le stop reste en place."""
import os, time, datetime as dt
from . import config as C, journal as J, notify as N

def kill(reason: str):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    open(C.KILL_SWITCH, "w").write(f"{dt.datetime.now(dt.timezone.utc).isoformat()[:19]}Z {reason}\n")
    J.record("risque", "kill", reason)
    N.send(f"🛑 ARRET (KILL)\n{reason}\nPlus aucune nouvelle entree. Les positions gardent leur stop.")

def is_stop(o) -> bool:
    return bool(o.get("reduceOnly") and ((o.get("isTrigger") and o.get("tpsl") == "sl") or "stop" in str(o.get("orderType", "")).lower()))

def _settle_r(p, pnl):
    return round(pnl / p["risk_usd"], 4) if p.get("risk_usd") else None

# ======================================================================== observation
class ObservationBroker:
    mode = "observation"
    def __init__(self, market, state, start_equity):
        self.m, self.s = market, state
        self.s.setdefault("virtual_equity", float(start_equity))

    def equity(self):
        try: mids = self.m.mids()
        except Exception: mids = {}
        up = 0.0
        for c, p in self.s["positions"].items():
            px = mids.get(c, p["entry"]); up += p["sz"] * (px - p["entry"]) * (1 if p["side"] == "long" else -1)
        return self.s["virtual_equity"] + up

    def positions(self):
        return {c: p["sz"] * (1 if p["side"] == "long" else -1) for c, p in self.s["positions"].items()}

    def open(self, coin, side, sz, lev, ref, stop_px):
        e = ref
        self.s["virtual_equity"] -= sz * e * C.FEE_TAKER
        return {"entry": e, "sz": sz, "stop": stop_px, "fee_in": sz * e * C.FEE_TAKER}

    def close(self, coin, reason, px=None):
        p = self.s["positions"].pop(coin)
        if px is None: px = self.m.mids().get(coin, p["entry"])
        sgn = 1 if p["side"] == "long" else -1
        pnl = sz_pnl = p["sz"] * (px - p["entry"]) * sgn - p["sz"] * px * C.FEE_TAKER
        self.s["virtual_equity"] += sz_pnl
        total = pnl - p.get("fee_in", 0.0)
        return {"coin": coin, "side": p["side"], "issue": reason, "entry": p["entry"], "exit": px, "pnl": round(total, 6), "R": _settle_r(p, total), "bar_ts": p.get("bar_ts")}

    def manage(self):
        """Stop virtuel : teste sur le prix median a chaque passage (le stop reel, lui, est sur l'exchange)."""
        closed = []
        try: mids = self.m.mids()
        except Exception: return closed
        for c, p in list(self.s["positions"].items()):
            px = mids.get(c)
            if px is None: continue
            hit = px <= p["stop"] if p["side"] == "long" else px >= p["stop"]
            if hit: closed.append(self.close(c, "STOP", p["stop"] * (1 - 0.0005 if p["side"] == "long" else 1 + 0.0005)))
        return closed

# ======================================================================== reel
class LiveBroker:
    mode = "reel"
    def __init__(self, market, state, exchange, sleep=time.sleep):
        self.m, self.s, self.x, self.info, self.sleep = market, state, exchange, market.info, sleep
        for api in (self.x, getattr(self.x, "info", None)):
            if api is not None and hasattr(api, "timeout"): api.timeout = C.HTTP_TIMEOUT_S

    def equity(self):
        try: return float(self.info.user_state(C.HL_ACCOUNT)["marginSummary"]["accountValue"])
        except Exception: return None

    def positions(self):                       # leve si illisible : l'appelant traite « inconnu »
        st = self.info.user_state(C.HL_ACCOUNT)
        return {p["position"]["coin"]: float(p["position"]["szi"]) for p in st.get("assetPositions", []) if float(p["position"]["szi"]) != 0}

    def orders(self, coin):
        return [o for o in self.info.frontend_open_orders(C.HL_ACCOUNT) if o.get("coin") == coin]

    def confirm_leverage(self, coin, lev):
        r = self.x.update_leverage(lev, coin, is_cross=False)
        if not (isinstance(r, dict) and r.get("status") == "ok"): raise RuntimeError(f"levier {lev}x refuse ({str(r)[:100]})")
        d = self.info.post("/info", {"type": "activeAssetData", "user": C.HL_ACCOUNT, "coin": coin}) or {}
        lu = ((d.get("leverage") or {}).get("type"), int((d.get("leverage") or {}).get("value", 0) or 0))
        if lu != ("isolated", lev): raise RuntimeError(f"levier non confirme : lu {lu}, attendu ('isolated', {lev})")

    def open(self, coin, side, sz, lev, ref, stop_px):
        """Entree IOC au plus a ref +/- 1 % et stop au marche dans le meme lot. Renvoie None si rien n'a ete rempli."""
        if os.path.exists(C.KILL_SWITCH): raise RuntimeError("KILL present")
        buy = side == "long"
        sz = self.m.round_sz(sz, coin)
        if sz <= 0: raise RuntimeError("taille nulle apres arrondi")
        lim = self.m.round_px(ref * (1 + C.ENTRY_SLIPPAGE if buy else 1 - C.ENTRY_SLIPPAGE), coin)
        sl = self.m.round_px(stop_px, coin)
        self.confirm_leverage(coin, lev)
        orders = [{"coin": coin, "is_buy": buy, "sz": sz, "limit_px": lim, "order_type": {"limit": {"tif": "Ioc"}}, "reduce_only": False},
                  {"coin": coin, "is_buy": not buy, "sz": sz, "limit_px": sl, "order_type": {"trigger": {"triggerPx": sl, "isMarket": True, "tpsl": "sl"}}, "reduce_only": True}]
        J.record("execution", "intent", f"{side} {coin} {sz} IOC limite {lim}, stop {sl}, levier {lev}", orders=orders)
        try:
            res = self.x.bulk_orders(orders, grouping="normalTpsl")
        except Exception as ex:
            kill(f"lot {coin} envoye, reponse perdue ({type(ex).__name__}) : verification manuelle")
            raise
        st = (res or {}).get("response", {}).get("data", {}).get("statuses", [])
        errs = [x["error"] for x in st if isinstance(x, dict) and "error" in x]
        if (res or {}).get("status") != "ok":
            self.safe_exit(coin, f"lot refuse : {res}"); raise RuntimeError(f"lot refuse : {str(res)[:200]}")
        try: pos = self.positions().get(coin, 0.0)
        except Exception:
            kill(f"{coin} : position illisible juste apres l'entree, stop envoye dans le lot"); raise
        if not pos:
            self._cancel_all(coin)
            J.record("execution", "non rempli", f"{coin} : entree IOC non remplie ({errs or 'aucun remplissage'}), ordres annules")
            return None
        if errs or not any(is_stop(o) for o in self.orders(coin)):
            self.safe_exit(coin, f"position ouverte sans stop confirme ({errs})"); raise RuntimeError(f"stop absent : {errs}")
        fill = (st[0] or {}).get("filled", {}) if st and isinstance(st[0], dict) else {}
        e = float(fill.get("avgPx") or ref)
        return {"entry": e, "sz": abs(pos), "stop": sl, "fee_in": 0.0}

    def _cancel_all(self, coin):
        for o in self.orders(coin):
            try: self.x.cancel(coin, o["oid"])
            except Exception: pass

    def close(self, coin, reason, px=None):
        p = self.s["positions"][coin]; t0 = int(p.get("opened_ms", 0))
        if not self.safe_exit(coin, reason): raise RuntimeError(f"sortie {coin} impossible")
        return self._settle(coin, reason, t0)

    def safe_exit(self, coin, reason):
        steps, known = [], False
        for _ in range(3):
            try: pos = self.positions().get(coin); known = True
            except Exception as ex: steps.append(f"positions illisibles : {type(ex).__name__}"); known = False; self.sleep(2); continue
            if not pos: break
            try: self.x.market_close(coin); steps.append("cloture market_close")
            except Exception as ex: steps.append(f"cloture : {type(ex).__name__}")
            self.sleep(2)
        try: flat = not self.positions().get(coin); known = True
        except Exception: flat, known = False, False
        if flat and known:
            self._cancel_all(coin)
            J.record("execution", "sortie", f"{coin} : {reason} : position fermee puis ordres annules", steps=steps); return True
        kill(f"sortie sure {coin} impossible ({reason}) : position inconnue ou ouverte, stop conserve")
        return False

    def _settle(self, coin, issue, since_ms):
        p = self.s["positions"].pop(coin)
        fills = [f for f in self.info.user_fills_by_time(C.HL_ACCOUNT, since_ms) if f.get("coin") == coin]
        pnl = sum(float(f.get("closedPnl", 0)) - float(f.get("fee", 0)) for f in fills)
        ex_px = next((float(f["px"]) for f in reversed(fills) if str(f.get("dir", "")).startswith("Close")), None)
        return {"coin": coin, "side": p["side"], "issue": issue, "entry": p["entry"], "exit": ex_px, "pnl": round(pnl, 6), "R": _settle_r(p, pnl), "bar_ts": p.get("bar_ts")}

    def manage(self):
        """Positions suivies : disparues sur l'exchange (stop touche) -> soldees depuis les fills ; sans stop au carnet -> sortie sure.
        Positions non suivies (orphelines) : sans stop -> sortie sure, avec stop -> entrees bloquees."""
        closed = []
        try: live = self.positions()
        except Exception as ex:
            J.record("execution", "erreur", f"positions illisibles ({type(ex).__name__}) : rien n'est touche"); return closed
        for coin, p in list(self.s["positions"].items()):
            try:
                if coin not in live:
                    self._cancel_all(coin); closed.append(self._settle(coin, "STOP (ou fermeture exchange)", int(p.get("opened_ms", 0)))); continue
                if not any(is_stop(o) for o in self.orders(coin)):
                    if self.safe_exit(coin, "position sans stop au carnet"): closed.append(self._settle(coin, "sortie sure (stop absent)", int(p.get("opened_ms", 0))))
            except Exception as ex:
                J.record("execution", "erreur", f"gestion {coin} : {type(ex).__name__}, nouvel essai au prochain passage")
        found = []
        for coin in live:
            if coin in self.s["positions"]: continue
            try: has_stop = any(is_stop(o) for o in self.orders(coin))
            except Exception: has_stop = False
            if not has_stop and self.safe_exit(coin, "position hors suivi sans stop"): continue
            found.append(coin)
        if sorted(found) != self.s.get("orphans", []) and found:
            N.send(f"⚠ Position(s) hors suivi : {', '.join(found)}. Nouvelles entrees bloquees jusqu'a leur fermeture.")
        self.s["orphans"] = sorted(found)
        return closed
