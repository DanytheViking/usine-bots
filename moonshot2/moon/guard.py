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

def size(side: str, ref: float, atr: float, equity: float, ctx: dict, positions: dict):
    """(taille, levier, notionnel, risque USD, raison du refus ou "")."""
    dist = C.STOP_ATR * float(atr or 0)
    if not (dist > 0 and ref > 0 and equity and equity > 0): return 0, 0, 0, 0, "stop ou prix invalide"
    d = int(ctx.get("sz_dec", 0)); step = 10 ** -d
    risk = equity * C.RISK_PER_TRADE
    sz = math.floor(risk / dist / step + 1e-9) * step
    if sz * ref < C.MIN_NOTIONAL_USD:
        sz = math.ceil(C.MIN_NOTIONAL_USD / ref / step - 1e-9) * step
        if sz * dist > equity * C.MAX_RISK_MIN_ORDER:
            return 0, 0, sz * ref, sz * dist, (f"minimum Hyperliquid ({C.MIN_NOTIONAL_USD} $) : risque {sz * dist / equity:.2%} "
                                               f"> {C.MAX_RISK_MIN_ORDER:.1%} de l'equity, trade saute")
    max_lev = int(ctx.get("max_lev", 1) or 1); lev = 0
    for L in range(min(C.MAX_LEVERAGE, max_lev), 0, -1):
        if liq_distance(L, max_lev, side) >= 2 * dist / ref: lev = L; break
    if not lev: return 0, 0, 0, 0, f"stop a {dist / ref:.1%} trop large : liquidation a moins de 2 fois le stop au levier 1"
    notional = sz * ref
    used = sum(p["notional"] / p["lev"] for p in positions.values())
    if used + notional / lev > equity * C.MARGIN_USE:
        return 0, lev, notional, sz * dist, f"marge insuffisante ({used:.2f} deja engages, {notional / lev:.2f} demandes, plafond {equity * C.MARGIN_USE:.2f})"
    return sz, lev, notional, sz * dist, ""
