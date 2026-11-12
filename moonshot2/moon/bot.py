"""Moonshot v2 : boucle principale. Strategie M2 (croisement EMA 50/200 en 4 h) sur 13 perps Hyperliquid.
A chaque cloture 4 h : sorties sur croisement inverse (avec retournement), puis entrees. Entre deux clotures : suivi des
positions et des stops. Fable donne un avis enregistre sur chaque signal, sans influence sur les ordres.
    python3 -m moon.bot              boucle
    python3 -m moon.bot --once       un passage
    python3 -m moon.bot --preflight  verifications en lecture seule (aucun ordre)"""
import os, sys, time, json, logging, argparse, datetime as dt
from . import config as C, journal as J, guard as G, signal as SG, notify as N, fable as F
from .market import Market
from .broker import ObservationBroker, LiveBroker, kill

log = logging.getLogger("moon")
STATUS = os.path.join(C.DATA_DIR, "status.json")
EQUITY = os.path.join(C.DATA_DIR, "equity.jsonl")
OBS_START = 66.57                                   # equity virtuelle de depart si le compte est illisible en observation

def utc(ms=None):
    t = dt.datetime.now(dt.timezone.utc) if ms is None else dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc)
    return t.isoformat()[:19] + "Z"

def build(info=None, exchange=None):
    if info is None:
        from hyperliquid.info import Info; from hyperliquid.utils import constants
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
    m = Market(info); s = G.load()
    if C.MODE != "reel":
        start = None
        if C.HL_ACCOUNT:
            try: start = float(m.info.user_state(C.HL_ACCOUNT)["marginSummary"]["accountValue"])
            except Exception: start = None
        return m, s, ObservationBroker(m, s, start or OBS_START)
    if not (C.HL_ACCOUNT and C.HL_AGENT_KEY): sys.exit("REEL refuse : HL_ACCOUNT et HL_AGENT_KEY (cle d'agent, trading seul) sont requis")
    forbidden = {a.strip().lower() for a in os.getenv("FORBIDDEN_ACCOUNTS", "").split(",") if a.strip()}
    if C.HL_ACCOUNT.lower() in forbidden: sys.exit("REEL refuse : compte interdit (FORBIDDEN_ACCOUNTS)")
    if exchange is None:
        from eth_account import Account; from hyperliquid.exchange import Exchange; from hyperliquid.utils import constants
        exchange = Exchange(Account.from_key(C.HL_AGENT_KEY), constants.MAINNET_API_URL, account_address=C.HL_ACCOUNT)
    return m, s, LiveBroker(m, s, exchange)

def on_close(s, c, b):
    c["ts"] = utc(); s["closed"].append(c)
    if b.mode == "reel" and c.get("R") is not None: s["r_ledger"].append(c["R"])
    J.record("cloture", c["issue"], f"{c['coin']} {c['side']} : {c['issue']}, P&L {c['pnl']:+.4f} USDC ({c.get('R')} R)", **c)
    N.send(f"{'✅' if c['pnl'] > 0 else '❌'} {c['coin']} {c['side']} ferme : {c['issue']}\nP&L {c['pnl']:+.2f} USDC ({c.get('R')} R)")

def enter(m, s, b, coin, side, ev, df, equity, day, fable_post=None):
    ctx = m.contexts().get(coin)
    if not ctx: J.record("signal", "saute", f"{coin} : contexte Hyperliquid absent"); return
    op = F.opinion(F.context_text(coin, side, ev, ctx, df), s, day, post=fable_post)
    J.record("fable", op.get("avis", "absent"), f"{coin} {side} : {op}", coin=coin, side=side, bar_ts=ev["bar_ts"], **op)
    if C.FABLE_DECIDE and op.get("avis") == "eviter":
        J.record("signal", "ecarte par Fable", f"{coin} {side} : Fable decide d'eviter ({op.get('confiance')} %) : {op.get('raison')}",
                 coin=coin, side=side, bar_ts=ev["bar_ts"], ref=ev["ref"], atr=ev["atr"])
        N.send(f"🔮 Thales (Fable) ecarte le signal M2 {coin} {side.upper()} ({op.get('confiance')} %)\n{op.get('raison')}")
        return
    sz, lev, notional, risk, why = G.size(side, ev["ref"], ev["atr"], equity, ctx, s["positions"])
    if why:
        J.record("signal", "saute", f"{coin} {side} : {why}"); N.send(f"⏭ Signal {coin} {side} saute : {why}"); return
    stop = ev["ref"] - C.STOP_ATR * ev["atr"] if side == "long" else ev["ref"] + C.STOP_ATR * ev["atr"]
    try:
        r = b.open(coin, side, sz, lev, ev["ref"], stop)
    except Exception as ex:
        J.record("execution", "erreur", f"{coin} {side} : {type(ex).__name__} {str(ex)[:200]}"); N.send(f"⚠ Entree {coin} {side} echouee : {str(ex)[:200]}"); return
    if r is None: N.send(f"⏭ {coin} {side} : entree non remplie (prix parti au-dela de 1 %)"); return
    s["positions"][coin] = {"side": side, "sz": r["sz"], "entry": r["entry"], "stop": r["stop"], "risk_usd": risk, "lev": lev,
                            "notional": r["sz"] * r["entry"], "opened_ms": int(time.time() * 1000), "bar_ts": ev["bar_ts"], "fee_in": r.get("fee_in", 0.0)}
    fab = f"\nFable : {op['avis']} ({op['confiance']} %) : {op['raison']}" if "avis" in op else ""
    J.record("execution", "ouvert", f"{coin} {side} {r['sz']} a {r['entry']}, stop {r['stop']}, risque {risk:.2f} USDC, levier {lev}")
    N.send(f"🟢 {coin} {side.upper()} ouvert a {r['entry']:.6g}\nStop {r['stop']:.6g} ; risque {risk:.2f} USDC ({risk / equity:.2%}) ; levier {lev}x{fab}")

def on_bar(m, s, b, now_ms, equity, reason, fable_post=None):
    """Traitement d'une cloture 4 h pour les actifs suivis (absents du meta ou trop peu echanges : ignores)."""
    day = utc(now_ms)[:10]; expected = now_ms // C.TF_MS * C.TF_MS - C.TF_MS; pending = []
    try: ctx = m.contexts()
    except Exception: ctx = {}
    for coin in C.COINS:
        if ctx and coin not in s["positions"] and (coin not in ctx or ctx[coin].get("vol_usd", 0) < C.MIN_DAY_VOLUME_USD): continue
        if s["last_bar"].get(coin) == expected: continue
        if C.FETCH_PAUSE_S: time.sleep(C.FETCH_PAUSE_S)
        try: df = SG.closed(m.candles(coin), now_ms)
        except Exception as ex:
            J.record("signal", "erreur", f"{coin} : bougies illisibles ({type(ex).__name__})"); pending.append(coin); continue
        if df.empty or int(df.ts.iloc[-1]) < expected: pending.append(coin); continue
        ev = SG.evaluate(df)
        if ev["bar_ts"] is None: s["last_bar"][coin] = expected; continue          # historique trop court : rien a jouer
        if s["last_bar"].get(coin) == ev["bar_ts"]: continue
        s["last_bar"][coin] = ev["bar_ts"]
        if not ev["cross"]: continue
        if now_ms - (ev["bar_ts"] + C.TF_MS) > C.MAX_SIGNAL_AGE_S * 1000:
            J.record("signal", "trop ancien", f"{coin} : croisement {ev['cross']} de la cloture {utc(ev['bar_ts'] + C.TF_MS)}, non joue (redemarrage)"); continue
        J.record("signal", ev["cross"], f"{coin} : croisement {ev['cross']} a la cloture {utc(ev['bar_ts'] + C.TF_MS)}", coin=coin, **{k: v for k, v in ev.items() if k != 'raison'})
        p = s["positions"].get(coin)
        if p and p["side"] != ev["cross"]:
            try: on_close(s, b.close(coin, "sortie signal (croisement inverse)"), b)
            except Exception as ex:
                J.record("execution", "erreur", f"sortie {coin} : {type(ex).__name__}"); continue
        elif p: continue
        if reason: J.record("signal", "bloque", f"{coin} {ev['cross']} : {reason}"); N.send(f"⏸ Signal {coin} {ev['cross']} non joue : {reason}"); continue
        enter(m, s, b, coin, ev["cross"], ev, df, b.equity() or equity, day, fable_post)
    return pending

def write_status(s, b, equity, note):
    try:
        json.dump({"ts": utc(), "bot": C.NAME, "version": C.VERSION, "mode": b.mode, "equity_usdc": equity, "positions": s["positions"],
                   "start_equity": s.get("start_equity"), "r_cumule": round(sum(s["r_ledger"]), 3), "baisse_R": round(G.drawdown_r(s["r_ledger"]), 3),
                   "pertes_affilee": G.loss_streak(s["r_ledger"]), "note": note, "kill": os.path.exists(C.KILL_SWITCH),
                   "derniers_trades": s["closed"][-10:]}, open(STATUS + ".tmp", "w"), indent=1, default=str)
        os.replace(STATUS + ".tmp", STATUS)
        with open(EQUITY, "a") as f: f.write(json.dumps({"t": int(time.time()), "eq": equity, "open": len(s["positions"])}) + "\n")
    except Exception as ex: log.warning("status : %s", ex)

def daily_report(s, b, equity, now):
    day = now.strftime("%Y-%m-%d")
    if now.hour < 8 or s.get("report_day") == day: return
    s["report_day"] = day
    pos = ", ".join(f"{c} {p['side']}" for c, p in s["positions"].items()) or "aucune"
    last = [c for c in s["closed"] if str(c.get("ts", "")) >= (now - dt.timedelta(days=1)).isoformat()[:19]]
    pnl = sum(c["pnl"] for c in last)
    N.send(f"📊 Rapport du {day}\nEquity : {equity:.2f} USDC (depart {s.get('start_equity') or 'n/d'})\nPositions : {pos}\n"
           f"Trades fermes 24 h : {len(last)}, P&L {pnl:+.2f} USDC\nR cumule (reel) : {sum(s['r_ledger']):+.2f} ; baisse depuis le sommet : {G.drawdown_r(s['r_ledger']):.1f} R")

def step(m, s, b, now=None, fable_post=None):
    now = now or dt.datetime.now(dt.timezone.utc); now_ms = int(now.timestamp() * 1000)
    for c in b.manage(): on_close(s, c, b)
    equity = b.equity()
    if b.mode == "reel" and s.get("start_equity") is None and equity:
        s["start_equity"] = equity; J.record("risque", "depart", f"equity de depart en reel : {equity:.2f} USDC (arret de ligne a {equity * (1 - C.LINE_STOP):.2f})")
    reason = G.gate(s, equity)
    if reason and G.is_fatal(reason) and not s.get("dead"):
        s["dead"] = True; kill(reason)
    bar_close = now_ms // C.TF_MS * C.TF_MS
    if now_ms - bar_close >= C.SIGNAL_DELAY_S * 1000 and s.get("bar_done") != bar_close:
        pending = on_bar(m, s, b, now_ms, equity, reason, fable_post)
        if not pending or now_ms - bar_close > 600_000: s["bar_done"] = bar_close
    daily_report(s, b, equity or 0.0, now)
    write_status(s, b, equity, reason or "entrees permises")
    G.save(s)
    return reason

def preflight(m, s, b):
    """Lecture seule : compte, positions, contextes et bougies des 13 actifs, taille simulee de chaque trade."""
    ok = True; print(f"mode : {C.MODE} ; compte : {(C.HL_ACCOUNT[:6] + '...' + C.HL_ACCOUNT[-4:]) if C.HL_ACCOUNT else 'absent'}")
    try: eq = float(m.info.user_state(C.HL_ACCOUNT)["marginSummary"]["accountValue"]); print(f"equity reelle du compte : {eq:.2f} USDC")
    except Exception as ex: eq = None; print(f"compte illisible : {type(ex).__name__}"); ok = False
    if C.HL_AGENT_KEY:
        try:
            from eth_account import Account
            agent = Account.from_key(C.HL_AGENT_KEY).address.lower()
            rows = m.info.post("/info", {"type": "extraAgents", "user": C.HL_ACCOUNT}) or []
            row = next((r for r in rows if str(r.get("address", "")).lower() == agent), None)
            valid = row and int(row.get("validUntil") or 0) > int(time.time() * 1000)
            print(f"cle d'agent {agent[:6]}...{agent[-4:]} : {'autorisee jusqu au ' + utc(int(row['validUntil'])) if valid else 'NON AUTORISEE ou expiree sur ce compte'}")
            if not valid and C.MODE == "reel": ok = False
        except Exception as ex:
            print(f"verification de la cle d'agent impossible : {type(ex).__name__}"); ok = ok and C.MODE != "reel"
    else:
        print("cle d'agent absente (observation seulement)")
    try: print(f"positions ouvertes sur l'exchange : {b.positions() or 'aucune'}")
    except Exception as ex: print(f"positions illisibles : {type(ex).__name__}"); ok = False
    ctx = m.contexts(); now_ms = int(time.time() * 1000)
    for coin in C.COINS:
        if coin not in ctx: print(f"{coin:8s} absent du meta Hyperliquid : ignore"); continue
        if ctx[coin].get("vol_usd", 0) < C.MIN_DAY_VOLUME_USD:
            print(f"{coin:8s} volume 24 h {ctx[coin].get('vol_usd', 0) / 1e6:.1f} M$ < {C.MIN_DAY_VOLUME_USD / 1e6:.1f} M$ : ignore"); continue
        df = SG.closed(m.candles(coin), now_ms); ev = SG.evaluate(df)
        if ev["atr"] is None: print(f"{coin:8s} historique insuffisant ({len(df)} bougies) : ignore pour l instant"); continue
        sz, lev, notional, risk, why = G.size(ev["trend"], ev["ref"], ev["atr"], eq or OBS_START, ctx[coin], {})
        print(f"{coin:6s} tendance {ev['trend']:5s} stop {C.STOP_ATR * ev['atr'] / ev['ref']:.1%} -> " +
              (why if why else f"taille {sz:g} ({notional:.2f} $), levier {lev}x, risque {risk:.2f} USDC"))
    print(f"Fable : {'cle presente, modele ' + C.FABLE_MODEL if C.ANTHROPIC_API_KEY else 'pas de cle (avis absents)'}")
    print("PREVOL OK" if ok else "PREVOL EN ECHEC"); return ok

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--once", action="store_true"); ap.add_argument("--preflight", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    m, s, b = build()
    if a.preflight: sys.exit(0 if preflight(m, s, b) else 1)
    J.record("demarrage", C.MODE, f"{C.NAME} {C.VERSION} demarre en mode {C.MODE}, {len(C.COINS)} actifs")
    N.send(f"Demarrage en mode {C.MODE.upper()} ; {len(C.COINS)} actifs ; risque {C.RISK_PER_TRADE:.0%} par trade")
    while True:
        try: note = step(m, s, b)
        except Exception as ex:
            note = f"erreur {type(ex).__name__}"; J.record("boucle", "erreur", C.redact(str(ex))[:300])
        log.info("passage : %s", note)
        if a.once: break
        time.sleep(C.LOOP_S)

if __name__ == "__main__":
    main()
