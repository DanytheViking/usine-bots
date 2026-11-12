"""Alertes Telegram de Moonshot v2 (envoi seulement, aucune commande recue). Une erreur d'envoi ne bloque jamais le trading."""
import os, logging
from . import config as C

log = logging.getLogger("moon.notify")
PREFIX = os.getenv("BOT_PREFIX", "🚀 Moonshot v2")

def send(text: str, post=None) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not (token and chat): return False
    try:
        if post is None:
            import requests
            post = requests.post
        head = PREFIX + (" (observation, aucun ordre)" if C.MODE != "reel" else "")
        r = post(f"https://api.telegram.org/bot{token}/sendMessage",
                 json={"chat_id": chat, "text": (head + "\n" + C.redact(text))[:4000], "disable_web_page_preview": True}, timeout=10)
        return getattr(r, "status_code", 0) == 200
    except Exception as ex:
        log.warning("telegram : %s", type(ex).__name__); return False
