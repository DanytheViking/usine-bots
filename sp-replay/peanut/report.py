"""Bilan de Smart Peanut :  python3 -m peanut.report   — trades clôturés, P&L, taux de réussite, profit factor, par stratégie."""
import os, json
from collections import defaultdict
from . import config as C, risk as R, journal as J

def main():
    s = R.load(); cl = [c for c in s["closed"] if c.get("issue") != "annulé (non rempli)"]
    ok, n, msg = J.verify()
    st = {}
    try: st = json.load(open(os.path.join(C.DATA_DIR, "status.json")))
    except Exception: pass
    print(f"Smart Peanut {C.VERSION} — {'PAPIER' if C.PAPER else 'RÉEL'} — equity {st.get('equity_usdc')} USDC — KILL {'OUI' if os.path.exists(C.KILL_SWITCH) else 'non'}")
    print(f"journal : {'✅' if ok else '❌'} {n} décisions — {msg}")
    print(f"positions ouvertes : {list(s['open']) or 'aucune'} — ordres maker annulés (non remplis) : {len(s['closed']) - len(cl)}")
    by = defaultdict(list)
    for c in cl: by[c["strat"]].append(c["pnl"]); by["TOTAL"].append(c["pnl"])
    print(f"{'stratégie':<16}{'trades':>7}{'gagnants':>10}{'P&L USDC':>11}{'PF':>7}")
    for k, v in sorted(by.items(), key=lambda kv: kv[0] == "TOTAL"):
        g, p = sum(x for x in v if x > 0), -sum(x for x in v if x < 0)
        print(f"{k:<16}{len(v):>7}{sum(x > 0 for x in v):>10}{sum(v):>+11.3f}{(g / p if p else float('inf')):>7.2f}")
    if len(cl) < 30: print(f"→ {len(cl)} trades : moins de 30, aucune conclusion possible (seuil de Pythagore).")

if __name__ == "__main__":
    main()
