"""Chien de garde de Moonshot v2 : conteneur separe, SANS cle de trading, donnees en lecture seule.
Il ne passe aucun ordre. Il previent sur Telegram si :
  - le bot ne donne plus signe de vie (status.json non mis a jour depuis plus de 15 minutes), puis quand il repart ;
  - un KILL apparait ;
  - une position ouverte sur Hyperliquid n'a pas d'ordre stop au carnet (verification independante du bot).
    python3 -m moon.garde"""
import os, json, time, logging
from . import config as C, notify as N

log = logging.getLogger("moon.garde")
STATUS = os.path.join(C.DATA_DIR, "status.json")
INFO_URL = "https://api.hyperliquid.xyz/info"
SILENCE_S = 15 * 60
EXCHANGE_EVERY_S = 5 * 60

def _ts(s):
    import datetime as dt
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()

def status_age(now):
    try: return now - _ts(json.load(open(STATUS))["ts"])
    except Exception: return None

def naked_positions(post):
    """Positions du compte sans ordre stop reduce-only au carnet. Leve si l'API est illisible."""
    st = post({"type": "clearinghouseState", "user": C.HL_ACCOUNT})
    pos = {p["position"]["coin"] for p in st.get("assetPositions", []) if float(p["position"]["szi"]) != 0}
    orders = post({"type": "frontendOpenOrders", "user": C.HL_ACCOUNT})
    covered = {o["coin"] for o in orders if o.get("reduceOnly") and (o.get("isTrigger") and o.get("tpsl") == "sl" or "stop" in str(o.get("orderType", "")).lower())}
    return sorted(pos - covered)

def _http_post(body):
    import requests
    r = requests.post(INFO_URL, json=body, timeout=10); r.raise_for_status(); return r.json()

class Garde:
    def __init__(self, post=_http_post, send=N.send, clock=time.time):
        self.post, self.send, self.clock = post, send, clock
        self.silent = False; self.kill_seen = os.path.exists(C.KILL_SWITCH); self.naked = set(); self.last_x = 0.0; self.x_errors = 0

    def tick(self):
        now = self.clock(); age = status_age(now)
        if age is None or age > SILENCE_S:
            if not self.silent:
                self.silent = True
                self.send(f"🚨 CHIEN DE GARDE : le bot ne donne plus signe de vie depuis {'?' if age is None else int(age // 60)} min.\n"
                          "Verifier : docker ps ; docker logs --tail 30 moonshot2")
        elif self.silent:
            self.silent = False; self.send("✅ CHIEN DE GARDE : le bot donne de nouveau signe de vie.")
        k = os.path.exists(C.KILL_SWITCH)
        if k and not self.kill_seen:
            try: why = open(C.KILL_SWITCH).read().strip()[:300]
            except Exception: why = "?"
            self.send(f"🛑 CHIEN DE GARDE : KILL present.\n{why}")
        self.kill_seen = k
        if C.HL_ACCOUNT and now - self.last_x >= EXCHANGE_EVERY_S:
            self.last_x = now
            try:
                naked = set(naked_positions(self.post)); self.x_errors = 0
                new = naked - self.naked
                if new: self.send(f"🚨 CHIEN DE GARDE : position(s) SANS STOP sur Hyperliquid : {', '.join(sorted(new))}.\n"
                                  "Le bot doit les couvrir ou les fermer au prochain passage ; sinon : touch /opt/moonshot2/data/KILL et fermer a la main.")
                if self.naked - naked: self.send(f"✅ CHIEN DE GARDE : stop retrouve ou position fermee : {', '.join(sorted(self.naked - naked))}.")
                self.naked = naked
            except Exception as ex:
                self.x_errors += 1
                if self.x_errors == 3: self.send(f"⚠ CHIEN DE GARDE : Hyperliquid illisible 3 fois de suite ({type(ex).__name__}).")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    g = Garde(); g.send("🐕 Chien de garde demarre : silence > 15 min, KILL, positions sans stop.")
    while True:
        try: g.tick()
        except Exception as ex: log.warning("garde : %s", type(ex).__name__)
        time.sleep(60)

if __name__ == "__main__":
    main()
