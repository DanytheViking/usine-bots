"""Bornes dures de Smart Peanut : elles s'appliquent APRÈS la décision des agents et ne peuvent que réduire ou refuser."""
import os, json, datetime as dt
from . import config as C

STATE = os.path.join(C.DATA_DIR, "state.json")
SLIP_MIN = 0.001        # v0.1.3 (P0-4) : réserve de glissement du stop au marché, au moins 0,10 % du prix…
SLIP_ATR = 0.25         # …ou 0,25 × l'ATR en %, si c'est plus

def liq_distance(L: int, max_lev: int, side: str) -> float:
    """v0.1.3 (P0-1) : distance relative entrée → liquidation d'une position ISOLÉE sur Hyperliquid.
    Marge de maintenance = moitié de la marge initiale au levier MAX de l'actif : l = 1 / (2 × max_lev).
    Prix de liquidation = entrée − sens × marge disponible / taille / (1 − l × sens)   (sens = +1 long, −1 short)
    → long : (1/L − l) / (1 − l)      short : (1/L − l) / (1 + l)
    Vérifié sur le short ZRO réel du 30/10 (entrée 1,77, 5x, levier max 5) : 1,9309 calculé, 1,930668 affiché."""
    l = 1 / (2 * max(1, int(max_lev)))
    return (1 / L - l) / ((1 + l) if side == "short" else (1 - l))

def slip_reserve(cand) -> float:
    return max(SLIP_MIN, SLIP_ATR * float(cand.atr_pct or 0) / 100)

def load() -> dict:
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("open", {}); s.setdefault("closed", []); s.setdefault("day", None); s.setdefault("day_start", None)
    s.setdefault("dead", False); s.setdefault("seen", [])
    return s

def save(s: dict):
    os.makedirs(C.DATA_DIR, exist_ok=True); s["seen"] = s["seen"][-500:]; s["closed"] = s["closed"][-500:]
    tmp = STATE + ".tmp"; json.dump(s, open(tmp, "w"), indent=1, default=str); os.replace(tmp, STATE)

def roll_day(s: dict, equity: float, now: dt.datetime):
    d = now.strftime("%Y-%m-%d")
    if s["day"] != d: s["day"], s["day_start"] = d, equity

def gate(s: dict, equity: float) -> str:
    """Raison de bloquer TOUTE nouvelle entrée, ou "" si les entrées sont permises."""
    if os.path.exists(C.KILL_SWITCH): return "KILL présent"
    if s.get("dead"): return "poche arrêtée définitivement (plancher touché)"
    if equity is None: return "equity illisible"
    if equity < C.FLOOR_USDC: return f"equity {equity:.2f} < plancher {C.FLOOR_USDC:.2f} USDC"
    if s["day_start"] and equity < s["day_start"] * (1 - C.DAILY_LOSS_STOP):
        return f"perte du jour > {C.DAILY_LOSS_STOP:.0%} ({equity:.2f} contre {s['day_start']:.2f} au début du jour UTC) : pause jusqu'à minuit UTC"
    if s.get("orphans"): return f"position(s) hors suivi sur l'exchange : {', '.join(s['orphans'])} — entrées bloquées (P0-3)"
    if len(s["open"]) >= C.MAX_OPEN: return f"{C.MAX_OPEN} positions déjà ouvertes"
    return ""

def size(cand, agent_size: float, equity: float, ctx: dict, s: dict):
    """Renvoie (taille en coin, levier, notionnel, risque USD, raison du refus ou "")."""
    if cand.coin in s["open"]: return 0, 0, 0, 0, f"déjà une position sur {cand.coin}"
    e, st = cand.entry, cand.stop; dist = abs(e - st) / e
    if dist <= 0: return 0, 0, 0, 0, "stop nul"
    per_coin = abs(e - st) + e * C.FEE_MAKER + st * (C.FEE_TAKER + slip_reserve(cand))   # perte au stop : frais + réserve de glissement
    risk_usd = equity * C.RISK_PER_TRADE * min(1.0, max(0.25, agent_size))
    lev, max_lev = 0, int(ctx.get("max_lev", 1) or 1)
    for L in range(min(C.MAX_LEVERAGE, max_lev), 0, -1):                  # plus grand levier dont la liquidation RÉELLE est ≥ 2 × le stop
        if liq_distance(L, max_lev, cand.side) >= 2 * dist: lev = L; break
    if not lev: return 0, 0, 0, 0, f"stop à {dist:.1%} trop large : liquidation à moins de 2 fois le stop même au levier 1"
    used = sum(p["notional"] / p["lev"] for p in s["open"].values())
    cap = max(0.0, equity * C.MARGIN_USE - used) * lev
    sz = min(risk_usd / per_coin, cap / e)
    notional = sz * e
    if notional < C.MIN_NOTIONAL_USD: return 0, lev, notional, 0, f"notionnel {notional:.2f} $ < minimum Hyperliquid ({C.MIN_NOTIONAL_USD} $) dans les bornes"
    return sz, lev, notional, sz * per_coin, ""
