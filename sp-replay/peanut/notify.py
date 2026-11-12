"""Alertes Telegram de Smart Peanut (ENVOI seulement, via le bot Telegram déjà actif d'Apex ; aucune commande reçue).
Ne bloque jamais le trading : toute erreur d'envoi est ignorée (et journalisée en local)."""
import os, requests, logging
from . import config as C
TOKEN, CHAT = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
log = logging.getLogger("peanut.notify")
PREFIX = "[LABO] 🥜 Smart Peanut (hors Apex)"     # P1-9 (D-20261030-1645-LAB) : jamais confondu avec Apex ; aucun bouton (pas de reply_markup)

def send(text: str) -> bool:
    if not (TOKEN and CHAT): return False
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                          json={"chat_id": CHAT, "text": (PREFIX + (" (papier)" if C.PAPER else "") + "\n" + text)[:4000],
                                "disable_web_page_preview": True}, timeout=10)
        return r.status_code == 200
    except Exception as ex:
        log.warning("telegram : %s", type(ex).__name__); return False
