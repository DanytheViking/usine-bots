"""Fable, le decideur : un avis sur chaque signal M2. Avec FABLE_DECIDE (par defaut, decision de Richard du 12/11/2026),
un avis « eviter » annule l'entree ; les signaux ecartes sont journalises pour mesurer l'apport de Fable.
Sans cle API, ou en cas d'erreur, le bot applique la regle M2 : l'avis est simplement absent."""
import json, re
from . import config as C

URL = "https://api.anthropic.com/v1/messages"
SYSTEM = ("Tu es l'analyste d'anticipation d'une equipe de trading crypto. On te presente un signal de suivi de tendance "
          "(croisement des moyennes mobiles 50 et 200 en 4 h) sur un perpetuel Hyperliquid. Donne ton avis sur ce trade, "
          "en tenant compte du contexte fourni et de ce que tu sais du marche. Reponds UNIQUEMENT par un objet JSON : "
          '{"avis": "prendre" ou "eviter", "confiance": entier de 0 a 100, "raison": "une phrase en francais"}.')

def context_text(coin, side, ev, ctx, df):
    c = df.close.values
    ret = lambda n: f"{(c[-1] / c[-1 - n] - 1) * 100:+.1f} %" if len(c) > n else "n/d"
    return (f"Actif : {coin}. Signal : {side} (croisement EMA 50/200 en 4 h, bougie cloturee).\n"
            f"Prix : {ev['ref']:.6g}. EMA 50 : {ev['ema_rapide']:.6g}. EMA 200 : {ev['ema_lente']:.6g}. ATR 4 h : {ev['atr']:.6g} "
            f"({ev['atr'] / ev['ref'] * 100:.2f} % du prix).\nVariation : 24 h {ret(6)}, 7 jours {ret(42)}, 30 jours {ret(180)}.\n"
            f"Funding horaire : {ctx.get('funding_h', 0) * 100:.4f} %.")

AVIS = {"prendre": "prendre", "pris": "prendre", "take": "prendre", "eviter": "eviter", "ecarter": "eviter", "avoid": "eviter", "skip": "eviter"}

def sans_accents(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def parse(text: str):
    """Premier objet JSON lisible de la reponse (bloc de code, texte autour, accents toleres)."""
    for m in re.finditer(r"\{[^{}]*\}", text or "", re.S):
        try: d = json.loads(m.group(0))
        except ValueError: continue
        avis = AVIS.get(sans_accents(str(d.get("avis", ""))).strip().lower())
        if avis: break
    else:
        return None
    try: conf = max(0, min(100, int(d.get("confiance", 0))))
    except (TypeError, ValueError): conf = 0
    return {"avis": avis, "confiance": conf, "raison": str(d.get("raison", ""))[:300]}

def apercu(text: str):
    return re.sub(r"\s+", " ", (text or ""))[:160]

def opinion(prompt: str, state: dict, day: str, post=None):
    """Renvoie {"avis", "confiance", "raison"} ou {"absent": raison}. Plafond d'appels par jour UTC."""
    if not C.ANTHROPIC_API_KEY: return {"absent": "pas de cle API"}
    used = state["fable_calls"].get(day, 0)
    if used >= C.FABLE_MAX_CALLS_DAY: return {"absent": "plafond d'appels du jour atteint"}
    state["fable_calls"] = {day: used + 1}
    try:
        if post is None:
            import requests
            post = requests.post
        r = post(URL, timeout=60, headers={"x-api-key": C.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                 json={"model": C.FABLE_MODEL, "max_tokens": 1000, "system": SYSTEM, "messages": [{"role": "user", "content": prompt}]})
        if getattr(r, "status_code", 0) != 200: return {"absent": f"API {getattr(r, 'status_code', '?')}"}
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        return parse(text) or {"absent": "reponse illisible", "apercu": apercu(text)}
    except Exception as ex:
        return {"absent": f"erreur {type(ex).__name__}"}
