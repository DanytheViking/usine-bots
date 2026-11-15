"""Le Gardien : etat persistant, taille des positions et arrets automatiques. Il ne peut que reduire ou refuser."""
import os, json, math
from . import config as C

STATE = os.path.join(C.DATA_DIR, "state.json")

def load() -> dict:
    try: s = json.load(open(STATE))
    except Exception: s = {}
    for k, v in (("positions", {}), ("closed", []), ("r_ledger", []), ("start_equity", None), ("last_bar", {}),
                 ("dead", False), ("fable_calls", {}), ("orphans", [])):
        s.setdefault(k, v)
    return s

def save(s: dict):
    os.makedirs(C.DATA_DIR, exist_ok=True); s["closed"] = s["closed"][-1000:]
    tmp = STATE + ".tmp"; json.dump(s, open(tmp, "w"), indent=1, default=str); os.replace(tmp, STATE)

def liq_distance(L: int, max_lev: int, side: str) -> float:
    """Distance relative entree vers liquidation d'une position isolee Hyperliquid (marge de maintenance = 1 / (2 x levier max))."""
    l = 1 / (2 * max(1, int(max_lev)))
    return (1 / L - l) / ((1 + l) if side == "short" else (1 - l))

def drawdown_r(ledger) -> float:
    peak = cur = 0.0; dd = 0.0
    for r in ledger:
        cur += r; peak = max(peak, cur); dd = max(dd, peak - cur)
    return dd

def loss_streak(ledger) -> int:
    n = 0
    for r in reversed(ledger):
        if r < 0: n += 1
        else: break
    return n

def gate(s: dict, equity) -> str:
    """Raison de bloquer toute nouvelle entree, ou "" si les entrees sont permises. Les arrets de ligne sont definitifs (KILL)."""
    if os.path.exists(C.KILL_SWITCH): return "KILL present"
    if s.get("dead"): return "ligne arretee definitivement"
    if equity is None: return "equity illisible"
    if equity < C.FLOOR_USDC: return f"equity {equity:.2f} sous le plancher de {C.FLOOR_USDC:.2f} USDC"
    if s.get("start_equity") and equity <= s["start_equity"] * (1 - C.LINE_STOP):
        return f"STOP LIGNE : equity {equity:.2f} <= {1 - C.LINE_STOP:.0%} du depart ({s['start_equity']:.2f})"
    if drawdown_r(s["r_ledger"]) >= C.STOP_DD_R:
        return f"STOP CONFORMITE : baisse de {drawdown_r(s['r_ledger']):.1f} R depuis le sommet (test : 26 R au plus)"
    if loss_streak(s["r_ledger"]) >= C.STOP_LOSS_STREAK:
        return f"STOP CONFORMITE : {loss_streak(s['r_ledger'])} pertes d'affilee (test : 15 au plus)"
    if s.get("orphans"): return f"position(s) hors suivi sur l'exchange : {', '.join(s['orphans'])}"
    return ""

def is_fatal(reason: str) -> bool:
    return reason.startswith("STOP LIGNE") or reason.startswith("STOP CONFORMITE") or "plancher" in reason

def plafonds() -> dict:
    """Bornes actives, journalisees avec chaque decision d'ordre."""
    return {"risque_par_trade": C.RISK_PER_TRADE, "risque_min_ordre": C.MAX_RISK_MIN_ORDER, "risque_ouvert_max": C.MAX_OPEN_RISK,
            "levier_max": C.MAX_LEVERAGE, "marge_max": C.MARGIN_USE, "reserve_liquidation": C.LIQ_RESERVE}

def _refus(code, why, **k):
    return {"sz": 0, "lev": 0, "notional": 0.0, "risk": 0.0, "code": code, "why": why, **k}

def taille(side: str, ref: float, atr: float, equity: float, ctx: dict, positions: dict) -> dict:
    """Taille d'une entree, en ne faisant que reduire ou refuser. Ordre des gardes :
      1. risque vise = equity x RISK_PER_TRADE, borne par le risque ouvert restant (MAX_OPEN_RISK, code RISK_LIMIT) ;
      2. minimum Hyperliquid : si l'ordre minimum impose plus que MAX_RISK_MIN_ORDER, refus (MIN_ORDER) ;
      3. levier : le plus haut tel que la liquidation reste a au moins LIQ_RESERVE fois le stop ; aucun : refus (LIQ_GUARD) ;
      4. marge : si la marge totale depasserait MARGIN_USE, la taille est reduite (MARGIN), refus si elle passe sous le minimum.
    Le stop ne bouge jamais. Renvoie sz, lev, notional, risk (reel, au stop), code ("" si rien n'a borne), why (refus) et les mesures."""
    dist = C.STOP_ATR * float(atr or 0)
    if not (dist > 0 and ref > 0 and equity and equity > 0): return _refus("INVALID", "stop ou prix invalide")
    d = int(ctx.get("sz_dec", 0)); step = 10 ** -d
    risk_target = equity * C.RISK_PER_TRADE
    open_risk = sum(float(p.get("risk_usd", 0) or 0) for p in positions.values())
    reste = equity * C.MAX_OPEN_RISK - open_risk
    code = ""; mesures = {"risk_target": round(risk_target, 4), "risque_ouvert": round(open_risk, 4), "dist_stop": round(dist / ref, 5)}
    risk = risk_target
    if reste < risk_target:
        if reste < C.MIN_NOTIONAL_USD * dist / ref:
            return _refus("RISK_LIMIT", f"risque ouvert {open_risk / equity:.1%} : plafond {C.MAX_OPEN_RISK:.0%} atteint, trade saute", **mesures)
        risk = reste; code = "RISK_LIMIT"
    sz = math.floor(risk / dist / step + 1e-9) * step
    if sz * ref < C.MIN_NOTIONAL_USD:
        sz = math.ceil(C.MIN_NOTIONAL_USD / ref / step - 1e-9) * step
        if sz * dist > equity * C.MAX_RISK_MIN_ORDER or sz * dist > reste + 1e-9:
            return _refus("MIN_ORDER", f"minimum Hyperliquid ({C.MIN_NOTIONAL_USD} $) : risque {sz * dist / equity:.2%} "
                          f"> {min(C.MAX_RISK_MIN_ORDER, reste / equity):.1%} de l'equity, trade saute", notional=sz * ref, **mesures)
    max_lev = int(ctx.get("max_lev", 1) or 1); lev = 0
    for L in range(min(C.MAX_LEVERAGE, max_lev), 0, -1):
        if liq_distance(L, max_lev, side) >= C.LIQ_RESERVE * dist / ref: lev = L; break
    if not lev:
        return _refus("LIQ_GUARD", f"stop a {dist / ref:.1%} trop large : liquidation a moins de {C.LIQ_RESERVE:g} fois le stop au levier 1", **mesures)
    used = sum(p["notional"] / p["lev"] for p in positions.values())
    libre = equity * C.MARGIN_USE - used
    if sz * ref / lev > libre:
        sz2 = math.floor(libre * lev / ref / step + 1e-9) * step
        if sz2 * ref < C.MIN_NOTIONAL_USD:
            return _refus("MARGIN", f"marge insuffisante ({used:.2f} deja engages, {sz * ref / lev:.2f} demandes, plafond {equity * C.MARGIN_USE:.2f})",
                          lev=lev, notional=sz * ref, **mesures)
        sz = sz2; code = "MARGIN"
    notional = sz * ref
    return {"sz": sz, "lev": lev, "notional": notional, "risk": sz * dist, "code": code, "why": "", "marge": round(notional / lev, 4),
            "marge_engagee": round(used, 4), "dist_liq": round(liq_distance(lev, max_lev, side), 5), **mesures}

def size(side: str, ref: float, atr: float, equity: float, ctx: dict, positions: dict):
    """(taille, levier, notionnel, risque USD, raison du refus ou "")."""
    t = taille(side, ref, atr, equity, ctx, positions)
    return t["sz"], t["lev"], t["notional"], t["risk"], t["why"]
