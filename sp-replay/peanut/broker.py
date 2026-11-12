"""Exécution : LiveBroker (Hyperliquid réel) et PaperBroker (simulation sur les vraies bougies 1 min, même interface).
Règles apprises sur Apex et reprises telles quelles :
  - levier envoyé UNE fois puis RELU (activeAssetData) avant l'entrée, sinon aucun ordre ;
  - entrée, stop et cible dans le MÊME lot (normalTpsl) ; entrée en post-only (maker) ;
  - réponse du lot perdue → KILL ; positions illisibles = position inconnue → jamais « à plat », KILL ;
  - délai maximal sur chaque appel REST ; sortie sûre = fermer d'abord, annuler ensuite."""
import os, time, json, datetime as dt
from . import config as C, journal as J, notify as N

def kill(reason: str):
    os.makedirs(C.DATA_DIR, exist_ok=True)
    open(C.KILL_SWITCH, "w").write(f"{dt.datetime.now(dt.timezone.utc).isoformat()} {reason}\n")
    J.record("risque", "kill", reason)
    N.send(f"🛑 ARRÊT D'URGENCE (KILL)\n{reason}\nPlus aucune nouvelle entrée. Les positions gardent leur stop.")

KEYS = ("id", "strat", "side", "entry", "stop", "tp", "sz", "risk_usd")
def _keys(p): return {k: p.get(k) for k in KEYS}

def is_stop(o) -> bool:
    return bool(o.get("reduceOnly") and ((o.get("isTrigger") and o.get("tpsl") == "sl") or "stop" in str(o.get("orderType", "")).lower()))

# ======================================================================== papier
class PaperBroker:
    paper = True
    def __init__(self, market, state):
        self.m, self.s = market, state
        self.s.setdefault("paper_equity", C.PAPER_START_USDC)

    def equity(self): return self.s["paper_equity"] + sum(p.get("upnl", 0.0) for p in self.s["open"].values())
    def positions(self): return {c: p["sz"] for c, p in self.s["open"].items() if p["filled"]}

    def open(self, cand, sz, lev):
        return {"entry_oid": f"paper-{cand.id}", "placed_ms": int(time.time() * 1000)}

    def snapshot(self):
        return [{"coin": c, "side": p["side"], "sz": p["sz"], "entry": p["entry"], "upnl": round(p.get("upnl", 0.0), 4), "liq": None,
                 "filled": p["filled"]} for c, p in self.s["open"].items()]

    def manage(self, now_ms=None):
        """Avance chaque position papier sur les bougies 1 min écoulées. Renvoie la liste des clôtures."""
        now_ms = now_ms or int(time.time() * 1000); closed = []
        for coin, p in list(self.s["open"].items()):
            df = self.m.candles(coin, "1m", 120, discretionary=False)
            df = df[(df.ts >= p.get("checked_ms", p["placed_ms"])) & (df.ts + 60_000 <= now_ms)]
            long_ = p["side"] == "long"; res = None
            for _, b in df.iterrows():
                if not p["filled"]:
                    if (b.low <= p["entry"] if long_ else b.high >= p["entry"]):
                        p["filled"], p["filled_ms"] = True, int(b.ts); self.s["paper_equity"] -= p["sz"] * p["entry"] * C.FEE_MAKER
                        # même bougie : on suppose le pire (stop testé avant la cible, cible ignorée sur la bougie d'entrée)
                        if (b.low <= p["stop"] if long_ else b.high >= p["stop"]): res = ("STOP", p["stop"], C.FEE_TAKER); break
                        continue
                    if b.ts - p["placed_ms"] >= C.ENTRY_TTL_MIN * 60_000:
                        res = ("annulé (non rempli)", None, 0.0); break
                    continue
                hit_s = b.low <= p["stop"] if long_ else b.high >= p["stop"]
                hit_t = b.high >= p["tp"] if long_ else b.low <= p["tp"]
                if hit_s: res = ("STOP", p["stop"], C.FEE_TAKER); break
                if hit_t: res = ("CIBLE", p["tp"], C.FEE_MAKER); break
                if b.ts - p["filled_ms"] >= C.MAX_HOLD_MIN * 60_000: res = ("temps max", float(b.close), C.FEE_TAKER); break
            if len(df): p["checked_ms"] = int(df.ts.iloc[-1]) + 60_000
            if not res and not p["filled"] and now_ms - p["placed_ms"] >= (C.ENTRY_TTL_MIN + 5) * 60_000:
                res = ("annulé (non rempli)", None, 0.0)                       # pas de bougie reçue : on n'attend pas indéfiniment
            if res:
                why, px, fee = res
                pnl = 0.0 if px is None else p["sz"] * (px - p["entry"]) * (1 if long_ else -1) - p["sz"] * px * fee
                self.s["paper_equity"] += pnl
                closed.append({"coin": coin, "issue": why, "exit": px, "pnl": round(pnl, 6), **_keys(p)})
                del self.s["open"][coin]
            elif p["filled"] and len(df):
                last = float(df.close.iloc[-1]); p["upnl"] = p["sz"] * (last - p["entry"]) * (1 if long_ else -1)
        return closed

# ======================================================================== réel
class LiveBroker:
    paper = False
    def __init__(self, market, state, exchange):
        self.m, self.s, self.x, self.info = market, state, exchange, market.info
        for api in (self.x, getattr(self.x, "info", None)):
            if api is not None and hasattr(api, "timeout"): api.timeout = C.HTTP_TIMEOUT_S

    def equity(self):
        try: return float(self.info.user_state(C.HL_ACCOUNT)["marginSummary"]["accountValue"])
        except Exception: return None

    def positions(self):                                    # lève si illisible : l'appelant traite « inconnu »
        st = self.info.user_state(C.HL_ACCOUNT)
        return {p["position"]["coin"]: float(p["position"]["szi"]) for p in st.get("assetPositions", []) if float(p["position"]["szi"]) != 0}

    def snapshot(self):
        """Positions réelles telles que Hyperliquid les voit (pour le tableau de bord). Lecture seule."""
        try:
            st = self.info.user_state(C.HL_ACCOUNT); out = []
            for a in st.get("assetPositions", []):
                q = a["position"]; sz = float(q["szi"])
                if sz == 0: continue
                out.append({"coin": q["coin"], "side": "long" if sz > 0 else "short", "sz": abs(sz), "entry": float(q.get("entryPx") or 0),
                            "upnl": float(q.get("unrealizedPnl") or 0), "liq": float(q["liquidationPx"]) if q.get("liquidationPx") else None,
                            "lev": (q.get("leverage") or {}).get("value"), "filled": True, "suivie": q["coin"] in self.s["open"]})
            return out
        except Exception as ex:
            return [{"erreur": f"positions illisibles ({type(ex).__name__})"}]

    def orders(self, coin):
        return [o for o in self.info.frontend_open_orders(C.HL_ACCOUNT) if o.get("coin") == coin]

    def confirm_leverage(self, coin, lev):
        r = self.x.update_leverage(lev, coin, is_cross=False)
        if not (isinstance(r, dict) and r.get("status") == "ok"): raise RuntimeError(f"updateLeverage {lev}x refusé ({str(r)[:100]})")
        d = self.info.post("/info", {"type": "activeAssetData", "user": C.HL_ACCOUNT, "coin": coin}) or {}
        lu = ((d.get("leverage") or {}).get("type"), int((d.get("leverage") or {}).get("value", 0) or 0))
        if lu != ("isolated", lev): raise RuntimeError(f"levier non confirmé : lu {lu}, attendu ('isolated', {lev})")

    def open(self, cand, sz, lev):
        if os.path.exists(C.KILL_SWITCH): raise RuntimeError("KILL présent")
        coin, buy = cand.coin, cand.side == "long"
        sz = self.m.round_sz(sz, coin)
        if sz <= 0: raise RuntimeError("taille nulle après arrondi")
        e, sl, tp = (self.m.round_px(p, coin) for p in (cand.entry, cand.stop, cand.tp))
        self.confirm_leverage(coin, lev)
        orders = [{"coin": coin, "is_buy": buy, "sz": sz, "limit_px": e, "order_type": {"limit": {"tif": "Alo"}}, "reduce_only": False},
                  {"coin": coin, "is_buy": not buy, "sz": sz, "limit_px": sl, "order_type": {"trigger": {"triggerPx": sl, "isMarket": True, "tpsl": "sl"}}, "reduce_only": True},
                  {"coin": coin, "is_buy": not buy, "sz": sz, "limit_px": tp, "order_type": {"trigger": {"triggerPx": tp, "isMarket": False, "tpsl": "tp"}}, "reduce_only": True}]
        J.record("execution", "intent", f"{cand.side} {coin} {sz} à {e} (maker), stop {sl}, cible {tp}, levier {lev}", id=cand.id, orders=orders)
        try:
            res = self.x.bulk_orders(orders, grouping="normalTpsl")
        except Exception as ex:
            kill(f"lot {coin} envoyé, réponse perdue ({type(ex).__name__}) : vérification manuelle")
            raise
        st = (res or {}).get("response", {}).get("data", {}).get("statuses", [])
        errs = [x["error"] for x in st if isinstance(x, dict) and "error" in x]
        if (res or {}).get("status") != "ok" or errs:
            self.safe_exit(coin, f"lot refusé : {errs or res}")
            raise RuntimeError(f"lot refusé : {errs or str(res)[:200]}")
        first = st[0] if st and isinstance(st[0], dict) else {}
        oid = (first.get("resting") or first.get("filled") or {}).get("oid")
        return {"entry_oid": oid, "placed_ms": int(time.time() * 1000), "sz": sz, "entry": e, "stop": sl, "tp": tp}

    def safe_exit(self, coin, reason):
        steps = []
        try:
            for o in self.orders(coin):
                if not o.get("reduceOnly"): self.x.cancel(coin, o["oid"]); steps.append(f"entrée {o['oid']} annulée")
        except Exception as ex: steps.append(f"annulation : {type(ex).__name__}")
        known = False
        for _ in range(3):
            try: pos = self.positions().get(coin); known = True
            except Exception as ex: steps.append(f"positions illisibles : {type(ex).__name__}"); known = False; time.sleep(2); continue
            if not pos: break
            try: self.x.market_close(coin); steps.append("clôture market_close")
            except Exception as ex: steps.append(f"clôture : {type(ex).__name__}")
            time.sleep(2)
        try: flat = not self.positions().get(coin); known = True
        except Exception: flat = False; known = False
        if flat and known:
            try:
                for o in self.orders(coin): self.x.cancel(coin, o["oid"])
            except Exception: pass
            J.record("execution", "safe_exit", f"{coin} : {reason} — position fermée puis ordres annulés", steps=steps); return True
        kill(f"sortie sûre {coin} impossible ({reason}) : position inconnue ou ouverte, stop conservé")
        return False

    def _fills(self, coin, since_ms):
        return [f for f in self.info.user_fills_by_time(C.HL_ACCOUNT, since_ms) if f.get("coin") == coin]

    def _settle(self, coin, p, fills, issue):
        """Solde un trade dont l'entrée a été remplie et qui n'a plus de position : P&L net depuis les fills (closedPnl − frais)."""
        pnl = sum(float(f.get("closedPnl", 0)) - float(f.get("fee", 0)) for f in fills)
        ex_px = next((float(f["px"]) for f in reversed(fills) if str(f.get("dir", "")).startswith("Close")), None)
        for o in self.orders(coin): self.x.cancel(coin, o["oid"])          # plus de position : cible restante sans objet
        del self.s["open"][coin]
        return {"coin": coin, "issue": issue, "exit": ex_px, "pnl": round(pnl, 6), "fills": len(fills), **_keys(p)}

    def manage(self, now_ms=None):
        """v0.1.3 : P0-2 (course au délai), P0-3 (orphelines), P1-5 (rempli puis clos entre deux passages), P1-6 (reliquat partiel)."""
        now_ms = now_ms or int(time.time() * 1000); closed = []
        try: live = self.positions()
        except Exception as ex:
            J.record("execution", "erreur", f"positions illisibles ({type(ex).__name__}) : rien n'est touché"); return closed
        ttl = C.ENTRY_TTL_MIN * 60_000
        for coin, p in list(self.s["open"].items()):
            try:
                if coin in live:
                    if not p["filled"]: p["filled"], p["filled_ms"] = True, now_ms
                    orders = self.orders(coin)
                    if now_ms - p["placed_ms"] >= ttl:                      # P1-6 : reliquat d'entrée partiel → annulé, stop conservé
                        for o in orders:
                            if not o.get("reduceOnly"):
                                self.x.cancel(coin, o["oid"]); J.record("execution", "reliquat", f"{coin} : reliquat d'entrée {o['oid']} annulé au délai, position partielle conservée avec son stop")
                    if not any(is_stop(o) for o in orders): self.safe_exit(coin, "position sans stop au carnet")
                    elif now_ms - p["filled_ms"] >= C.MAX_HOLD_MIN * 60_000: self.safe_exit(coin, "temps maximal atteint")
                    continue
                if p["filled"]:                                             # rempli puis plus de position : stop, cible ou sortie sûre
                    closed.append(self._settle(coin, p, self._fills(coin, p["placed_ms"]), "fermé")); continue
                fills = self._fills(coin, p["placed_ms"])
                if fills:                                                   # P1-5 : rempli ET clos entre deux passages
                    closed.append(self._settle(coin, p, fills, "fermé (rempli puis clos entre deux passages)")); continue
                if now_ms - p["placed_ms"] < ttl: continue
                # P0-2 : délai dépassé → annuler l'ENTRÉE seulement, puis relire : si elle s'est remplie entre-temps, on la garde
                for o in self.orders(coin):
                    if not o.get("reduceOnly"): self.x.cancel(coin, o["oid"])
                if self.positions().get(coin):
                    p["filled"], p["filled_ms"] = True, now_ms
                    J.record("execution", "course", f"{coin} : entrée remplie au moment de l'annulation — position conservée avec son stop"); continue
                fills = self._fills(coin, p["placed_ms"])
                if fills:
                    closed.append(self._settle(coin, p, fills, "fermé (rempli puis clos entre deux passages)")); continue
                for o in self.orders(coin): self.x.cancel(coin, o["oid"])  # ni position ni fill, entrée annulée : stop/cible orphelins sans objet
                closed.append({"coin": coin, "issue": "annulé (non rempli)", "exit": None, "pnl": 0.0, **_keys(p)})
                del self.s["open"][coin]
            except Exception as ex:
                J.record("execution", "erreur", f"gestion {coin} : {type(ex).__name__}, nouvel essai au prochain passage")
        self.orphans(live)
        return closed

    def orphans(self, live):
        """P0-3 : position sur l'exchange absente de l'état. Sans stop → sortie sûre ; avec stop → entrées bloquées et alerte."""
        found = []
        for coin in live:
            if coin in self.s["open"]: continue
            try: has_stop = any(is_stop(o) for o in self.orders(coin))
            except Exception: has_stop = False
            if not has_stop:
                ok = self.safe_exit(coin, "position hors suivi SANS stop")
                N.send(f"⚠ Position {coin} hors suivi et sans stop : sortie sûre {'faite' if ok else 'IMPOSSIBLE → KILL'}")
                if ok: continue
            found.append(coin)
        new = sorted(set(found) - set(self.s.get("orphans", [])))
        if new:
            J.record("risque", "orpheline", f"position(s) hors suivi avec stop : {', '.join(new)} — entrées bloquées jusqu'à leur fermeture")
            N.send(f"⚠ Position(s) hors suivi : {', '.join(new)} (stop présent). Nouvelles entrées bloquées jusqu'à leur fermeture.")
        self.s["orphans"] = sorted(found)
