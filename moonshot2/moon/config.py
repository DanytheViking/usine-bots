"""Moonshot v2 : reglages. Tout vient de l'environnement (.env sur le VPS). Les bornes dures sont plafonnees ici :
une variable peut les rendre plus strictes, jamais plus larges."""
import os

def _f(k, d): return float(os.getenv(k, d))
def _i(k, d): return int(os.getenv(k, d))

NAME = os.getenv("BOT_NAME", "moonshot2")
VERSION = "2.7.0"
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
TF = "1h" if NAME == "smartpeanut2" else "4h"                 # Lab : M2 en 1 h (USINE-SPEC-M2H1, exception ecrite de Richard) ; Moonshot reste en 4 h
TF_MS = (1 if TF == "1h" else 4) * 3_600_000
ENTREE_TENDANCE = NAME == "smartpeanut2"                     # Lab v5 (choix ecrit de Richard du 22/11) : sans position, entree dans la tendance EMA 50 / 200 en cours
MAX_POSITIONS = 2 if NAME == "smartpeanut2" else len(COINS)   # Lab : deux positions au plus (cadre montre a Richard le 22/11) ; priorite :
                                                             # a chaque cloture, actifs lus dans l'ordre de COINS, la premiere entree prend la place
BARS_JOUR = 86_400_000 // TF_MS
BARS = min(max(_i("BARS", "1000"), 600), 1000)                                                    # historique lu a chaque cloture (EMA 200 stable : poids initial < 0,01 %)
SIGNAL_DELAY_S = max(_i("SIGNAL_DELAY_S", "20"), 20)                                            # attente apres la cloture avant de lire la bougie
FETCH_PAUSE_S = min(max(_f("FETCH_PAUSE_S", "0"), 0.0), 5.0)    # pause entre deux actifs : menage la limite de poids de l'IP
MAX_SIGNAL_AGE_S = 1800                                        # un croisement plus vieux que 30 min (bot arrete) n'est pas joue

# ---- bornes dures
RISK_PER_TRADE = min(_f("RISK_PER_TRADE", "0.01"), 0.20 if NAME == "smartpeanut2" else 0.05)   # Lab : 20 % au plus (Richard, 15/11) ; Moonshot 5 % au plus (Richard, 16/11), 1 % par defaut
MAX_RISK_MIN_ORDER = min(_f("MAX_RISK_MIN_ORDER", "0.015"), 0.20 if NAME == "smartpeanut2" else 0.015)   # si le minimum Hyperliquid impose plus : trade saute
MAX_OPEN_RISK = min(_f("MAX_OPEN_RISK", "0.40"), 0.40)         # risque ouvert total (somme des risques au stop) <= 40 % de l'equity
MAX_LEVERAGE = min(_i("MAX_LEVERAGE", "5"), 5)                 # isole
MARGIN_USE = min(_f("MARGIN_USE", "0.90"), 0.90)               # marge totale engagee <= 90 % de l'equity
LIQ_RESERVE = max(_f("LIQ_RESERVE", "2"), 2.0)                 # liquidation a au moins 2 fois la distance du stop (stop a moins de 50 % du chemin)
MIN_NOTIONAL_USD = 10.5                                        # minimum Hyperliquid, environ 10 $
ENTRY_SLIPPAGE = min(_f("ENTRY_SLIPPAGE", "0.01"), 0.02)       # prix limite IOC : 1 % au-dela du prix de reference
LINE_STOP = min(_f("LINE_STOP", "0.50"), 0.80 if NAME == "smartpeanut2" else 0.50)   # arret de ligne : -50 % (09/11), -80 % au Lab (Richard, 15/11)
STOP_DD_R = min(_f("STOP_DD_R", "30"), 30)                     # baisse depuis le sommet >= 30 R en reel : arret (test : 26 R max)
STOP_LOSS_STREAK = min(_i("STOP_LOSS_STREAK", "20"), 20)       # 20 pertes d'affilee en reel : arret (test : 15 max)
GARDE_DD_R = float("inf") if NAME == "smartpeanut2" else 10.0  # garde-fou de Moonshot (le Lab a ses propres regles) : baisse de 10 R depuis le sommet en reel -> risque ramene a GARDE_RISK
GARDE_RISK = 0.01                                              # jusqu'a decision ecrite de Richard (remise a zero de garde_risque dans l'etat)
FLOOR_USDC = max(_f("FLOOR_USDC", "10"), 5)

FEE_TAKER = 0.00045

# ---- Thales, le decideur : il utilise le modele Fable de preference, le modele de secours seulement si Fable ne repond pas
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
FABLE_MODEL = os.getenv("FABLE_MODEL", "claude-fable-5-1")
THALES_SECOURS = os.getenv("THALES_SECOURS", "claude-opus-5-5")   # vide : pas de secours
FABLE_MAX_CALLS_DAY = min(_i("FABLE_MAX_CALLS_DAY", "40"), 100)
# Thales decide (decision de Richard du 12/11/2026) : parmi les signaux M2, un avis « eviter » annule l'entree.
# Avis absent (pas de cle, erreur, plafond) : la regle M2 s'applique. Les sorties restent mecaniques. FABLE_DECIDE=0 le desactive.
FABLE_DECIDE = os.getenv("FABLE_DECIDE", "1").strip().lower() in ("1", "oui", "true")

KILL_SWITCH = os.path.join(DATA_DIR, "KILL")

def redact(s: str) -> str:
    for k in (HL_AGENT_KEY, ANTHROPIC_API_KEY, os.getenv("TELEGRAM_BOT_TOKEN", "")):
        if k: s = s.replace(k, "***")
    return s
