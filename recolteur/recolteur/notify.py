"""Alertes Telegram du Recolteur (envoi seulement). Une erreur d'envoi ne bloque jamais le moteur."""
import os, logging
from . import config as C

log = logging.getLogger("recolteur.notify")
PREFIX = "🌊 T6 Recolteur (papier, aucun ordre)"

def send(text, post=None):
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not (token and chat): return False
    try:
        if post is None:
            import requests
            post = requests.post
        r = post(f"https://api.telegram.org/bot{token}/sendMessage",
                 json={"chat_id": chat, "text": (PREFIX + "\n" + C.redact(str(text)))[:4000], "disable_web_page_preview": True}, timeout=10)
        return getattr(r, "status_code", 0) == 200
    except Exception as ex:
        log.warning("telegram : %s", type(ex).__name__); return False
