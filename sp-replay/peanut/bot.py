"""Smart Peanut — boucle principale. Scanne les actifs les plus volatils de Hyperliquid, propose les failles du moment,
laisse le conseil d'agents décider, borne la taille, exécute (papier ou réel) et journalise tout.
    python3 -m peanut.bot            (boucle)        python3 -m peanut.bot --once   (un passage)"""
import os, sys, time, json, logging, argparse, datetime as dt
from . import config as C, journal as J, risk as R, agent as A, signals as S, notify as N
from .market import Market
from .broker import PaperBroker, LiveBroker, kill

log = logging.getLogger("peanut")
STATUS = os.path.join(C.DATA_DIR, "status.json")
EQUITY = os.path.join(C.DATA_DIR, "equity.jsonl")

def equity_point(eq, n_open):
    if eq is None: return
    try:
        with open(EQUITY, "a") as f: f.write(json.dumps({"t": int(time.time()), "eq": round(eq, 4), "open": n_open}) + "\n")
    except Exception as ex: log.warning("courbe d'equity : %s", ex)

def status(s, equity, note, broker):
    try:
        json.dump({"ts": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "bot": C.NAME, "version": C.VERSION, "paper": broker.paper,
                   "equity_usdc": equity, "open": s["open"], "closed_today": [c for c in s["closed"] if str(c.get("ts", "")).startswith(s.get("day") or "x")],
                   "note": note, "universe": s.get("universe", []), "kill": os.path.exists(C.KILL_SWITCH),
                   "kill_reason": (open(C.KILL_SWITCH).read().strip()[:300] if os.path.exists(C.KILL_SWITCH) else ""),
                   "positions_exchange": broker.snapshot(), "day_start": s.get("day_start"), "dead": s.get("dead"),
                   "account": (C.HL_ACCOUNT[:6] + "…" + C.HL_ACCOUNT[-4:]) if C.HL_ACCOUNT and not broker.paper else "papier",
                   "limits": {"levier_max": C.MAX_LEVERAGE, "risque_trade": C.RISK_PER_TRADE, "positions_max": C.MAX_OPEN,
                              "perte_jour": C.DAILY_LOSS_STOP, "plancher": C.FLOOR_USDC, "duree_max_min": C.MAX_HOLD_MIN}},
                  open(STATUS + ".tmp", "w"), indent=1, default=str); os.replace(STATUS + ".tmp", STATUS)
    except Exception as ex: log.warning("status : %s", ex)

def measure(c: dict):
    """P0-4 : multiple de R réalisé (P&L / risque prévu) et glissement constaté sur un stop (en % du prix du stop, > 0 = défavorable)."""
    r = c.get("risk_usd")
    c["R"] = round(c["pnl"] / r, 3) if r else None
    if c.get("exit") is not None and c.get("stop") and c.get("issue") != "annulé (non rempli)":
        near_stop = abs(c["exit"] - c["stop"]) <= 0.5 * abs(c["entry"] - c["stop"])
        if c.get("issue") == "STOP" or near_stop:   # sortie au stop : glissement = au-delà du stop
            c["slip_stop_pct"] = round(((c["stop"] - c["exit"]) if c["side"] == "long" else (c["exit"] - c["stop"])) / c["stop"] * 100, 4)

def build(info=None, exchange=None):
    if info is None:
        from hyperliquid.info import Info; from hyperliquid.utils import constants
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
    m = Market(info); s = R.load()
    if C.PAPER: return m, s, PaperBroker(m, s)
    forbidden = {a.strip().lower() for a in os.getenv("FORBIDDEN_ACCOUNTS", "").split(",") if a.strip()}
    if not (C.HL_ACCOUNT and C.HL_AGENT_KEY): sys.exit("RÉEL refusé : HL_ACCOUNT et HL_AGENT_KEY (clé d'agent, trading seul) sont requis")
    if C.HL_ACCOUNT.lower() in forbidden: sys.exit("RÉEL refusé : ce compte est celui d'Apex ou de Moonshot (FORBIDDEN_ACCOUNTS)")
    if exchange is None:
        from eth_account import Account; from hyperliquid.exchange import Exchange; from hyperliquid.utils import constants
        exchange = Exchange(Account.from_key(C.HL_AGENT_KEY), constants.MAINNET_API_URL, account_address=C.HL_ACCOUNT)
    return m, s, LiveBroker(m, s, exchange)

def step(m, s, b, now=None, decide=A.decide, scan=S.scan):
    now = now or dt.datetime.now(dt.timezone.utc)
    pending = {c for c, p in s["open"].items() if not p["filled"]}
    for c in b.manage():                                              # 1. positions : remplissage, stop, cible, temps max
        c["ts"] = now.isoformat()[:19] + "Z"; measure(c); s["closed"].append(c)
        J.record("cloture", c["issue"], f"{c['coin']} {c['side']} {c['strat']} : {c['issue']}, P&L {c['pnl']:+.4f} USDC", **c)
        if c["issue"] != "annulé (non rempli)":
            N.send(f"{'✅' if c['pnl'] > 0 else '❌'} Clôture {c['coin']} {c['side']} ({c['strat']}) : {c['issue']}\nP&L {c['pnl']:+.2f} USDC · equity {b.equity() or 0:.2f}")
    for c in pending:
        p = s["open"].get(c)
        if p and p["filled"]:
            N.send(f"📈 En position : {p['side']} {c} ({p['strat']})\nentrée {p['entry']:.6g} · stop {p['stop']:.6g} · cible {p['tp']:.6g} · levier {p['lev']}x · risque {p['risk_usd']:.2f} $")
    eq = b.equity(); R.roll_day(s, eq, now) if eq is not None else None
    hb = now.strftime("%Y-%m-%d") + "-" + str(now.hour // 6)              # résumé toutes les 6 h (00, 06, 12, 18 UTC)
    if eq is not None and s.get("last_summary") != hb:
        s["last_summary"] = hb; day = [x for x in s["closed"] if str(x.get("ts", "")).startswith(now.strftime("%Y-%m-%d")) and x.get("issue") != "annulé (non rempli)"]
        N.send(f"🕒 Point {now.strftime('%H:%M')} UTC — equity {eq:.2f} $ (jour {eq - (s['day_start'] or eq):+.2f})\n"
               f"trades du jour : {len(day)} · P&L {sum(x['pnl'] for x in day):+.2f} $ · positions : {', '.join(s['open']) or 'aucune'}"
               + ("\n⚠ KILL actif" if os.path.exists(C.KILL_SWITCH) else ""))
    equity_point(eq, len(s["open"]))
    if eq is not None:                                                # P1-8 : entrées bloquées dès la 1re lecture (gate),
        s["floor_hits"] = s.get("floor_hits", 0) + 1 if eq < C.FLOOR_USDC else 0   # arrêt DÉFINITIF après 3 lectures consécutives
        if s["floor_hits"] >= C.FLOOR_CONFIRM_READS and not s["dead"]:
            s["dead"] = True; kill(f"equity {eq:.2f} USDC sous le plancher {C.FLOOR_USDC} ({s['floor_hits']} lectures consécutives) : poche arrêtée")
        elif s["floor_hits"]:
            J.record("risque", "plancher", f"lecture {s['floor_hits']}/{C.FLOOR_CONFIRM_READS} sous {C.FLOOR_USDC} USDC ({eq:.2f}) : entrées bloquées")
    why = R.gate(s, eq)
    if why:
        R.save(s); status(s, eq, why, b); return why
    try:                                                              # 2. univers : volatilité re-mesurée par petits lots (P1-7)
        u = m.universe()
        if u and u != s.get("universe"):
            s["universe"], s["universe_t"] = u, time.time(); J.record("univers", "maj", ", ".join(u))
    except Exception as ex: J.record("univers", "erreur", f"{type(ex).__name__}")
    cands = [c for c in scan(m, s.get("universe", [])) if c.id not in s["seen"] and c.coin not in s["open"]]   # 3. failles du moment
    if not cands:
        R.save(s); status(s, eq, "aucune faille détectée à ce passage", b); return "rien"
    ctx = m.contexts(); s["seen"] += [c.id for c in cands]
    pairs = [(c, {k: ctx[c.coin][k] for k in ("funding_an", "oi_usd", "vol_usd", "mark", "prev", "max_lev")}) for c in cands]
    for c, _ in pairs: J.record("signal", "candidat", f"{c.strat} {c.coin} {c.side} : {c.why}", **c.to_dict())
    recent = [{k: x.get(k) for k in ("coin", "strat", "side", "issue", "pnl")} for x in s["closed"][-10:]]
    acct = {"equity_usdc": round(eq, 4), "positions": list(s["open"]), "papier": b.paper, "risque_max_par_trade": C.RISK_PER_TRADE}
    res = decide(pairs, acct, recent)                                 # 4. le conseil d'agents décide
    J.record("agent", res["source"], res["note"] or "—", decisions=res["decisions"])
    for c, cx in pairs:
        d = res["decisions"].get(c.id)
        if not d or d["action"] != "take":
            J.record("decision", "skip", f"{c.coin} {c.strat} : {(d or {}).get('reason') or 'non retenu par le conseil'}"); continue
        if R.gate(s, b.equity()): J.record("decision", "bloque", R.gate(s, b.equity())); break
        sz, lev, notional, risk_usd, no = R.size(c, d["size"], eq, ctx[c.coin], s)   # 5. bornes dures
        if no: J.record("risque", "refus", f"{c.coin} {c.strat} : {no}"); continue
        try:
            r = b.open(c, sz, lev)                                    # 6. exécution (maker + stop + cible)
        except Exception as ex:
            J.record("execution", "erreur", f"{c.coin} : {C.redact(str(ex))[:200]}"); continue
        s["open"][c.coin] = {"id": c.id, "strat": c.strat, "side": c.side, "entry": r.get("entry", c.entry), "stop": r.get("stop", c.stop),
                             "tp": r.get("tp", c.tp), "sz": r.get("sz", sz), "lev": lev, "notional": notional, "risk_usd": risk_usd,
                             "placed_ms": r["placed_ms"], "entry_oid": r.get("entry_oid"), "filled": False, "agent": d}
        N.send(f"🎯 Ordre posé : {c.side} {c.coin} ({c.strat}, maker)\nentrée {c.entry:.6g} · stop {c.stop:.6g} · cible {c.tp:.6g} · levier {lev}x · risque {risk_usd:.2f} $\nGrok ({d['confidence']}) : {d['reason'][:200]}")
        J.record("execution", "place", f"{c.side} {c.coin} {sz:.6g} à {c.entry:.6g}, stop {c.stop:.6g}, cible {c.tp:.6g}, levier {lev}, risque {risk_usd:.2f} USDC "
                 f"({'papier' if b.paper else 'RÉEL'}) — agent : {d['confidence']}, taille {d['size']:.2f} : {d['reason']}", **s["open"][c.coin])
    R.save(s); status(s, eq, res["note"], b); return "decide"

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser(); ap.add_argument("--once", action="store_true"); a = ap.parse_args()
    m, s, b = build()
    log.info("Smart Peanut %s — %s — capital papier %s USDC — bornes : levier ≤ %s, risque ≤ %.0f %%/trade, %s positions, plancher %s USDC",
             C.VERSION, "PAPIER" if b.paper else "RÉEL", C.PAPER_START_USDC if b.paper else "-", C.MAX_LEVERAGE, C.RISK_PER_TRADE * 100, C.MAX_OPEN, C.FLOOR_USDC)
    J.record("demarrage", "papier" if b.paper else "reel", f"Smart Peanut {C.VERSION}")
    N.send(f"▶ Démarrage v{C.VERSION} ({'papier' if b.paper else 'RÉEL'}) — positions suivies : {', '.join(s['open']) or 'aucune'}")
    while True:
        t0 = time.time()
        try: log.info("passage : %s", step(m, s, b))
        except Exception as ex:
            log.error("passage : %s", C.redact(str(ex))); J.record("boucle", "erreur", f"{type(ex).__name__}: {C.redact(str(ex))[:200]}")
            errs = s.get("errs", 0) + 1; s["errs"] = errs
            if errs in (5, 30, 120): N.send(f"⚠ {errs} passages en erreur d'affilée ({type(ex).__name__}). Le bot continue d'essayer ; les stops restent posés.")
        else: s["errs"] = 0
        if a.once: break
        time.sleep(max(5, C.LOOP_S - (time.time() - t0)))

if __name__ == "__main__":
    main()
