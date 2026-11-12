"""Essai d'execution reel, a lancer a la main, bot arrete : un aller-retour minimal passe par le code du bot.
Verifie : levier relu, entree IOC et stop declencheur reduce-only dans le meme lot, stop present au carnet,
sortie sure (fermeture puis annulation), compte a plat, cout lu dans les fills, journal et Telegram.
Ce n'est pas un trade de strategie : aucune decision de marche, sens et taille fixes.
    python3 -m moon.essai [--coin BTC] [--notionnel 12]"""
import os, sys, time, argparse
from . import config as C, journal as J, notify as N
from .broker import is_stop

LEVIER = 2
STOP_PCT = 0.03
ATTENTE_S = 5

def run(m, s, b, coin="BTC", notionnel=12.0, sleep=time.sleep, now_ms=None):
    def out(msg): print(msg, flush=True)
    if C.MODE != "reel" or getattr(b, "mode", "") != "reel": out("refus : l'essai ne tourne qu'en mode reel"); return 1
    if os.path.exists(C.KILL_SWITCH): out("refus : KILL present"); return 1
    if s.get("positions"): out(f"refus : le bot suit des positions ({', '.join(s['positions'])})"); return 1
    if not 10.5 <= notionnel <= 25: out("refus : notionnel entre 10,5 et 25 USD"); return 1
    try: live = b.positions()
    except Exception as ex: out(f"refus : positions illisibles ({type(ex).__name__})"); return 1
    if live: out(f"refus : positions ouvertes sur le compte ({', '.join(live)})"); return 1
    if b.orders(coin): out(f"refus : ordres deja ouverts sur {coin}"); return 1
    ctx = m.contexts()
    if coin not in ctx: out(f"refus : {coin} absent du meta"); return 1
    mid = m.mids()[coin]; d = ctx[coin]["sz_dec"]
    sz = m.round_sz(notionnel / mid, coin)
    while sz * mid < C.MIN_NOTIONAL_USD: sz = round(sz + 10 ** -d, d)
    lev = min(LEVIER, ctx[coin]["max_lev"]); stop = mid * (1 - STOP_PCT)
    t0 = now_ms if now_ms is not None else int(time.time() * 1000)
    out(f"essai {coin} : achat {sz} (~{sz * mid:.2f} $), levier {lev}x isole, stop {STOP_PCT:.0%} sous {mid:g}")
    J.record("essai", "debut", f"essai d'execution {coin} {sz}, levier {lev}, stop {stop:g}")
    try:
        res = b.open(coin, "long", sz, lev, mid, stop)
    except Exception as ex:
        out(f"ECHEC a l'entree : {type(ex).__name__} {C.redact(str(ex))[:200]}")
        N.send(f"🧪 Essai d'execution {coin} : ECHEC a l'entree ({type(ex).__name__}). Verifie le compte."); return 1
    if res is None:
        out("entree IOC non remplie : ordres annules, rien d'ouvert. Relance l'essai.")
        J.record("essai", "non rempli", f"{coin} : IOC non rempli"); return 1
    stops = [o for o in b.orders(coin) if is_stop(o)]
    out(f"1. position ouverte : {res['sz']} {coin} a {res['entry']:g}")
    out(f"2. stop au carnet : {len(stops)} ordre(s), declencheur {[o.get('triggerPx') for o in stops]}, reduce-only {[bool(o.get('reduceOnly')) for o in stops]}")
    sleep(ATTENTE_S)
    ok = b.safe_exit(coin, "essai d'execution termine")
    try: flat = not b.positions().get(coin) and not b.orders(coin)
    except Exception: flat = False
    out(f"3. sortie sure : {'position fermee et ordres annules' if ok and flat else 'INCOMPLETE'}")
    try:
        fills = [f for f in m.info.user_fills_by_time(C.HL_ACCOUNT, t0) if f.get("coin") == coin]
        frais = sum(float(f.get("fee", 0)) for f in fills); pnl = sum(float(f.get("closedPnl", 0)) for f in fills)
        out(f"4. cout de l'essai : frais {frais:.4f} USDC, resultat {pnl:+.4f} USDC, total {pnl - frais:+.4f} USDC ({len(fills)} remplissages)")
    except Exception as ex:
        frais = pnl = 0.0; out(f"4. fills illisibles ({type(ex).__name__})")
    good = bool(stops) and ok and flat
    J.record("essai", "resultat", "ESSAI EXECUTION OK" if good else "ESSAI EXECUTION EN ECHEC",
             coin=coin, taille=res["sz"], entree=res["entry"], stops=len(stops), cout=round(pnl - frais, 6))
    N.send(f"🧪 Essai d'execution {coin} : {'OK' if good else 'EN ECHEC'}\nentree {res['sz']} a {res['entry']:g}, stop au carnet : {'oui' if stops else 'NON'}, "
           f"sortie : {'propre' if ok and flat else 'INCOMPLETE'}, cout {pnl - frais:+.4f} USDC")
    out("ESSAI EXECUTION OK" if good else "ESSAI EXECUTION EN ECHEC")
    return 0 if good else 1

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--coin", default="BTC"); ap.add_argument("--notionnel", type=float, default=12.0)
    a = ap.parse_args(argv)
    from .bot import build
    m, s, b = build()
    sys.exit(run(m, s, b, a.coin, a.notionnel))

if __name__ == "__main__":
    main()
