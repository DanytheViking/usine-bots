"""Deployeur de l'usine (VPS, lance par cron toutes les 10 minutes, en root).
A chaque passage :
  1. lit la branche main du depot prive ; un nouveau commit est extrait dans un dossier de travail ;
  2. constitution (bornes.py, locale, jamais mise a jour par le depot) : une violation et tout le commit est refuse ;
  3. pour chaque cible dont la source a change : image candidate, tests sans reseau, sauvegarde, copie, redemarrage,
     controle de sante, retour automatique a la version precedente en cas d'echec ;
  4. travaux demandes par le depot (jobs/*.json), types fixes, executes en conteneur ;
  5. messages du depot (messages/*.md) relayes sur Telegram ;
  6. rapport d'etat pousse sur la branche rapports (sans cle ni secret).
Aucune cle n'est lue ni ecrite par ce programme, sauf le jeton Telegram pour envoyer les messages.
    python3 /opt/deployeur/deployeur.py [--adopter] [--une-fois]"""
import os, re, sys, json, time, shutil, fcntl, tarfile, subprocess, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bornes

RACINE = os.getenv("DEPLOYEUR_RACINE", "")                                  # prefixe de chemins (tests seulement)
def R(p): return RACINE + p
BASE = os.getenv("DEPLOYEUR_BASE", "/opt/deployeur")
INSTALL = os.getenv("DEPLOYEUR_INSTALL", os.path.dirname(os.path.abspath(__file__)))
PUBLIC = os.getenv("DEPLOYEUR_PUBLIC", R("/opt/usine-public"))
FICHIERS_DEPLOYEUR = ("deployeur.py", "bornes.py", "installer.sh", "lanceur.sh")
REPO = os.path.join(BASE, "depot")
ETAT = os.path.join(BASE, "etat.json")
STAGE = os.path.join(BASE, "travail")
SAUVEGARDES = os.path.join(BASE, "sauvegardes")
JOBS = R("/root/jobs")
LOG = os.path.join(BASE, "deployeur.log")
H4 = 4 * 3600
FENETRE_AVANT, FENETRE_APRES = 3 * 60, 8 * 60
SANTE_ATTENTE = 90
TYPES_JOBS = ("usine", "recolteur_rapport", "prevol", "controle")
MODULE = re.compile(r"^usine\.[a-z0-9_]+$")
ARG = re.compile(r"^[A-Za-z0-9_./=:\-]{1,200}$")
ID = re.compile(r"^[a-z0-9][a-z0-9\-]{0,40}$")

def redact(s):
    s = re.sub(r"0x[0-9a-fA-F]{64}", "[cle]", str(s))
    s = re.sub(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b", "[jeton]", s)
    return re.sub(r"sk-ant-[A-Za-z0-9_\-]{10,}", "[cle]", s)

class Ctx:
    """Acces au monde exterieur (commandes, horloge, Telegram), remplacable dans les tests."""
    def __init__(self):
        self.now = time.time; self.sleep = time.sleep
    def run(self, cmd, timeout=1800, cwd=None, env=None):
        try:
            r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=timeout)
            return r.returncode, (r.stdout + r.stderr)[-20000:]
        except subprocess.TimeoutExpired: return 124, "delai depasse"
    def send(self, text):
        tok = chat = ""
        try:
            for l in open(R("/opt/moonshot2/.env")):
                if l.startswith("TELEGRAM_BOT_TOKEN="): tok = l.split("=", 1)[1].strip().strip('"')
                if l.startswith("TELEGRAM_CHAT_ID="): chat = l.split("=", 1)[1].strip().strip('"')
        except OSError: return False
        if not (tok and chat): return False
        import urllib.request
        body = json.dumps({"chat_id": chat, "text": ("🏭 Usine\n" + redact(text))[:4000], "disable_web_page_preview": True}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", body, {"Content-Type": "application/json"}), timeout=10)
            return True
        except Exception: return False

def log(msg):
    os.makedirs(BASE, exist_ok=True)
    with open(LOG, "a") as f: f.write(dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " " + redact(msg) + "\n")

def load_state():
    try: return json.load(open(ETAT))
    except Exception: return {"deploye": None, "par_cible": {}, "refuse": None, "jobs": {}, "messages": [], "echecs": {}, "dernier_rapport": 0}

def save_state(s):
    tmp = ETAT + ".tmp"; json.dump(s, open(tmp, "w"), indent=1); os.replace(tmp, ETAT)

def git(ctx, *args, timeout=300):
    return ctx.run(["git", "-C", REPO, *args], timeout=timeout)

def extract(ctx, commit, dest):
    shutil.rmtree(dest, ignore_errors=True); os.makedirs(dest)
    rc, out = ctx.run(["sh", "-c", f"git -C {REPO} archive {commit} | tar -x -C {dest}"])
    if rc: raise RuntimeError("extraction du commit impossible : " + out[-300:])

def changed(ctx, old, new):
    if old is None: return None                                           # premier passage : tout est considere
    rc, out = git(ctx, "diff", "--name-only", old, new)
    if rc: return None
    return [l.strip() for l in out.splitlines() if l.strip()]

def entree(ctx, commit, nom):
    rc, out = git(ctx, "show", f"{commit}:deploy/cibles.json")
    try: return next(({k: v for k, v in c.items() if k != "audit"} for c in json.loads(out) if c.get("nom") == nom), None) if rc == 0 else None
    except ValueError: return None

def concerne(cible, paths, ctx=None, old=None, new=None):
    if paths is None: return True
    src = cible["source"].rstrip("/") + "/"
    if any(p.startswith(src) for p in paths) or f"deploy/env/{cible['nom']}.json" in paths: return True
    if "deploy/cibles.json" in paths:
        if ctx is None or old is None: return True
        return entree(ctx, old, cible["nom"]) != entree(ctx, new, cible["nom"])
    return False

def audit(ctx, cible, new, stage, chemins=None):
    """Cibles en argent reel et Deployeur : le dernier commit qui les touche doit etre approuve par l'Auditeur
    (audits/<sha>.json, verdict « approuve »). Renvoie True, False (refuse) ou None (en attente)."""
    if chemins is None:
        if not cible.get("audit"): return True
        chemins = [cible["source"], f"deploy/env/{cible['nom']}.json"]
    rc, sha = git(ctx, "log", "-1", "--format=%H", new, "--", *chemins); sha = sha.strip()
    if rc or not sha: return True
    p = os.path.join(stage, "audits", f"{sha}.json")
    if not os.path.exists(p): return None
    try: v = json.load(open(p))
    except ValueError: return False
    return v.get("commit") == sha and v.get("verdict") == "approuve"

def en_fenetre_4h(ctx):
    t = int(ctx.now()) % H4
    return t < FENETRE_APRES or t > H4 - FENETRE_AVANT

# ================================================================ deploiement d'une cible
def tests(ctx, cible, stage, tag):
    for t in cible.get("tests", []):
        cmd = ["docker", "run", "--rm", "--network", "none", "--tmpfs", "/tmp"]
        for vol in cible.get("test_volumes", []): cmd += ["-v", vol.replace("{stage}", stage)]
        for k, v in {"DATA_DIR": "/tmp/t", **cible.get("test_env", {})}.items(): cmd += ["-e", f"{k}={v}"]
        if cible.get("test_workdir"): cmd += ["-w", cible["test_workdir"]]
        cmd += [tag, "python3", "-B", t]
        rc, out = ctx.run(cmd, timeout=1800)
        last = [l for l in out.splitlines() if re.match(r"^\d+/\d+ tests ok", l)]
        if rc or not last: return False, f"{t} : " + (out.strip().splitlines()[-1] if out.strip() else f"code {rc}")
    return True, "tests ok"

def sauvegarder(cible, ts):
    os.makedirs(SAUVEGARDES, exist_ok=True)
    arc = os.path.join(SAUVEGARDES, f"{cible['nom']}-{ts}.tgz")
    with tarfile.open(arc, "w:gz") as tf:
        for f in cible["fichiers"] + [".env"]:
            p = os.path.join(R(cible["dest"]), f)
            if os.path.exists(p): tf.add(p, arcname=f)
    os.chmod(arc, 0o600)
    old = sorted(f for f in os.listdir(SAUVEGARDES) if f.startswith(cible["nom"] + "-"))
    for f in old[:-10]: os.remove(os.path.join(SAUVEGARDES, f))                # 10 sauvegardes par cible
    return arc

def restaurer(cible, arc):
    for f in cible["fichiers"]:
        p = os.path.join(R(cible["dest"]), f)
        if os.path.isdir(p): shutil.rmtree(p)
        elif os.path.exists(p): os.remove(p)
    with tarfile.open(arc) as tf: tf.extractall(R(cible["dest"]), filter="data")

def copier(cible, src):
    os.makedirs(R(cible["dest"]), exist_ok=True)
    for f in cible["fichiers"]:
        a, b = os.path.join(src, f), os.path.join(R(cible["dest"]), f)
        if os.path.isdir(b): shutil.rmtree(b)
        elif os.path.exists(b): os.remove(b)
        if os.path.isdir(a): shutil.copytree(a, b)
        elif os.path.exists(a): shutil.copy2(a, b)

def appliquer_env(cible, env):
    p = os.path.join(R(cible["dest"]), ".env")
    lines = open(p).read().splitlines() if os.path.exists(p) else []
    for k, v in env.items():
        lines = [l for l in lines if not l.startswith(k + "=")] + [f"{k}={v}"]
    open(p, "w").write("\n".join(lines) + "\n"); os.chmod(p, 0o600)

def compose(ctx, cible, *args):
    out_all = ""
    for c in cible.get("composes", []):
        rc, out = ctx.run(["docker", "compose", "-p", c["projet"], "-f", os.path.join(R(cible["dest"]), c["fichier"]), *args], cwd=R(cible["dest"]))
        out_all += out
        if rc: return rc, out_all
    return 0, out_all

def sante(ctx, cible):
    """Services en marche, sans redemarrage pendant 30 s, statut frais si la cible en ecrit un."""
    def etat():
        res = {}
        for c in cible.get("composes", []):
            rc, out = ctx.run(["docker", "compose", "-p", c["projet"], "-f", os.path.join(R(cible["dest"]), c["fichier"]), "ps", "-a",
                               "--format", "{{.Name}} {{.State}}"], cwd=R(cible["dest"]))
            for l in out.splitlines():
                p = l.split()
                if len(p) >= 2: res[p[0]] = p[1]
        return res
    attendu = sum(c.get("services", 0) for c in cible.get("composes", []))
    ctx.sleep(SANTE_ATTENTE); a = etat()
    if sum(1 for s in a.values() if s == "running") < attendu: return False, f"services en marche : {a}"
    restarts = {n: ctx.run(["docker", "inspect", "-f", "{{.RestartCount}}", n])[1].strip() for n in a}
    ctx.sleep(30)
    if any(ctx.run(["docker", "inspect", "-f", "{{.RestartCount}}", n])[1].strip() != r for n, r in restarts.items()): return False, "redemarrages en boucle"
    if cible.get("statut"):
        p = os.path.join(R(cible["dest"]), cible["statut"])
        if not os.path.exists(p) or ctx.now() - os.path.getmtime(p) > 180: return False, "statut non mis a jour"
    return True, "en marche"

def deployer_cible(ctx, s, cible, commit, stage):
    nom = cible["nom"]; short = commit[:8]; src = os.path.join(stage, cible["source"])
    tag = f"usine-candidat-{nom}:{short}"
    rc, out = ctx.run(["docker", "build", "-q", "-t", tag, src], timeout=1800)
    if rc: return False, "construction de l'image impossible : " + out[-200:]
    ok, why = tests(ctx, cible, src, tag)
    ctx.run(["docker", "image", "rm", tag])
    if not ok: return False, "tests en echec : " + why
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    arc = sauvegarder(cible, ts)
    copier(cible, src)
    envp = os.path.join(stage, "deploy", "env", f"{nom}.json")
    if os.path.exists(envp): appliquer_env(cible, json.load(open(envp)))
    for cmd in cible.get("apres_copie", []):
        if cmd == "image_usine": ctx.run(["docker", "build", "-q", "-t", "usine-py:1", R(cible["dest"])], timeout=1800)
        if cmd == "donnees_10001":
            dd = os.path.join(R(cible["dest"]), "data"); os.makedirs(dd, exist_ok=True)
            try: os.chown(dd, 10001, 10001)
            except PermissionError: pass
    if not cible.get("composes"): return True, f"copie faite ({short})"
    rc, out = compose(ctx, cible, "up", "-d", "--build", "--remove-orphans")
    ok, why = (False, "demarrage impossible : " + out[-200:]) if rc else sante(ctx, cible)
    if ok: return True, f"deploye ({short}), {why}"
    restaurer(cible, arc); compose(ctx, cible, "up", "-d", "--build", "--remove-orphans")
    return False, f"echec apres deploiement ({why}) : version precedente restauree"

# ================================================================ travaux et messages
def lancer_job(ctx, job, deploye_ok):
    jid, typ = job.get("id", ""), job.get("type")
    if not ID.match(jid) or typ not in TYPES_JOBS: return "refuse : id ou type invalide"
    out = os.path.join(JOBS, jid); os.makedirs(out, exist_ok=True)
    name = f"job-{jid}"
    if typ == "usine":
        mod, args = job.get("module", ""), [str(a) for a in job.get("args", [])]
        if not MODULE.match(mod) or not all(ARG.match(a) for a in args): return "refuse : module ou arguments invalides"
        cmd = ["docker", "run", "-d", "--name", name] + ([] if job.get("reseau") else ["--network", "none"]) + [
               "-v", "/root/usine:/app:ro", "-v", "/root/sp-replay:/sp:ro", "-v", "/root/donnees-usine:/d", "-v", f"{out}:/out",
               "-w", "/app", "-e", "PYTHONPATH=/sp:/app", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "PYTHONUNBUFFERED=1",
               "usine-py:1", "python", "-B", "-m", mod, *args]
    elif typ == "controle":
        return controle(ctx, jid)
    elif typ == "recolteur_rapport":
        cmd = ["docker", "compose", "-p", "recolteur", "-f", "/opt/recolteur/docker-compose.yml", "run", "-d", "--name", name, "--no-deps",
               "recolteur", "python3", "-m", "recolteur.rapport"]
    else:
        bot = job.get("bot")
        if bot not in ("moonshot2", "peanut2"): return "refuse : bot inconnu"
        f = "docker-compose.yml" if bot == "moonshot2" else "docker-compose.peanut.yml"
        cmd = ["docker", "compose", "-p", bot, "-f", f"/opt/{bot}/{f}", "run", "-d", "--name", name, "--no-deps", "moon",
               "python3", "-m", "moon.bot", "--preflight"]
    ctx.run(["docker", "rm", "-f", name])
    rc, o = ctx.run(cmd, cwd="/opt")
    return "lance" if rc == 0 else "echec au lancement : " + o[-200:]

def adresses():
    out = {}
    try:
        for l in open(R("/opt/tableau/.env")):
            k, _, v = l.strip().partition("=")
            if k in ("MOON_ACCOUNT", "LABO_ACCOUNT") and re.match(r"^0x[0-9a-fA-F]{40}$", v.strip().strip('"')): out[k] = v.strip().strip('"')
    except OSError: pass
    return out

def controle(ctx, jid):
    """Controleur : reel contre simule (entrees, frais, funding), sur les fills publics Hyperliquid et les journaux des bots."""
    out = os.path.join(JOBS, jid); os.makedirs(out, exist_ok=True); ad = adresses(); bots = []
    if ad.get("MOON_ACCOUNT"): bots.append(f"moonshot2:{ad['MOON_ACCOUNT']}:/b/moonshot2/journal.jsonl")
    if ad.get("LABO_ACCOUNT"): bots.append(f"peanut2:{ad['LABO_ACCOUNT']}:/b/peanut2/journal.jsonl")
    if not bots: return "refuse : adresses publiques des comptes introuvables"
    cmd = ["docker", "run", "--rm", "--name", f"job-{jid}", "-v", "/root/usine:/app:ro", "-v", "/root/sp-replay:/sp:ro",
           "-v", "/opt/moonshot2/data:/b/moonshot2:ro", "-v", "/opt/peanut2/data:/b/peanut2:ro", "-v", f"{out}:/out",
           "-w", "/app", "-e", "PYTHONPATH=/sp:/app", "-e", "PYTHONDONTWRITEBYTECODE=1", "usine-py:1", "python", "-B", "-m", "usine.controle", "--out", "/out"]
    for b in bots: cmd += ["--bot", b]
    rc, o = ctx.run(cmd, timeout=600)
    p = os.path.join(out, "controle.json")
    if rc or not os.path.exists(p): return "echec : " + o.strip()[-200:]
    rep = json.load(open(p)); os.makedirs(PUBLIC, exist_ok=True); shutil.copy2(p, os.path.join(PUBLIC, "controle.json"))
    os.chmod(os.path.join(PUBLIC, "controle.json"), 0o644)
    ctx.send("🧾 Controleur : " + rep.get("resume", "rapport ecrit"))
    return "fait : " + rep.get("verdict", "?")

def controle_hebdo(ctx, s):
    t = dt.datetime.fromtimestamp(ctx.now(), dt.timezone.utc)
    sem = f"controle-{t.isocalendar()[0]}-s{t.isocalendar()[1]:02d}"
    if t.weekday() == 0 and t.hour >= 6 and sem not in s["jobs"]:
        st = controle(ctx, sem); s["jobs"][sem] = {"etat": st, "debut": int(ctx.now()), "type": "controle"}; log(f"job {sem} : {st}")

def jobs(ctx, s, stage):
    d = os.path.join(stage, "jobs")
    if not os.path.isdir(d): return
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"): continue
        try: job = json.load(open(os.path.join(d, f)))
        except Exception: continue
        jid = job.get("id", f[:-5])
        if jid in s["jobs"]: continue
        st = lancer_job(ctx, job, True); s["jobs"][jid] = {"etat": st, "debut": int(ctx.now()), "type": job.get("type")}
        log(f"job {jid} : {st}"); ctx.send(f"Travail {jid} ({job.get('type')}) : {st}")

def messages(ctx, s, stage):
    d = os.path.join(stage, "messages")
    if not os.path.isdir(d): return
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md") or f in s["messages"]: continue
        ctx.send(open(os.path.join(d, f), encoding="utf-8").read()[:3500]); s["messages"].append(f)

# ================================================================ rapport
def rapport(ctx, s):
    d = os.path.join(BASE, "rapport"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    rc, ps = ctx.run(["docker", "ps", "-a", "--format", "{{.Names}} | {{.Status}} | {{.Image}}"])
    etat = {"ts": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "deploye": s.get("deploye"), "refuse": s.get("refuse"),
            "par_cible": s.get("par_cible"), "echecs": s.get("echecs"), "jobs": s.get("jobs"), "conteneurs": ps.strip().splitlines()}
    for bot, p in (("moonshot2", "/opt/moonshot2/data/status.json"), ("peanut2", "/opt/peanut2/data/status.json"), ("recolteur", "/opt/recolteur/data/status.json")):
        try: etat[bot] = json.load(open(R(p)))
        except Exception as ex: etat[bot] = f"illisible ({type(ex).__name__})"
    open(os.path.join(d, "etat.json"), "w").write(redact(json.dumps(etat, indent=1, ensure_ascii=False, default=str)))
    for bot, p in (("moonshot2", "/opt/moonshot2/data/journal.jsonl"), ("peanut2", "/opt/peanut2/data/journal.jsonl"), ("recolteur", "/opt/recolteur/data/journal.jsonl")):
        try:
            lines = open(R(p), encoding="utf-8").read().splitlines()[-60:]
            open(os.path.join(d, f"journal-{bot}.jsonl"), "w").write(redact("\n".join(lines)) + "\n")
        except OSError: pass
    for jid in list(s.get("jobs", {}))[-30:]:
        rc, out = ctx.run(["docker", "logs", "--tail", "60", f"job-{jid}"])
        rc2, st = ctx.run(["docker", "inspect", "-f", "{{.State.Status}} {{.State.ExitCode}}", f"job-{jid}"])
        os.makedirs(os.path.join(d, "jobs"), exist_ok=True)
        open(os.path.join(d, "jobs", f"{jid}.txt"), "w").write(redact(f"etat conteneur : {st.strip()}\n\n{out}"))
        src = os.path.join(JOBS, jid)
        if os.path.isdir(src):
            for f in os.listdir(src):
                if f.endswith((".md", ".json")) and os.path.getsize(os.path.join(src, f)) < 2_000_000:
                    shutil.copy2(os.path.join(src, f), os.path.join(d, "jobs", f"{jid}-{f}"))
    for r in sorted(os.listdir(R("/root"))) if os.path.isdir(R("/root")) else []:
        p = os.path.join(R("/root"), r, "verdicts.md")
        if r.startswith("rapport-") and os.path.exists(p):
            os.makedirs(os.path.join(d, "verdicts"), exist_ok=True); shutil.copy2(p, os.path.join(d, "verdicts", f"{r}.md"))
    for bot in ("moonshot2", "peanut2"):                                        # avis des collegues : bilans de Fable Chercheur
        src = R(f"/opt/{bot}/data/chercheur")
        if os.path.isdir(src):
            os.makedirs(os.path.join(d, "chercheur"), exist_ok=True)
            for f in sorted(x for x in os.listdir(src) if x.endswith(".md"))[-4:]:
                open(os.path.join(d, "chercheur", f"{bot}-{f}"), "w").write(redact(open(os.path.join(src, f), encoding="utf-8").read()))
    try: open(os.path.join(d, "deployeur.log"), "w").write("\n".join(open(LOG).read().splitlines()[-200:]) + "\n")
    except OSError: pass
    cmds = [["git", "-C", d, "init", "-q", "-b", "rapports"], ["git", "-C", d, "add", "-A"],
            ["git", "-C", d, "-c", "user.name=usine", "-c", "user.email=usine@localhost", "commit", "-q", "-m", "etat " + etat["ts"]],
            ["git", "-C", d, "push", "-q", "-f", REMOTE, "rapports:rapports"]]
    for c in cmds:
        rc, out = ctx.run(c, timeout=120)
        if rc: log("rapport : " + out[-200:]); return False
    return True

REMOTE = os.getenv("DEPLOYEUR_REMOTE", "git@github-usine:DanytheViking/usine-bots.git")

# ================================================================ mise a jour du Deployeur lui-meme
def sha(p):
    import hashlib
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None

def auto_maj(ctx, stage):
    """Le depot contient deployeur/ : si une version differente passe ses propres tests, elle remplace celle-ci.
    L'ancienne est gardee dans precedent/ ; lanceur.sh la restaure apres trois echecs de suite."""
    src = os.path.join(stage, "deployeur")
    if not os.path.isfile(os.path.join(src, "deployeur.py")): return None
    if all(sha(os.path.join(src, f)) == sha(os.path.join(INSTALL, f)) for f in FICHIERS_DEPLOYEUR if os.path.exists(os.path.join(src, f))):
        return None
    rc, out = ctx.run(["python3", "-B", os.path.join(src, "tests", "test_deployeur.py")], timeout=1200, env={"DEPOT_SRC": stage})
    if rc or not re.search(r"^\d+/\d+ tests ok", out, re.M):
        return False, "nouvelle version du Deployeur refusee : tests en echec"
    prev = os.path.join(BASE, "precedent"); shutil.rmtree(prev, ignore_errors=True); os.makedirs(prev)
    for f in FICHIERS_DEPLOYEUR:
        if os.path.exists(os.path.join(INSTALL, f)): shutil.copy2(os.path.join(INSTALL, f), prev)
    if os.path.isdir(os.path.join(INSTALL, "tests")): shutil.copytree(os.path.join(INSTALL, "tests"), os.path.join(prev, "tests"))
    for f in FICHIERS_DEPLOYEUR:
        if os.path.exists(os.path.join(src, f)): shutil.copy2(os.path.join(src, f), os.path.join(INSTALL, f))
    if os.path.isdir(os.path.join(src, "tests")):
        shutil.rmtree(os.path.join(INSTALL, "tests"), ignore_errors=True); shutil.copytree(os.path.join(src, "tests"), os.path.join(INSTALL, "tests"))
    return True, f"Deployeur mis a jour par le depot ({sha(os.path.join(INSTALL, 'deployeur.py'))[:12]}), ancienne version gardee"

# ================================================================ cycle
def cycle(ctx, adopter=False):
    s = load_state()
    rc, out = git(ctx, "fetch", "-q", "origin", "main")
    if rc: log("fetch : " + out[-200:]); return s
    rc, new = git(ctx, "rev-parse", "origin/main"); new = new.strip()
    stage = os.path.join(STAGE, "commit")
    if new != s.get("deploye") and new != s.get("refuse"):
        extract(ctx, new, stage)
        viol = bornes.verifier(stage)
        if viol:
            s["refuse"] = new; log(f"commit {new[:8]} refuse : {viol}")
            ctx.send(f"Commit {new[:8]} REFUSE par la constitution :\n- " + "\n- ".join(viol[:10]))
        elif adopter:
            s["deploye"] = new; s["par_cible"] = {c["nom"]: new for c in json.load(open(os.path.join(stage, "deploy", "cibles.json")))}
            log(f"adoption de {new[:8]} sans deploiement"); ctx.send(f"Deployeur installe : etat actuel adopte ({new[:8]}). Surveillance du depot toutes les 10 minutes.")
        else:
            cibles = json.load(open(os.path.join(stage, "deploy", "cibles.json"))); termine = True
            for c in cibles:
                if s["par_cible"].get(c["nom"]) == new: continue
                old = s["par_cible"].get(c["nom"])
                if not concerne(c, changed(ctx, old, new), ctx, old, new): s["par_cible"][c["nom"]] = new; continue
                if s["echecs"].get(c["nom"]) == new: continue
                a = audit(ctx, c, new, stage)
                if a is None:
                    termine = False
                    if s.setdefault("attente_audit", {}).get(c["nom"]) != new:
                        s["attente_audit"][c["nom"]] = new; log(f"{c['nom']} {new[:8]} : en attente de l'Auditeur"); ctx.send(f"{c['nom']} : mise a jour {new[:8]} en attente de l'Auditeur")
                    continue
                if a is False:
                    s["echecs"][c["nom"]] = new; log(f"{c['nom']} {new[:8]} : refuse par l'Auditeur"); ctx.send(f"{c['nom']} : mise a jour {new[:8]} REFUSEE par l'Auditeur"); continue
                if c.get("fenetre_4h") and en_fenetre_4h(ctx): termine = False; continue
                try: ok, why = deployer_cible(ctx, s, c, new, stage)
                except Exception as ex: ok, why = False, f"erreur {type(ex).__name__} : {ex}"
                log(f"{c['nom']} {new[:8]} : {why}"); ctx.send(f"{c['nom']} : {why}")
                if ok: s["par_cible"][c["nom"]] = new
                else: s["echecs"][c["nom"]] = new
                save_state(s)
            if termine: s["deploye"] = new
    if os.path.isdir(stage) and s.get("deploye") == new:
        if s.get("maj_vue") != new:
            a = audit(ctx, None, new, stage, ["deployeur"])
            if a:
                s["maj_vue"] = new; r = auto_maj(ctx, stage)
                if r: log(r[1]); ctx.send(r[1])
            elif a is False:
                s["maj_vue"] = new; ctx.send(f"Nouvelle version du Deployeur {new[:8]} REFUSEE par l'Auditeur")
        jobs(ctx, s, stage); messages(ctx, s, stage)
        controle_hebdo(ctx, s)
    save_state(s)
    try: publier(ctx, s)
    except Exception as ex: log(f"publication : {type(ex).__name__}")
    if ctx.now() - s.get("dernier_rapport", 0) >= 3300 or adopter:
        if rapport(ctx, s): s["dernier_rapport"] = int(ctx.now()); save_state(s)
    return s

def publier(ctx, s):
    """Vue publique pour le tableau de bord (aucun secret) : etat, conteneurs, commits recents, journal, disque."""
    d = PUBLIC; os.makedirs(d, exist_ok=True)
    rc, ps = ctx.run(["docker", "ps", "-a", "--format", "{{.Names}} | {{.Status}}"])
    rc2, lg = git(ctx, "log", "origin/main", "-15", "--format=%h%x1f%cI%x1f%s")
    commits = [dict(zip(("sha", "date", "message"), l.split("\x1f"))) for l in lg.splitlines() if l.count("\x1f") == 2] if rc2 == 0 else []
    try: journal = open(LOG).read().splitlines()[-40:]
    except OSError: journal = []
    du = shutil.disk_usage("/")
    out = {"ts": dt.datetime.now(dt.timezone.utc).isoformat()[:19] + "Z", "deploye": s.get("deploye"), "refuse": s.get("refuse"),
           "echecs": s.get("echecs"), "jobs": {k: v.get("etat") for k, v in (s.get("jobs") or {}).items()},
           "conteneurs": sorted(ps.strip().splitlines()) if rc == 0 else [], "commits": commits, "journal": journal,
           "disque": {"libre_go": round(du.free / 1e9, 1), "total_go": round(du.total / 1e9, 1)}}
    tmp = os.path.join(d, "etat.json.tmp"); open(tmp, "w").write(redact(json.dumps(out, ensure_ascii=False)))
    os.chmod(tmp, 0o644); os.replace(tmp, os.path.join(d, "etat.json"))

def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    os.makedirs(BASE, exist_ok=True)
    with open(os.path.join(BASE, ".verrou"), "w") as lk:
        try: fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return 0
        cycle(Ctx(), adopter="--adopter" in a)
    return 0

if __name__ == "__main__":
    sys.exit(main())
