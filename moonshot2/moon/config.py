"""Moonshot v2 : reglages. Tout vient de l'environnement (.env sur le VPS). Les bornes dures sont plafonnees ici :
une variable peut les rendre plus strictes, jamais plus larges."""
import os

def _f(k, d): return float(os.getenv(k, d))
def _i(k, d): return int(os.getenv(k, d))

NAME = os.getenv("BOT_NAME", "moonshot2")
VERSION = "2.2.1"
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
MODE = os.getenv("MODE", "observation").strip().lower()       # "observation" (aucun ordre) ou "reel"
if MODE not in ("observation", "reel"): MODE = "observation"
HL_ACCOUNT = os.getenv("HL_ACCOUNT", "")                       # adresse publique du compte Moonshot
HL_AGENT_KEY = os.getenv("HL_AGENT_KEY", "")                   # cle d'agent Hyperliquid : trader seulement, jamais retirer
HTTP_TIMEOUT_S = _f("HTTP_TIMEOUT_S", "10")
LOOP_S = max(_i("LOOP_S", "60"), 30)

# ---- strategie M2 (figee par le pre-enregistrement du catalogue v1, testee en v1 et v2)
COINS_DEFAUT = ("BTC", "ETH", "SOL", "ZEC", "HYPE", "NEAR", "kPEPE", "XRP", "PUMP", "XMR", "LIT", "UNI", "AVAX")
COINS = tuple(c.strip() for c in os.getenv("COINS", ",".join(COINS_DEFAUT)).split(",") if c.strip())
MIN_DAY_VOLUME_USD = max(_f("MIN_DAY_VOLUME_USD", "0"), 0.0)   # actifs moins echanges : ignores (glissement trop fort)
EMA_FAST, EMA_SLOW, ATR_N, STOP_ATR = 50, 200, 14, 3.0
TF = "4h"
TF_MS = 4 * 3_600_000
BARS = min(max(_i("BARS", "1000"), 600), 1000)                                                    # historique lu a chaque cloture 4 h (EMA 200 stable : poids initial < 0,01 %)
SIGNAL_DELAY_S = max(_i("SIGNAL_DELAY_S", "20"), 20)                                            # attente apres la cloture 4 h avant de lire la bougie
FETCH_PAUSE_S = min(max(_f("FETCH_PAUSE_S", "0"), 0.0), 5.0)    # pause entre deux actifs : menage la limite de poids de l'IP
MAX_SIGNAL_AGE_S = 1800                                        # un croisement plus vieux que 30 min (bot arrete) n'est pas joue

# ---- bornes dures
RISK_PER_TRADE = min(_f("RISK_PER_TRADE", "0.01"), 0.01)       # 1 % de l'equity au stop (decision de Richard du 12/11)
MAX_RISK_MIN_ORDER = min(_f("MAX_RISK_MIN_ORDER", "0.015"), 0.015)   # si le minimum Hyperliquid impose plus : trade saute
MAX_LEVERAGE = min(_i("MAX_LEVERAGE", "5"), 5)                 # isole
MARGIN_USE = min(_f("MARGIN_USE", "0.90"), 0.90)               # marge totale engagee <= 90 % de l'equity
MIN_NOTIONAL_USD = 10.5                                        # minimum Hyperliquid, environ 10 $
ENTRY_SLIPPAGE = min(_f("ENTRY_SLIPPAGE", "0.01"), 0.02)       # prix limite IOC : 1 % au-dela du prix de reference
LINE_STOP = min(_f("LINE_STOP", "0.50"), 0.50)                 # equity <= 50 % du depart : arret de la ligne (decision du 09/11)
STOP_DD_R = min(_f("STOP_DD_R", "30"), 30)                     # baisse depuis le sommet >= 30 R en reel : arret (test : 26 R max)
STOP_LOSS_STREAK = min(_i("STOP_LOSS_STREAK", "20"), 20)       # 20 pertes d'affilee en reel : arret (test : 15 max)
FLOOR_USDC = max(_f("FLOOR_USDC", "10"), 5)

FEE_TAKER = 0.00045

# ---- Fable (avis enregistres seulement : aucune influence sur les ordres)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FABLE_MODEL = os.getenv("FABLE_MODEL", "claude-fable-5-1")
FABLE_MAX_CALLS_DAY = min(_i("FABLE_MAX_CALLS_DAY", "40"), 100)

KILL_SWITCH = os.path.join(DATA_DIR, "KILL")

def redact(s: str) -> str:
    for k in (HL_AGENT_KEY, ANTHROPIC_API_KEY, os.getenv("TELEGRAM_BOT_TOKEN", "")):
        if k: s = s.replace(k, "***")
    return s
