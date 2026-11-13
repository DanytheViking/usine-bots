"""Tests hors ligne du Deployeur : vrai git (depot local), faux Docker, faux Telegram.
    python3 -B tests/test_deployeur.py"""
import os, sys, json, shutil, tempfile, subprocess, importlib
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, HERE)
DEPOT_SRC = os.getenv("DEPOT_SRC", os.path.join(os.path.dirname(HERE), "depot"))

def sh(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()

def mini_tree(d):
    """Copie reduite du depot : config des bots, cibles, compose, un fichier par cible."""
    for rel in ("moonshot2/moon/config.py", "moonshot2/docker-compose.yml", "moonshot2/docker-compose.peanut.yml", "moonshot2/Dockerfile",
                "recolteur/docker-compose.yml", "recolteur/Dockerfile", "tableau/docker-compose.yml", "tableau/docker-compose.telecommande.yml",
                "tableau/Dockerfile", "usine/Dockerfile", "deploy/cibles.json"):
        os.makedirs(os.path.dirname(os.path.join(d, rel)), exist_ok=True); shutil.copy2(os.path.join(DEPOT_SRC, rel), os.path.join(d, rel))
    c = [{k: v for k, v in x.items() if k != "audit"} for x in json.load(open(os.path.join(d, "deploy/cibles.json")))]   # audit : teste a part
    json.dump(c, open(os.path.join(d, "deploy/cibles.json"), "w"))
    for x in ("moonshot2/moon/bot.py", "moonshot2/tests/test_moon.py", "recolteur/recolteur/main.py", "tableau/tableau/server.py", "usine/usine/sim.py"):
        os.makedirs(os.path.dirname(os.path.join(d, x)), exist_ok=True); open(os.path.join(d, x), "w").write("x = 1\n")

class World:
    def __init__(self):
        self.root = tempfile.mkdtemp()
        os.environ["DEPLOYEUR_BASE"] = os.path.join(self.root, "base"); os.environ["DEPLOYEUR_RACINE"] = os.path.join(self.root, "fs")
        self.origin = os.path.join(self.root, "origin.git"); self.work = os.path.join(self.root, "work")
        sh("git", "init", "-q", "--bare", "-b", "main", self.origin)
        os.makedirs(self.work); mini_tree(self.work)
        for c in (["git", "init", "-q", "-b", "main"], ["git", "add", "-A"], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init"],
                  ["git", "remote", "add", "origin", self.origin], ["git", "push", "-q", "origin", "main"]): sh(*c, cwd=self.work)
        os.environ["DEPLOYEUR_REMOTE"] = self.origin
        self.install = os.path.join(self.root, "install"); os.makedirs(self.install)
        for f in ("deployeur.py", "bornes.py"): shutil.copy2(os.path.join(HERE, f), self.install)
        os.environ["DEPLOYEUR_INSTALL"] = self.install
        import deployeur as D; importlib.reload(D); self.D = D
        sh("git", "clone", "-q", self.origin, D.REPO)
        for p in ("/opt/moonshot2/data", "/opt/peanut2/data", "/opt/recolteur/data", "/opt/tableau", "/root/usine"): os.makedirs(D.R(p), exist_ok=True)
        open(D.R("/opt/moonshot2/.env"), "w").write("MODE=reel\nHL_AGENT_KEY=0x" + "1" * 64 + "\n")
        self.ctx = FakeCtx(self)

    def commit(self, rel, content, msg="maj"):
        p = os.path.join(self.work, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "w").write(content)
        for c in (["git", "add", "-A"], ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", msg], ["git", "push", "-q", "origin", "main"]): sh(*c, cwd=self.work)
        return sh("git", "rev-parse", "HEAD", cwd=self.work)

class FakeCtx:
    def __init__(self, w):
        self.w, self.t, self.sent, self.docker = w, 1_794_000_000 + 3600, [], []
        self.tests_ok, self.running, self.restarts, self.write_status = True, True, iter([]), True
    def now(self): return self.t
    def sleep(self, s):
        self.t += s
        if self.write_status:
            for b in ("moonshot2", "peanut2", "recolteur"):
                p = self.w.D.R(f"/opt/{b}/data/status.json"); open(p, "w").write("{}"); os.utime(p, (self.t, self.t))
    def send(self, text): self.sent.append(text); return True
    def run(self, cmd, timeout=1800, cwd=None, env=None):
        if cmd[0] != "docker":
            r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True); return r.returncode, r.stdout + r.stderr
        self.docker.append(cmd)
        if cmd[1] == "run" and "--network" in cmd and "python3" in cmd:
            if self.tests_ok == "muet": return 0, "rien\n"
            return (0, "7/7 tests ok\n") if self.tests_ok else (1, "ECHEC test_x\n1/2 tests ok\n")
        if cmd[1] == "compose" and "ps" in cmd:
            names = {"moonshot2": ["moonshot2", "moonshot2-garde", "moonshot2-chercheur"], "peanut2": ["peanut2", "peanut2-garde"],
                     "recolteur": ["recolteur"], "tableau": ["usine-tableau"], "telecommande": ["usine-telecommande"]}[cmd[3]]
            return 0, "\n".join(f"{n} {'running' if self.running else 'exited'}" for n in names)
        if cmd[1] == "inspect" and "{{.RestartCount}}" in cmd: return 0, next(self.restarts, "0")
        return 0, ""

def deployed_file(w, dest, rel): return os.path.join(w.D.R(dest), rel)

# ================================================================ constitution
def test_constitution_depot_reel_et_violations():
    import bornes
    assert bornes.verifier(DEPOT_SRC) == []
    d = tempfile.mkdtemp(); shutil.copytree(DEPOT_SRC, d, dirs_exist_ok=True)
    cfg = os.path.join(d, "moonshot2/moon/config.py"); src = open(cfg).read()
    open(cfg, "w").write(src.replace('min(_f("RISK_PER_TRADE", "0.01"), 0.01)', 'min(_f("RISK_PER_TRADE", "0.05"), 0.05)'))
    v = bornes.verifier(d); assert any("RISK_PER_TRADE" in x for x in v)
    open(cfg, "w").write(src)
    open(os.path.join(d, "moonshot2/moon/vol.py"), "w").write("ex.withdraw_from_bridge(1)\n")
    open(os.path.join(d, "recolteur/x.yml"), "w").write("services:\n  a:\n    privileged: true\n    volumes: [/var/run/docker.sock:/s]\n")
    v = bornes.verifier(d)
    assert any("withdraw" in x for x in v) and any("privileged" in x for x in v) and any("docker.sock" in x for x in v)

def test_constitution_cibles_et_env():
    import bornes
    d = tempfile.mkdtemp(); shutil.copytree(DEPOT_SRC, d, dirs_exist_ok=True)
    c = json.load(open(os.path.join(d, "deploy/cibles.json")))
    c[0]["dest"] = "/etc"; c[1]["fichiers"].append(".env"); c[2]["test_volumes"] = ["/root:/r:ro"]; c[3]["test_volumes"] = ["/root/usine:/u"]
    json.dump(c, open(os.path.join(d, "deploy/cibles.json"), "w"))
    json.dump({"MODE": "reel", "RISK_PER_TRADE": "0.02", "HL_AGENT_KEY": "x", "MAX_LEVERAGE": 3}, open(os.path.join(d, "deploy/env/peanut2.json"), "w"))
    v = bornes.verifier(d)
    for frag in ("destination interdite /etc", "fichier interdit .env", "volume de test interdit /root:/r:ro", "volume de test interdit /root/usine:/u",
                 "RISK_PER_TRADE hors bornes", "variable interdite HL_AGENT_KEY"): assert any(frag in x for x in v), frag
    assert not any("MAX_LEVERAGE" in x for x in v) and not any("MODE" in x for x in v)

# ================================================================ cycle
def test_adoption_puis_deploiement_cible():
    w = World(); D = w.D
    s = D.cycle(w.ctx, adopter=True)
    base = sh("git", "rev-parse", "HEAD", cwd=w.work)
    noms = {c["nom"] for c in json.load(open(os.path.join(w.work, "deploy/cibles.json")))}
    assert s["deploye"] == base and set(s["par_cible"]) == noms and {"moonshot2", "peanut2", "recolteur", "tableau", "usine"} <= noms
    assert not any(c[1] == "build" for c in w.ctx.docker) and "adopte" in w.ctx.sent[0]
    new = w.commit("recolteur/recolteur/main.py", "x = 2\n")
    w.ctx.docker.clear(); s = D.cycle(w.ctx)
    assert s["deploye"] == new and all(v == new for v in s["par_cible"].values())
    builds = [c for c in w.ctx.docker if c[1] == "build"]
    assert len(builds) == 1 and builds[0][-1].endswith("/recolteur")                          # seule la cible changee
    assert open(deployed_file(w, "/opt/recolteur", "recolteur/main.py")).read() == "x = 2\n"
    ups = [c for c in w.ctx.docker if c[1] == "compose" and "up" in c]
    assert ups and ups[0][3] == "recolteur" and any("recolteur : deploye" in m for m in w.ctx.sent)
    tests = [c for c in w.ctx.docker if c[1] == "run" and "--network" in c]
    assert tests and tests[0][tests[0].index("--network") + 1] == "none"

def test_tests_en_echec_rien_ne_change():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    open(deployed_file(w, "/opt/recolteur", "marqueur"), "w").write("avant")
    w.ctx.tests_ok = False; new = w.commit("recolteur/recolteur/main.py", "x = 3\n")
    s = D.cycle(w.ctx)
    assert s["echecs"]["recolteur"] == new and s["par_cible"]["recolteur"] != new
    assert not os.path.exists(deployed_file(w, "/opt/recolteur", "recolteur/main.py"))
    assert not any(c[1] == "compose" and "up" in c for c in w.ctx.docker) and any("tests en echec" in m for m in w.ctx.sent)
    n = len(w.ctx.docker); D.cycle(w.ctx); assert not any(c[1] == "build" for c in w.ctx.docker[n:])   # pas de nouvel essai du meme commit

def test_tests_sans_resultat_refuses():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.ctx.tests_ok = "muet"; new = w.commit("recolteur/recolteur/main.py", "x = 9\n")
    s = D.cycle(w.ctx); assert s["echecs"]["recolteur"] == new

def test_echec_non_rejoue_pendant_un_report():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.ctx.t = 1_794_000_000 // (4 * 3600) * (4 * 3600) + 120; w.ctx.tests_ok = False
    w.commit("moonshot2/moon/bot.py", "x = 8\n"); new = w.commit("recolteur/recolteur/main.py", "x = 8\n")
    s = D.cycle(w.ctx); assert s["echecs"]["recolteur"] == new and s["deploye"] != new
    n = len([c for c in w.ctx.docker if c[1] == "build"]); w.ctx.t += 60; D.cycle(w.ctx)
    assert len([c for c in w.ctx.docker if c[1] == "build"]) == n

def test_sante_ko_restaure_la_version_precedente():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    os.makedirs(deployed_file(w, "/opt/recolteur", "recolteur"), exist_ok=True)
    open(deployed_file(w, "/opt/recolteur", "recolteur/main.py"), "w").write("ancien\n")
    open(deployed_file(w, "/opt/recolteur", ".env"), "w").write("TELEGRAM_CHAT_ID=1\n")
    w.ctx.running = False; new = w.commit("recolteur/recolteur/main.py", "x = 4\n")
    s = D.cycle(w.ctx)
    assert s["echecs"]["recolteur"] == new and open(deployed_file(w, "/opt/recolteur", "recolteur/main.py")).read() == "ancien\n"
    assert open(deployed_file(w, "/opt/recolteur", ".env")).read() == "TELEGRAM_CHAT_ID=1\n"
    assert any("version precedente restauree" in m for m in w.ctx.sent)
    assert len([c for c in w.ctx.docker if c[1] == "compose" and "up" in c]) == 2

def test_redemarrages_en_boucle_detectes():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.ctx.restarts = iter(["0", "3"]); new = w.commit("recolteur/recolteur/main.py", "x = 5\n")
    s = D.cycle(w.ctx); assert s["echecs"]["recolteur"] == new and any("redemarrages en boucle" in m for m in w.ctx.sent)

def test_statut_fige_detecte():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    p = D.R("/opt/recolteur/data/status.json"); open(p, "w").write("{}"); os.utime(p, (w.ctx.t - 3600, w.ctx.t - 3600))
    w.ctx.write_status = False; new = w.commit("recolteur/recolteur/main.py", "x = 6\n")
    s = D.cycle(w.ctx); assert s["echecs"]["recolteur"] == new and any("statut non mis a jour" in m for m in w.ctx.sent)

def test_fenetre_4h_reporte_les_bots():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.ctx.t = 1_794_000_000 // (4 * 3600) * (4 * 3600) + 120                               # 2 min apres une cloture 4 h
    new = w.commit("moonshot2/moon/bot.py", "x = 7\n")
    s = D.cycle(w.ctx)
    assert s["deploye"] != new and s["par_cible"]["moonshot2"] != new and s["par_cible"]["recolteur"] == new
    assert not any(c[1] == "build" for c in w.ctx.docker)
    w.ctx.t += 20 * 60; s = D.cycle(w.ctx)
    assert s["deploye"] == new and s["par_cible"]["moonshot2"] == new and s["par_cible"]["peanut2"] == new

def test_env_applique_sans_toucher_aux_cles():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    open(deployed_file(w, "/opt/peanut2", ".env"), "w").write("MODE=observation\nHL_AGENT_KEY=secret\nCOINS=DOGE\n")
    new = w.commit("deploy/env/peanut2.json", json.dumps({"MODE": "reel", "COINS": "DOGE,WIF"}))
    s = D.cycle(w.ctx)
    env = open(deployed_file(w, "/opt/peanut2", ".env")).read().splitlines()
    assert "HL_AGENT_KEY=secret" in env and "MODE=reel" in env and "COINS=DOGE,WIF" in env and "MODE=observation" not in env
    assert s["par_cible"]["peanut2"] == new

def test_commit_refuse_par_la_constitution():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    src = open(os.path.join(w.work, "moonshot2/moon/config.py")).read()
    new = w.commit("moonshot2/moon/config.py", src.replace('"0.50"), 0.50)', '"0.90"), 0.90)'))
    s = D.cycle(w.ctx)
    assert s["refuse"] == new and s["deploye"] != new and not any(c[1] == "build" for c in w.ctx.docker)
    assert any("REFUSE" in m and "LINE_STOP" in m for m in w.ctx.sent)
    n = len(w.ctx.sent); D.cycle(w.ctx); assert len(w.ctx.sent) == n                         # refus annonce une seule fois

def test_jobs_et_messages():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.commit("jobs/verdicts-v4.json", json.dumps({"id": "verdicts-v4", "type": "usine", "module": "usine.verdicts_v3", "args": ["--spec", "specs/x.json"]}))
    w.commit("jobs/mauvais.json", json.dumps({"id": "mauvais", "type": "usine", "module": "os.system", "args": ["rm -rf /"]}))
    w.commit("jobs/shell.json", json.dumps({"id": "shell", "type": "bash", "commande": "rm -rf /", "bot": "peanut2"}))
    w.commit("jobs/prevol.json", json.dumps({"id": "prevol-p", "type": "prevol", "bot": "peanut2"}))
    w.commit("messages/2026-11-13-bilan.md", "Bilan du jour : tout va bien")
    s = D.cycle(w.ctx)
    assert s["jobs"]["verdicts-v4"]["etat"] == "lance" and s["jobs"]["mauvais"]["etat"].startswith("refuse") and s["jobs"]["shell"]["etat"].startswith("refuse")
    assert s["jobs"]["prevol-p"]["etat"] == "lance"
    run = [c for c in w.ctx.docker if "job-verdicts-v4" in c and c[1] == "run"][0]
    assert run[run.index("--network") + 1] == "none" and run[-6:] == ["python", "-B", "-m", "usine.verdicts_v3", "--spec", "specs/x.json"]
    assert "Bilan du jour : tout va bien" in w.ctx.sent
    n = len(w.ctx.sent); D.cycle(w.ctx); assert len(w.ctx.sent) == n                         # ni job ni message rejoue

def test_rapport_pousse_sans_secret():
    w = World(); D = w.D
    open(D.R("/opt/moonshot2/data/status.json"), "w").write(json.dumps({"mode": "reel", "fuite": "0x" + "ab" * 32}))
    open(D.R("/opt/moonshot2/data/journal.jsonl"), "w").write('{"a": "jeton 123456789:' + "A" * 35 + '"}\n')
    os.makedirs(D.R("/opt/moonshot2/data/chercheur"), exist_ok=True)
    for k in range(6): open(D.R(f"/opt/moonshot2/data/chercheur/bilan-2026-11-{10 + k}.md"), "w").write(f"bilan {k}")
    D.cycle(w.ctx, adopter=True)
    files = sh("git", "--git-dir", w.origin, "ls-tree", "-r", "--name-only", "rapports")
    assert "chercheur/moonshot2-bilan-2026-11-15.md" in files and "chercheur/moonshot2-bilan-2026-11-11.md" not in files
    out = sh("git", "--git-dir", w.origin, "show", "rapports:etat.json")
    assert '"mode": "reel"' in out and "ab" * 32 not in out and "[cle]" in out
    j = sh("git", "--git-dir", w.origin, "show", "rapports:journal-moonshot2.jsonl"); assert "A" * 35 not in j and "[jeton]" in j
    t0 = D.load_state()["dernier_rapport"]
    w.ctx.t += 600; D.cycle(w.ctx); assert D.load_state()["dernier_rapport"] == t0                         # rapport horaire
    w.ctx.t += 3600; D.cycle(w.ctx); assert D.load_state()["dernier_rapport"] > t0
    assert sh("git", "--git-dir", w.origin, "rev-list", "--count", "rapports") == "1"                   # branche ecrasee

def test_auto_mise_a_jour_du_deployeur():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    old = open(os.path.join(w.install, "deployeur.py")).read()
    w.commit("deployeur/tests/test_deployeur.py", "print('2/2 tests ok')\n")
    sha = w.commit("deployeur/deployeur.py", "VERSION = 2\n")
    D.cycle(w.ctx)
    assert open(os.path.join(w.install, "deployeur.py")).read() == old                     # pas d'audit : rien ne change
    w.commit(f"audits/{sha}.json", json.dumps({"commit": sha, "verdict": "approuve", "auditeur": "Auditeur"}))
    s = D.cycle(w.ctx)
    assert open(os.path.join(w.install, "deployeur.py")).read() == "VERSION = 2\n"
    assert open(os.path.join(D.BASE, "precedent", "deployeur.py")).read() == old
    assert any("Deployeur mis a jour par le depot" in m for m in w.ctx.sent)
    w.commit("deployeur/tests/test_deployeur.py", "import sys\nprint('1/2 tests ok')\nsys.exit(1)\n")
    sha = w.commit("deployeur/deployeur.py", "VERSION = 3\n")
    w.commit(f"audits/{sha}.json", json.dumps({"commit": sha, "verdict": "approuve"}))
    D.cycle(w.ctx)
    assert open(os.path.join(w.install, "deployeur.py")).read() == "VERSION = 2\n" and any("refusee" in m for m in w.ctx.sent)

def test_vue_publique_pour_le_tableau():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    w.commit("recolteur/recolteur/main.py", "x = 11\n", msg="Correction du recolteur")
    D.cycle(w.ctx)
    pub = json.load(open(os.path.join(D.PUBLIC, "etat.json")))
    assert pub["commits"][0]["message"] == "Correction du recolteur" and len(pub["commits"][0]["sha"]) >= 7
    assert pub["deploye"] and pub["disque"]["total_go"] > 0 and isinstance(pub["journal"], list)
    assert oct(os.stat(os.path.join(D.PUBLIC, "etat.json")).st_mode)[-3:] == "644"
    assert "HL_AGENT_KEY" not in json.dumps(pub) and "1" * 64 not in json.dumps(pub)

def with_audit_flags(w):
    c = json.load(open(os.path.join(w.work, "deploy/cibles.json")))
    for x in c:
        if x["nom"] in ("moonshot2", "peanut2"): x["audit"] = True
    return w.commit("deploy/cibles.json", json.dumps(c))

def test_audit_bloque_puis_libere_les_bots():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    flags = with_audit_flags(w); s = D.cycle(w.ctx)
    assert s["deploye"] == flags and not any(c[1] == "build" for c in w.ctx.docker)      # ajouter le drapeau ne redeploie rien
    w.ctx.t = 1_794_000_000 // (4 * 3600) * (4 * 3600) + 3600
    sha = w.commit("moonshot2/moon/bot.py", "x = 20\n")
    s = D.cycle(w.ctx)
    assert s["par_cible"]["moonshot2"] != sha and s["deploye"] != sha and any("en attente de l'Auditeur" in m for m in w.ctx.sent)
    n = len(w.ctx.sent); D.cycle(w.ctx); assert len(w.ctx.sent) == n                           # annonce une seule fois
    w.commit(f"audits/{sha}.json", json.dumps({"commit": sha, "verdict": "approuve"}))
    s = D.cycle(w.ctx); new = sh("git", "rev-parse", "HEAD", cwd=w.work)
    assert s["par_cible"]["moonshot2"] == new and s["par_cible"]["peanut2"] == new and s["deploye"] == new
    sha2 = w.commit("moonshot2/moon/bot.py", "x = 21\n")
    w.commit(f"audits/{sha2}.json", json.dumps({"commit": sha2, "verdict": "refuse", "raison": "stop du mauvais cote"}))
    s = D.cycle(w.ctx); new = sh("git", "rev-parse", "HEAD", cwd=w.work)
    assert s["echecs"]["moonshot2"] == new and any("REFUSEE par l'Auditeur" in m for m in w.ctx.sent)
    w.commit(f"audits/{sha2}.json", json.dumps({"commit": "autre", "verdict": "approuve"}))  # approbation d'un autre commit : refus
    s = D.cycle(w.ctx); new = sh("git", "rev-parse", "HEAD", cwd=w.work); assert s["echecs"]["moonshot2"] == new

def test_messages_relayes_pendant_l_attente_de_l_auditeur():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True); with_audit_flags(w); D.cycle(w.ctx)
    w.ctx.t = 1_794_000_000 // (4 * 3600) * (4 * 3600) + 3600
    sha = w.commit("moonshot2/moon/bot.py", "x = 30\n")
    w.commit("messages/2026-11-13-trade.md", "Trade XMR ouvert")
    w.commit("jobs/attente.json", json.dumps({"id": "attente", "type": "usine", "module": "usine.verdicts_v3", "args": []}))
    s = D.cycle(w.ctx)
    assert s["par_cible"]["moonshot2"] != sha and "Trade XMR ouvert" in w.ctx.sent and "attente" not in s["jobs"]
    n = len(w.ctx.sent); D.cycle(w.ctx); assert len(w.ctx.sent) == n                           # message relaye une seule fois
    w.commit("messages/2026-11-13-refus.md", "ne doit pas partir")
    w.commit("moonshot2/moon/config.py", open(os.path.join(w.work, "moonshot2/moon/config.py")).read().replace('_f("RISK_PER_TRADE", "0.01"), 0.01)', '_f("RISK_PER_TRADE", "0.05"), 0.05)'))
    s = D.cycle(w.ctx); assert s["refuse"] and "ne doit pas partir" not in w.ctx.sent       # commit refuse : rien n'est relaye

def test_audit_couvre_les_variables_du_bot():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True); with_audit_flags(w); D.cycle(w.ctx)
    base = sh("git", "log", "-1", "--format=%H", "--", "moonshot2", cwd=w.work)
    w.commit(f"audits/{base}.json", json.dumps({"commit": base, "verdict": "approuve"})); D.cycle(w.ctx)   # le code du bot est approuve
    w.ctx.t = 1_794_000_000 // (4 * 3600) * (4 * 3600) + 3600
    sha = w.commit("deploy/env/peanut2.json", json.dumps({"MODE": "reel"}))
    s = D.cycle(w.ctx); assert s["par_cible"]["peanut2"] != sha and s["par_cible"]["recolteur"] == sha

def test_controle_hebdomadaire():
    w = World(); D = w.D; D.cycle(w.ctx, adopter=True)
    open(D.R("/opt/tableau/.env"), "w").write("MOON_ACCOUNT=0x" + "a" * 40 + "\nLABO_ACCOUNT=0x" + "c" * 40 + "\nTELEGRAM_BOT_TOKEN=x\n")
    orig = w.ctx.run
    def run(cmd, timeout=1800, cwd=None, env=None):
        if cmd[:2] == ["docker", "run"] and "usine.controle" in cmd:
            out = cmd[cmd.index("-v", cmd.index("/opt/peanut2/data:/b/peanut2:ro")) + 1].split(":")[0]
            json.dump({"verdict": "CONFORME", "resume": "0 trade"}, open(os.path.join(out, "controle.json"), "w"))
            w.ctx.docker.append(cmd); return 0, ""
        return orig(cmd, timeout, cwd, env)
    w.ctx.run = run
    import datetime as dt
    lundi = int(dt.datetime(2026, 11, 16, 7, 0, tzinfo=dt.timezone.utc).timestamp()); w.ctx.t = lundi
    s = D.cycle(w.ctx)
    assert s["jobs"]["controle-2026-s47"]["etat"] == "fait : CONFORME" and any("Controleur" in m for m in w.ctx.sent)
    c = [x for x in w.ctx.docker if "usine.controle" in x][0]
    assert "--bot" in c and any(a.startswith("moonshot2:0x") for a in c) and "--network" not in c
    assert json.load(open(os.path.join(D.PUBLIC, "controle.json")))["verdict"] == "CONFORME"
    n = len([x for x in w.ctx.docker if "usine.controle" in x]); w.ctx.t += 600; D.cycle(w.ctx)
    assert len([x for x in w.ctx.docker if "usine.controle" in x]) == n                         # une fois par semaine

def test_sources_propres():
    for f in ("deployeur.py", "bornes.py"):
        src = open(os.path.join(HERE, f), encoding="utf-8").read()
        assert "\u2014" not in src

if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]; bad = 0
    for n, f in tests:
        try: f(); print(f"ok   {n}")
        except Exception as e:
            bad += 1; import traceback; print(f"ECHEC {n} : {e!r}"); traceback.print_exc()
    print(f"{len(tests) - bad}/{len(tests)} tests ok"); sys.exit(1 if bad else 0)
