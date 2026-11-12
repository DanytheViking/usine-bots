"""Contrôles AVANT le passage en réel (lecture seule, aucun ordre) :  python3 -m peanut.preflight
Compte Labo valide et distinct d'Apex/Moonshot, clé d'agent bien approuvée pour CE compte, capital plausible, compte à plat."""
import os, re, sys
from . import config as C

def main(info=None, max_equity=float(os.getenv("PREFLIGHT_MAX_EQUITY", "150"))):
    ok = True
    def chk(cond, msg):
        nonlocal ok; print(("✅ " if cond else "❌ ") + msg); ok = ok and bool(cond)
    acct = C.HL_ACCOUNT.strip(); forb = {a.strip().lower() for a in os.getenv("FORBIDDEN_ACCOUNTS", "").split(",") if a.strip()}
    chk(re.fullmatch(r"0x[0-9a-fA-F]{40}", acct), f"adresse du compte Labo au bon format ({acct[:6]}…{acct[-4:]})")
    chk(len([a for a in forb if re.fullmatch(r"0x[0-9a-f]{40}", a)]) >= 2, f"adresses Apex et Moonshot connues ({len(forb)} interdites)")
    chk(acct.lower() not in forb, "le compte Labo n'est NI Apex NI Moonshot")
    try:
        from eth_account import Account
        agent = Account.from_key(C.HL_AGENT_KEY).address
        chk(True, f"clé d'agent lisible (adresse de l'agent {agent[:6]}…{agent[-4:]})")
        chk(agent.lower() != acct.lower(), "la clé n'est PAS la clé principale du compte (c'est bien un agent)")
    except Exception as ex:
        agent = None; chk(False, f"clé d'agent illisible ({type(ex).__name__})")
    if info is None:
        from hyperliquid.info import Info; from hyperliquid.utils import constants
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
    try:
        ag = info.post("/info", {"type": "extraAgents", "user": acct})
        if isinstance(ag, list):
            chk(agent and any(str(a.get("address", "")).lower() == agent.lower() for a in ag), f"agent approuvé par Hyperliquid pour ce compte ({len(ag)} agent(s))")
        else: print(f"⚠️  liste des agents non lisible ({str(ag)[:80]}) : sera vérifiée par le premier ordre")
    except Exception as ex: print(f"⚠️  liste des agents non lisible ({type(ex).__name__}) : sera vérifiée par le premier ordre")
    try:
        st = info.user_state(acct); eq = float(st["marginSummary"]["accountValue"])
        pos = [p for p in st.get("assetPositions", []) if float(p["position"]["szi"]) != 0]
        orders = info.frontend_open_orders(acct)
        chk(C.FLOOR_USDC < eq <= max_equity, f"capital du compte Labo : {eq:.2f} USDC (attendu entre {C.FLOOR_USDC} et {max_equity:.0f})")
        chk(not pos and not orders, f"compte à plat : {len(pos)} position(s), {len(orders)} ordre(s)")
    except Exception as ex: chk(False, f"compte illisible ({type(ex).__name__})")
    print("\n" + ("✅ PRÉ-VOL OK : le passage en réel est possible" if ok else "❌ PRÉ-VOL ÉCHOUÉ : on reste en papier"))
    return ok

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
