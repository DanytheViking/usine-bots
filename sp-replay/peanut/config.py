"""Smart Peanut — réglages. Tout vient de l'environnement (.env.lab sur le VPS). Les BORNES DURES sont plafonnées ici :
une variable peut les rendre plus strictes, jamais plus larges (min/max appliqués dans le code)."""
import os

def _f(k, d): return float(os.getenv(k, d))
def _i(k, d): return int(os.getenv(k, d))
def _b(k, d): return os.getenv(k, d).strip().lower() in ("1", "true", "yes", "oui")

NAME            = "smart-peanut"
VERSION         = "0.1.3"
DATA_DIR        = os.getenv("DATA_DIR", "/app/data")
PAPER           = _b("PAPER", "true")                  # mode papier par défaut : AUCUN ordre réel
PAPER_START_USDC = _f("PAPER_START_USDC", "50")
HL_ACCOUNT      = os.getenv("HL_ACCOUNT", "")          # adresse publique du compte Labo (séparé)
HL_AGENT_KEY    = os.getenv("HL_AGENT_KEY", "")        # clé d'AGENT Hyperliquid : trader seulement, jamais retirer
XAI_API_KEY     = os.getenv("XAI_API_KEY", "")
XAI_MODEL       = os.getenv("XAI_MODEL", "grok-4.7")
AGENT_ENABLED   = _b("AGENT_ENABLED", "true")
AGENT_MAX_CALLS_DAY = min(_i("AGENT_MAX_CALLS_DAY", "150"), 300)
HTTP_TIMEOUT_S  = _f("HTTP_TIMEOUT_S", "10")
LOOP_S          = max(_i("LOOP_S", "60"), 30)

# ---- univers : perpétuels Hyperliquid « validateurs » seulement (pas de HIP-3), assez liquides
MIN_DAY_VOLUME_USD = max(_f("MIN_DAY_VOLUME_USD", "5000000"), 2_000_000)
UNIVERSE_SIZE      = min(_i("UNIVERSE_SIZE", "12"), 25)
EXCLUDE            = {c.strip() for c in os.getenv("EXCLUDE", "").split(",") if c.strip()}

# ---- BORNES DURES (les agents ne peuvent pas les franchir)
MAX_LEVERAGE       = min(_i("MAX_LEVERAGE", "5"), 5)              # isolé, ≤ levier max de l'actif
RISK_PER_TRADE     = min(_f("RISK_PER_TRADE", "0.08"), 0.10)      # perte au stop ≤ 8 % de l'equity (10 % maximum)
MAX_OPEN           = min(_i("MAX_OPEN", "2"), 3)                  # positions simultanées
MARGIN_USE         = min(_f("MARGIN_USE", "0.90"), 0.90)          # notionnel ≤ equity × levier × 90 %
DAILY_LOSS_STOP    = min(_f("DAILY_LOSS_STOP", "0.20"), 0.30)     # −20 % sur la journée UTC → pause jusqu'à minuit UTC
FLOOR_USDC         = max(_f("FLOOR_USDC", "10"), 5)               # equity < plancher → KILL définitif
MAX_HOLD_MIN       = min(_i("MAX_HOLD_MIN", "240"), 720)          # sortie forcée après 4 h
ENTRY_TTL_MIN      = min(_i("ENTRY_TTL_MIN", "15"), 60)           # ordre maker non rempli → annulé
MIN_NOTIONAL_USD   = 10.5                                          # minimum Hyperliquid ≈ 10 $

# ---- coûts (frais de base Hyperliquid, perps validateurs)
FEE_MAKER = 0.00015
FEE_TAKER = 0.00045

# ---- v0.1.3 (P1-7) : charge sur l'API Hyperliquid. Limite officielle : 1200 de poids / minute / IP, PARTAGÉE avec Apex et
# Moonshot sur le même VPS. Le Labo s'impose un plafond pour ses appels « discrétionnaires » (bougies, univers) ; les appels de
# sécurité (positions, ordres, fills, annulations, clôtures) sont comptés mais jamais bloqués.
API_WEIGHT_PER_MIN = min(_i("API_WEIGHT_PER_MIN", "400"), 600)
UNIVERSE_FETCH_PER_PASS = min(_i("UNIVERSE_FETCH_PER_PASS", "8"), 15)
FLOOR_CONFIRM_READS = 3                                           # P1-8 : arrêt DÉFINITIF après 3 lectures consécutives < plancher

KILL_SWITCH = os.path.join(DATA_DIR, "KILL")

def redact(s: str) -> str:
    for k in (HL_AGENT_KEY, XAI_API_KEY, os.getenv("TELEGRAM_BOT_TOKEN", "")):
        if k: s = s.replace(k, "***")
    return s
