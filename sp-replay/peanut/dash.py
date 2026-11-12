"""Tableau de bord de Smart Peanut — LECTURE SEULE des fichiers du bot (aucune clé, aucun accès à l'exchange, aucun bouton d'ordre).
Écoute dans le conteneur sur 8089 ; publié UNIQUEMENT sur 127.0.0.1 du VPS → s'ouvre depuis le Mac via un tunnel SSH :
    ssh -N -L 8089:127.0.0.1:8089 root@srv1454597.hstgr.cloud      puis      http://localhost:8089"""
import os, json, time
from collections import defaultdict
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from . import config as C, journal as J

D = C.DATA_DIR
def _j(name, default):
    try: return json.load(open(os.path.join(D, name)))
    except Exception: return default

def _tail(name, n):
    p = os.path.join(D, name)
    if not os.path.exists(p): return []
    with open(p, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400_000)); lines = f.read().decode("utf-8", "ignore").splitlines()
        if size > 400_000: lines = lines[1:]                     # première ligne possiblement coupée
    out = []
    for l in lines[-n:]:
        try: out.append(json.loads(l))
        except Exception: pass
    return out

def api() -> dict:
    st, s = _j("status.json", {}), _j("state.json", {})
    closed = [c for c in s.get("closed", []) if c.get("issue") != "annulé (non rempli)"]
    by = defaultdict(lambda: {"n": 0, "win": 0, "pnl": 0.0, "g": 0.0, "p": 0.0})
    for c in closed:
        for k in (c.get("strat", "?"), "TOTAL"):
            b = by[k]; x = float(c.get("pnl") or 0); b["n"] += 1; b["win"] += x > 0; b["pnl"] += x
            b["g" if x > 0 else "p"] += abs(x)
    stats = {k: {**v, "pf": (round(v["g"] / v["p"], 2) if v["p"] else None), "pnl": round(v["pnl"], 4)} for k, v in by.items()}
    eq = _tail("equity.jsonl", 4000)
    jr = [{"seq": r["seq"], "ts": r["ts"], "stage": r["stage"], "decision": r["decision"], "reason": r["reason"]} for r in _tail("journal.jsonl", 80)]
    ok, n, msg = J.verify()
    return {"now": int(time.time()), "status": st, "open": s.get("open", {}), "closed": s.get("closed", [])[-60:][::-1], "stats": stats,
            "equity": eq, "journal": jr[::-1], "chain": {"ok": ok, "n": n, "msg": msg}, "agent_usage": _j("agent_usage.json", {}),
            "agent_max": C.AGENT_MAX_CALLS_DAY, "paper_start": C.PAPER_START_USDC}

PAGE = r"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Peanut</title><style>
:root{--bg:#f6f5f1;--card:#fff;--ink:#1d1c1a;--mut:#6f6b63;--line:#e6e2d9;--up:#1f8a4c;--dn:#c2372b;--acc:#b8741a;--chip:#f1ece2}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1c19;--ink:#efece6;--mut:#9b968c;--line:#2e2c27;--up:#4cc27c;--dn:#ef6b5e;--acc:#e3a24a;--chip:#2a2823}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
.w{max-width:1280px;margin:0 auto;padding:20px 16px 40px}h1{font-size:20px;margin:0}h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:0 0 10px;font-weight:600}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}.pill{border-radius:99px;padding:4px 12px;font-weight:600;font-size:12px;background:var(--chip)}
.live{background:var(--dn);color:#fff}.paper{background:var(--acc);color:#fff}.kill{background:#000;color:#fff}
.g{display:grid;gap:14px}.g4{grid-template-columns:repeat(4,1fr)}.g2{grid-template-columns:2fr 1fr}@media(max-width:900px){.g4{grid-template-columns:repeat(2,1fr)}.g2{grid-template-columns:1fr}}
.c{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}.big{font-size:30px;font-weight:700;font-variant-numeric:tabular-nums}
.sub{color:var(--mut);font-size:12px}.up{color:var(--up)}.dn{color:var(--dn)}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
th{text-align:left;color:var(--mut);font-weight:500;font-size:12px;border-bottom:1px solid var(--line);padding:6px 6px}td{padding:6px;border-bottom:1px solid var(--line);vertical-align:top}
.tw{overflow-x:auto}.mono{font-family:ui-monospace,Menlo,monospace;font-size:12px}.chips span{display:inline-block;background:var(--chip);border-radius:6px;padding:2px 8px;margin:2px;font-size:12px}
.j td:nth-child(4){max-width:640px}.tag{font-size:11px;font-weight:700;padding:1px 6px;border-radius:4px;background:var(--chip)}svg{width:100%;height:180px;display:block}
.alert{background:var(--dn);color:#fff;border-radius:10px;padding:10px 14px;margin-bottom:14px;font-weight:600}
</style></head><body><div class="w">
<div class="top"><div><h1>Smart Peanut <span id="ver" class="sub"></span></h1><div class="sub" id="acct"></div></div><div id="mode"></div></div>
<div id="alert"></div>
<div class="g g4">
 <div class="c"><h2>Equity</h2><div class="big" id="eq">–</div><div class="sub" id="eqd"></div></div>
 <div class="c"><h2>Aujourd'hui (UTC)</h2><div class="big" id="day">–</div><div class="sub" id="dayd"></div></div>
 <div class="c"><h2>Trades clôturés</h2><div class="big" id="nt">–</div><div class="sub" id="ntd"></div></div>
 <div class="c"><h2>Conseil Grok</h2><div class="big" id="ag">–</div><div class="sub" id="agd"></div></div>
</div>
<div class="g g2" style="margin-top:14px">
 <div class="c"><h2>Courbe d'equity</h2><svg id="ch" viewBox="0 0 800 180" preserveAspectRatio="none"></svg><div class="sub" id="chd"></div></div>
 <div class="c"><h2>Univers surveillé (volatilité)</h2><div class="chips" id="uni"></div><h2 style="margin-top:14px">Bornes dures</h2><div class="sub" id="lim"></div><h2 style="margin-top:14px">Dernière note</h2><div id="note" class="sub"></div></div>
</div>
<div class="c" style="margin-top:14px"><h2>Positions et ordres</h2><div class="tw"><table id="pos"></table></div><div class="sub" id="exch"></div></div>
<div class="c" style="margin-top:14px"><h2>Par stratégie</h2><div class="tw"><table id="st"></table></div></div>
<div class="c" style="margin-top:14px"><h2>Historique des trades</h2><div class="tw"><table id="hist"></table></div></div>
<div class="c j" style="margin-top:14px"><h2>Journal des décisions <span class="sub" id="chain"></span></h2><div class="tw"><table id="jr"></table></div></div>
<div class="sub" style="margin-top:12px" id="upd"></div>
</div><script>
const f=(x,d=2)=>x==null||isNaN(x)?"–":(+x).toFixed(d),sg=x=>x>0?"up":x<0?"dn":"",pm=x=>(x>0?"+":"")+f(x,2);
const t=s=>s?String(s).replace("T"," ").slice(5,16):"–",esc=s=>String(s??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
function chart(pts){const el=document.getElementById("ch");if(pts.length<2){el.innerHTML="";return}
 const xs=pts.map(p=>p.t),ys=pts.map(p=>p.eq),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),pad=(y1-y0)*.1||0.5;
 const X=x=>(x-x0)/(x1-x0||1)*800,Y=y=>170-(y-(y0-pad))/((y1+pad)-(y0-pad))*160;
 const d=pts.map((p,i)=>(i?"L":"M")+X(p.t).toFixed(1)+" "+Y(p.eq).toFixed(1)).join(" ");const up=ys[ys.length-1]>=ys[0];
 el.innerHTML=`<path d="${d} L800 180 L0 180Z" fill="${up?'var(--up)':'var(--dn)'}" opacity=".08"/><path d="${d}" fill="none" stroke="${up?'var(--up)':'var(--dn)'}" stroke-width="2" vector-effect="non-scaling-stroke"/>`;
 document.getElementById("chd").textContent=`min ${f(y0)} · max ${f(y1)} USDC · ${new Date(x0*1000).toLocaleString()} → ${new Date(x1*1000).toLocaleString()}`}
async function go(){let d;try{d=await (await fetch("api",{cache:"no-store"})).json()}catch(e){document.getElementById("upd").textContent="⚠ tableau injoignable";return}
 const s=d.status||{},eq=s.equity_usdc,start=s.paper?d.paper_start:(d.equity[0]||{}).eq;
 document.getElementById("ver").textContent="v"+(s.version||"?");document.getElementById("acct").textContent="compte "+(s.account||"?")+" · Hyperliquid perps";
 document.getElementById("mode").innerHTML=(s.kill?'<span class="pill kill">KILL</span> ':'')+(s.paper?'<span class="pill paper">PAPIER</span>':'<span class="pill live">● RÉEL</span>');
 document.getElementById("alert").innerHTML=s.kill?`<div class="alert">ARRÊT D'URGENCE actif — aucune nouvelle entrée. ${esc(s.kill_reason)}</div>`:(s.dead?'<div class="alert">Poche arrêtée définitivement (plancher touché)</div>':'');
 document.getElementById("eq").textContent=f(eq)+" $";const tot=eq-start;document.getElementById("eqd").innerHTML=`<span class="${sg(tot)}">${pm(tot)} USDC (${f(start?tot/start*100:0,1)} %)</span> depuis le départ (${f(start)})`;
 const dd=eq-(s.day_start||eq);document.getElementById("day").innerHTML=`<span class="${sg(dd)}">${pm(dd)}</span>`;document.getElementById("dayd").textContent=`début du jour ${f(s.day_start)} · pause à −${f((s.limits||{}).perte_jour*100,0)} %`;
 const T=d.stats.TOTAL||{n:0,win:0,pnl:0,pf:null};document.getElementById("nt").textContent=T.n;document.getElementById("ntd").innerHTML=`${T.win} gagnants (${f(T.n?T.win/T.n*100:0,0)} %) · PF ${T.pf??"–"} · <span class="${sg(T.pnl)}">${pm(T.pnl)} $</span>`;
 const u=d.agent_usage||{};document.getElementById("ag").textContent=(u.calls||0)+" / "+d.agent_max;document.getElementById("agd").textContent="appels aujourd'hui (budget quotidien)";
 chart(d.equity);document.getElementById("uni").innerHTML=(s.universe||[]).map(c=>`<span>${esc(c)}</span>`).join("");
 const L=s.limits||{};document.getElementById("lim").textContent=`levier ≤ ${L.levier_max} · risque ≤ ${f((L.risque_trade||0)*100,0)} %/trade · ${L.positions_max} positions · plancher ${L.plancher} $ · durée max ${L.duree_max_min} min`;
 document.getElementById("note").textContent=s.note||"–";
 const ex=Object.fromEntries((s.positions_exchange||[]).filter(p=>p.coin).map(p=>[p.coin,p]));
 const rows=Object.entries(d.open).map(([c,p])=>{const e=ex[c]||{};const st=p.filled?"en position":"ordre maker en attente";
  return `<tr><td><b>${esc(c)}</b></td><td class="${p.side=='long'?'up':'dn'}">${p.side}</td><td>${esc(p.strat)}</td><td>${st}</td><td>${f(p.entry,6)}</td><td class="dn">${f(p.stop,6)}</td><td class="up">${f(p.tp,6)}</td><td>${f(p.sz,4)}</td><td>${p.lev}x</td><td>${f(p.notional)}</td><td>${f(p.risk_usd)}</td><td>${e.liq?f(e.liq,6):"–"}</td><td class="${sg(e.upnl??p.upnl)}">${pm(e.upnl??p.upnl??0)}</td><td>${t(new Date(p.placed_ms).toISOString())}</td><td class="sub">${esc((p.agent||{}).confidence)} · ${esc((p.agent||{}).reason)}</td></tr>`}).join("");
 document.getElementById("pos").innerHTML=`<tr><th>Actif</th><th>Sens</th><th>Stratégie</th><th>État</th><th>Entrée</th><th>Stop</th><th>Cible</th><th>Taille</th><th>Levier</th><th>Notionnel $</th><th>Risque $</th><th>Liquidation</th><th>P&L latent</th><th>Placé</th><th>Avis du conseil</th></tr>`+(rows||'<tr><td colspan="15" class="sub">aucune position</td></tr>');
 const orphan=(s.positions_exchange||[]).filter(p=>p.erreur||(p.coin&&!d.open[p.coin]));document.getElementById("exch").innerHTML=orphan.length?'<span class="dn">⚠ vu sur l\'exchange mais non suivi : '+esc(JSON.stringify(orphan))+'</span>':(s.paper?"":"positions confirmées par Hyperliquid");
 document.getElementById("st").innerHTML=`<tr><th>Stratégie</th><th>Trades</th><th>Gagnants</th><th>Taux</th><th>P&L $</th><th>Profit factor</th></tr>`+Object.entries(d.stats).sort((a,b)=>(a[0]=="TOTAL")-(b[0]=="TOTAL")).map(([k,v])=>`<tr><td>${k=="TOTAL"?"<b>TOTAL</b>":esc(k)}</td><td>${v.n}</td><td>${v.win}</td><td>${f(v.n?v.win/v.n*100:0,0)} %</td><td class="${sg(v.pnl)}">${pm(v.pnl)}</td><td>${v.pf??"–"}</td></tr>`).join("")+(T.n<30?'<tr><td colspan="6" class="sub">moins de 30 trades : aucune conclusion statistique possible</td></tr>':'');
 document.getElementById("hist").innerHTML=`<tr><th>Clôture</th><th>Actif</th><th>Sens</th><th>Stratégie</th><th>Issue</th><th>Entrée</th><th>Sortie</th><th>Taille</th><th>P&L $</th></tr>`+(d.closed.map(c=>`<tr><td>${t(c.ts)}</td><td><b>${esc(c.coin)}</b></td><td>${c.side}</td><td>${esc(c.strat)}</td><td>${esc(c.issue)}</td><td>${f(c.entry,6)}</td><td>${f(c.exit,6)}</td><td>${f(c.sz,4)}</td><td class="${sg(c.pnl)}">${pm(c.pnl)}</td></tr>`).join("")||'<tr><td colspan="9" class="sub">aucun trade clôturé</td></tr>');
 document.getElementById("chain").textContent=(d.chain.ok?"✓ ":"✗ ")+d.chain.n+" décisions · "+d.chain.msg;
 document.getElementById("jr").innerHTML=`<tr><th>#</th><th>Heure UTC</th><th>Étape</th><th>Décision</th></tr>`+d.journal.map(r=>`<tr><td class="mono">${r.seq}</td><td class="mono">${t(r.ts)}</td><td>${esc(r.stage)}</td><td><span class="tag">${esc(r.decision)}</span> ${esc(r.reason)}</td></tr>`).join("");
 document.getElementById("upd").textContent="mis à jour "+new Date().toLocaleTimeString()+" · dernier passage du bot "+t(s.ts)+" UTC · rafraîchi toutes les 15 s · lecture seule"}
go();setInterval(go,15000);
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?")[0] in ("/api", "/api/"):
            body, ct = json.dumps(api(), default=str).encode(), "application/json"
        elif self.path.split("?")[0] in ("/", "/index.html"):
            body, ct = PAGE.encode(), "text/html; charset=utf-8"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Type", ct); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("DASH_PORT", "8089"))), H).serve_forever()
