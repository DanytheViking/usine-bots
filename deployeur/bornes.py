"""Constitution de l'usine : regles que le code venu du depot ne peut pas changer.
Ce fichier est installe sur le VPS a la main et n'est JAMAIS mis a jour par le Deployeur.
verifier(arbre) renvoie la liste des violations ; une seule suffit pour refuser tout le commit."""
import os, re, json

# Bornes dures du risque : ces lignes doivent rester presentes, a l'identique, dans le code des bots.
LIGNES_BORNES = (
    'RISK_PER_TRADE = min(_f("RISK_PER_TRADE", "0.01"), 0.01)',
    'MAX_RISK_MIN_ORDER = min(_f("MAX_RISK_MIN_ORDER", "0.015"), 0.015)',
    'MAX_LEVERAGE = min(_i("MAX_LEVERAGE", "5"), 5)',
    'MARGIN_USE = min(_f("MARGIN_USE", "0.90"), 0.90)',
    'LINE_STOP = min(_f("LINE_STOP", "0.50"), 0.50)',
    'STOP_DD_R = min(_f("STOP_DD_R", "30"), 30)',
    'STOP_LOSS_STREAK = min(_i("STOP_LOSS_STREAK", "20"), 20)',
)
CONFIG_BOTS = ("moonshot2/moon/config.py",)

# Aucun mouvement de fonds, aucune gestion de cle : le code des bots ne fait que trader.
INTERDITS_CODE = ("withdraw", "usd_transfer", "usdclasstransfer", "usd_class_transfer", "vault_usd_transfer", "spot_transfer",
                  "sub_account_transfer", "approve_agent", "approveagent", "approve_builder_fee", "set_referrer", "convert_to_multi_sig",
                  "send_asset", "sendasset", "spotsend", "usdsend", "token_delegate", "c_deposit", "c_withdraw")

# Conteneurs : jamais d'acces a l'hote.
INTERDITS_COMPOSE = ("docker.sock", "privileged", "network_mode: host", "network_mode: \"host\"", "pid: host", "cap_add", "devices:",
                     "/etc", "/root/.ssh", "/opt/deployeur", "- /:/", "userns_mode", "ipc: host")

DESTINATIONS = {"/opt/moonshot2", "/opt/peanut2", "/opt/recolteur", "/opt/tableau", "/root/usine"}
SOURCES_TEST = ("/root/usine", "/root/sp-replay", "{stage}")

ENV_PERMIS = {"MODE": ("observation", "reel"), "COINS": None, "MIN_DAY_VOLUME_USD": (0, 1e10), "RISK_PER_TRADE": (0, 0.01),
              "MAX_LEVERAGE": (1, 5), "BARS": (600, 1000), "SIGNAL_DELAY_S": (20, 600), "FETCH_PAUSE_S": (0, 5),
              "CAPITAL_PAPIER": (10, 100000), "BOT_PREFIX": None, "LOOP_S": (30, 600)}
NOM_FICHIER = re.compile(r"^[A-Za-z0-9_.\-/]+$")

def _files(root, exts):
    for d, _, fs in os.walk(root):
        if "/.git" in d: continue
        for f in fs:
            if f.endswith(exts): yield os.path.join(d, f)

def verifier(arbre):
    v = []
    for rel in CONFIG_BOTS:
        p = os.path.join(arbre, rel)
        if not os.path.exists(p): v.append(f"{rel} absent : bornes illisibles"); continue
        src = open(p, encoding="utf-8").read()
        for ligne in LIGNES_BORNES:
            if ligne not in src: v.append(f"borne modifiee ou retiree dans {rel} : {ligne.split(' =')[0]}")
    for p in _files(arbre, (".py", ".sh")):
        if "/tests/" in p or p.endswith("/deployeur/bornes.py"): continue      # tests sans reseau ; la constitution cite les mots interdits
        low = open(p, encoding="utf-8", errors="ignore").read().lower().replace(" ", "")
        for mot in INTERDITS_CODE:
            if mot in low: v.append(f"appel interdit « {mot} » dans {os.path.relpath(p, arbre)}")
    for p in _files(arbre, (".yml", ".yaml")):
        txt = open(p, encoding="utf-8", errors="ignore").read()
        for mot in INTERDITS_COMPOSE:
            if mot in txt: v.append(f"option interdite « {mot} » dans {os.path.relpath(p, arbre)}")
    v += verifier_cibles(arbre) + verifier_env(arbre)
    return v

def verifier_cibles(arbre):
    p = os.path.join(arbre, "deploy", "cibles.json")
    if not os.path.exists(p): return ["deploy/cibles.json absent"]
    try: cibles = json.load(open(p))
    except Exception as ex: return [f"deploy/cibles.json illisible : {type(ex).__name__}"]
    v = []
    for c in cibles:
        nom = c.get("nom", "?")
        if c.get("dest") not in DESTINATIONS: v.append(f"cible {nom} : destination interdite {c.get('dest')}")
        for f in c.get("fichiers", []):
            if f.startswith("/") or ".." in f or not NOM_FICHIER.match(f) or f.startswith(".env") or f == "data": v.append(f"cible {nom} : fichier interdit {f}")
        for vol in c.get("test_volumes", []):
            src = vol.split(":")[0]
            if not vol.endswith(":ro") or not any(src == s or src.startswith(s + "/") for s in SOURCES_TEST):
                v.append(f"cible {nom} : volume de test interdit {vol}")
    return v

def verifier_env(arbre):
    d = os.path.join(arbre, "deploy", "env"); v = []
    if not os.path.isdir(d): return v
    for f in os.listdir(d):
        if not f.endswith(".json"): continue
        try: env = json.load(open(os.path.join(d, f)))
        except Exception: v.append(f"deploy/env/{f} illisible"); continue
        for k, val in env.items():
            if k not in ENV_PERMIS: v.append(f"deploy/env/{f} : variable interdite {k}"); continue
            borne = ENV_PERMIS[k]; s = str(val)
            if "\n" in s or "=" in s: v.append(f"deploy/env/{f} : valeur invalide pour {k}"); continue
            if isinstance(borne, tuple) and isinstance(borne[0], str):
                if s not in borne: v.append(f"deploy/env/{f} : {k} doit valoir {' ou '.join(borne)}")
            elif isinstance(borne, tuple):
                try: x = float(s)
                except ValueError: v.append(f"deploy/env/{f} : {k} non numerique"); continue
                if not borne[0] <= x <= borne[1]: v.append(f"deploy/env/{f} : {k} hors bornes {borne}")
            elif not re.match(r"^[A-Za-z0-9,._ \-]{0,400}$", s) and not k == "BOT_PREFIX":
                v.append(f"deploy/env/{f} : valeur invalide pour {k}")
    return v
