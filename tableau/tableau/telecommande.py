"""Telecommande Telegram de l'usine. Aucune cle de trading : elle lit les fichiers des bots et l'API publique Hyperliquid,
et ne sait faire qu'une seule action, poser un KILL (arreter les nouvelles entrees d'un bot). Elle ne peut ni ouvrir un trade,
ni retirer un KILL : la reprise se fait volontairement sur le VPS.
Seul le chat TELEGRAM_CHAT_ID est obei ; tout autre expediteur est ignore.
Commandes : /etat  /positions  /pnl  /kill moonshot|peanut|tous (puis /confirmer dans les 60 s)  /aide"""
import os, time, json, logging, datetime as dt
from . import server as S

log = logging.getLogger("telecommande")
TOKEN, CHAT = os.getenv("TELEGRAM_BOT_TOKEN", ""), str(os.getenv("TELEGRAM_CHAT_ID", ""))
BOTS = {"moonshot": ("Moonshot", S.MOON), "peanut": ("Smart Peanut v2", S.PEANUT2)}
CONFIRM_S = 60
AIDE = ("Commandes :\n/etat : resume des deux bots\n/positions : positions ouvertes et stops sur Hyperliquid\n/pnl : resultat depuis le depart\n"
        "/kill moonshot | peanut | tous : arreter les nouvelles entrees (confirmation demandee)\n/aide : cette liste\n"
        "La reprise apres un KILL se fait sur le VPS, jamais depuis Telegram.")

def _fmt(x, d=2):
    return "n/d" if x is None else f"{x:+.{d}f}" if isinstance(x, (int, float)) else str(x)

def etat():
    ex = S.EX.get(); lines = ["📊 Etat de l'usine"]
    for key, (nom, base) in BOTS.items():
        if not os.path.exists(os.path.join(base, "status.json")): continue
        b = S.moonshot(base); compte = (ex.get("comptes") or {}).get("Moonshot" if key == "moonshot" else "Smart Peanut", {})
        vivant = b["age_s"] is not None and b["age_s"] < 900
        lines.append(f"\n{nom} : {(b['status'].get('mode') or '?').upper()}{' · KILL' if b['kill'] else ''} · {'en marche' if vivant else 'SILENCIEUX'}\n"
                     f"Capital {compte.get('valeur', 'n/d')} USDC (depart {b['start_equity']}) · positions {len(b['positions'])}\n"
                     f"R cumule {_fmt(b['r_cumule'])} · baisse {b['baisse_R']:.1f}/30 R · pertes d'affilee {b['pertes_affilee']}/20")
    if ex.get("erreur"): lines.append(f"\n⚠ {ex['erreur']}")
    return "\n".join(lines)

def positions():
    ex = S.EX.get(); lines = ["📌 Positions (Hyperliquid)"]
    for nom, c in (ex.get("comptes") or {}).items():
        for q in c.get("positions", []):
            lines.append(f"{nom} · {q['coin']} {q['sens']} · entree {q['entree']:.6g} · prix {q['prix'] or 0:.6g} · P&L {q['pnl']:+.2f} · "
                         f"{'stop OK' if q['stop'] else 'SANS STOP'}")
    return "\n".join(lines) if len(lines) > 1 else "📌 Aucune position ouverte."

def pnl():
    ex = S.EX.get(); lines = ["💰 Resultat depuis le depart"]
    for key, (nom, base) in BOTS.items():
        if not os.path.exists(os.path.join(base, "status.json")): continue
        b = S.moonshot(base); v = (ex.get("comptes") or {}).get("Moonshot" if key == "moonshot" else "Smart Peanut", {}).get("valeur")
        st = b["start_equity"]
        perf = f"{v - st:+.2f} USDC ({(v / st - 1) * 100:+.2f} %)" if v and st else "n/d"
        n = len(b["closed"]); g = sum(1 for c in b["closed"] if (c.get("pnl") or 0) > 0)
        lines.append(f"{nom} : {perf} · {n} trades recents dont {g} gagnants")
    return "\n".join(lines)

def poser_kill(cibles):
    done = []
    for key in cibles:
        nom, base = BOTS[key]
        if not os.path.isdir(base): continue
        with open(os.path.join(base, "KILL"), "a") as f:
            f.write(f"{dt.datetime.now(dt.timezone.utc).isoformat()[:19]}Z KILL pose depuis Telegram par Richard\n")
        done.append(nom)
    return done

class Telecommande:
    def __init__(self, send, clock=time.time):
        self.send, self.clock, self.pending = send, clock, None

    def handle(self, chat_id, text):
        if str(chat_id) != CHAT or not CHAT: return None                 # tout autre expediteur est ignore
        t = (text or "").strip().lower().split()
        if not t: return None
        cmd, arg = t[0].split("@")[0], (t[1] if len(t) > 1 else "")
        if cmd in ("/aide", "/start", "/help"): return AIDE
        if cmd == "/etat": return etat()
        if cmd == "/positions": return positions()
        if cmd == "/pnl": return pnl()
        if cmd == "/kill":
            cibles = list(BOTS) if arg == "tous" else [arg] if arg in BOTS else None
            if not cibles: return "Usage : /kill moonshot | peanut | tous"
            self.pending = (cibles, self.clock())
            return f"⚠ Confirmer l'arret des nouvelles entrees pour : {', '.join(BOTS[c][0] for c in cibles)} ?\nEnvoie /confirmer dans les {CONFIRM_S} s."
        if cmd == "/confirmer":
            if not self.pending or self.clock() - self.pending[1] > CONFIRM_S:
                self.pending = None; return "Rien a confirmer (ou delai depasse). Recommence avec /kill."
            done = poser_kill(self.pending[0]); self.pending = None
            return f"🛑 KILL pose : {', '.join(done) or 'aucun bot trouve'}. Plus aucune nouvelle entree ; les positions gardent leur stop."
        return "Commande inconnue. /aide pour la liste."

def _api(method, payload=None, timeout=40):
    import requests
    r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload or {}, timeout=timeout)
    return r.json()

def send(text):
    try: _api("sendMessage", {"chat_id": CHAT, "text": text[:4000], "disable_web_page_preview": True}, timeout=10)
    except Exception as ex: log.warning("envoi : %s", type(ex).__name__)

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not (TOKEN and CHAT): raise SystemExit("TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID requis")
    tc = Telecommande(send); offset = None
    try:
        r = _api("getUpdates", {"timeout": 0})                           # ignore les vieux messages en attente
        if r.get("result"): offset = r["result"][-1]["update_id"] + 1
    except Exception: pass
    send("🎛 Telecommande active. /aide pour la liste des commandes.")
    while True:
        try:
            r = _api("getUpdates", {"timeout": 30, "offset": offset, "allowed_updates": ["message"]})
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message") or {}
                reply = tc.handle((m.get("chat") or {}).get("id"), m.get("text"))
                if reply: send(reply)
        except Exception as ex:
            log.warning("boucle : %s", type(ex).__name__); time.sleep(5)

if __name__ == "__main__":
    main()
