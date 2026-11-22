"""Journal chaine SHA-256 : chaque decision porte l'empreinte de la precedente.
    python3 -m moon.journal --verify     python3 -m moon.journal --tail"""
import os, sys, json, hashlib, datetime as dt
from . import config as C

PATH = os.path.join(C.DATA_DIR, "journal.jsonl")

def _last():
    if not os.path.exists(PATH): return 0, "0" * 64
    with open(PATH, "rb") as f:
        f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 65536)); tail = f.read().decode("utf-8", "ignore").strip().splitlines()
    if not tail: return 0, "0" * 64
    r = json.loads(tail[-1]); return r["seq"], r["hash"]

def record(stage: str, decision: str, reason: str, **data) -> dict:
    os.makedirs(C.DATA_DIR, exist_ok=True)
    seq, prev = _last()
    r = {"seq": seq + 1, "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z",
         "bot": C.NAME, "mode": C.MODE, "stage": stage, "decision": decision, "reason": C.redact(str(reason))[:600],
         "data": json.loads(json.dumps(data, default=str)), "prev": prev}
    r["hash"] = hashlib.sha256((prev + json.dumps({k: v for k, v in r.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
    with open(PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
    return r

PARCOURS = os.path.join(C.DATA_DIR, "parcours.jsonl")
CODES = ("NO_SIGNAL", "STALE_DATA", "VOLUME_FILTER", "META_ABSENT", "SHORT_HISTORY", "STALE_SIGNAL", "IN_POSITION", "EXIT", "BLOCKED",
         "AI_VETO", "MIN_ORDER", "RISK_LIMIT", "LIQ_GUARD", "MARGIN", "INVALID", "ORDER_REJECTED", "NOT_FILLED", "EXECUTED", "POSITION_LIMIT")

def trace(code: str, coin: str, bar_ts, **data) -> dict:
    """Parcours des signaux : une ligne par actif suivi et par cloture, avec un code stable et les valeurs utilisees
    (EMA, ATR, volume, taille avant et apres arrondi, marge). Fichier simple, non chaine ; le journal garde les decisions."""
    assert code in CODES, code
    os.makedirs(C.DATA_DIR, exist_ok=True)
    r = {"ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "bot": C.NAME, "coin": coin, "bar_ts": bar_ts, "code": code,
         **json.loads(json.dumps(data, default=str))}
    with open(PARCOURS, "a", encoding="utf-8") as f: f.write(C.redact(json.dumps(r, ensure_ascii=False)) + "\n")
    return r

def bilan_parcours(path: str = PARCOURS, depuis: str = "") -> dict:
    """Comptes par code depuis une date (ISO) : « X signaux, Y exclusions, Z ordres, N executions »."""
    n = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try: r = json.loads(line)
            except ValueError: continue
            if r.get("ts", "") >= depuis: n[r["code"]] = n.get(r["code"], 0) + 1
    signaux = sum(v for k, v in n.items() if k not in ("NO_SIGNAL", "STALE_DATA", "VOLUME_FILTER", "META_ABSENT", "SHORT_HISTORY", "IN_POSITION"))
    ordres = sum(n.get(k, 0) for k in ("ORDER_REJECTED", "NOT_FILLED", "EXECUTED"))
    return {"codes": n, "signaux": signaux, "exclusions": signaux - ordres, "ordres": ordres, "executions": n.get("EXECUTED", 0)}

def verify(path: str = PATH):
    if not os.path.exists(path): return True, 0, "journal vide"
    prev, n = "0" * 64, 0
    for line in open(path, encoding="utf-8"):
        r = json.loads(line); h = r.pop("hash")
        if r["prev"] != prev: return False, n, f"rupture de chaîne à seq {r['seq']}"
        if hashlib.sha256((prev + json.dumps(r, sort_keys=True, ensure_ascii=False)).encode()).hexdigest() != h:
            return False, n, f"empreinte invalide à seq {r['seq']}"
        prev, n = h, n + 1
    return True, n, f"chaine intacte, derniere empreinte {prev[:16]}"

if __name__ == "__main__":
    if "--verify" in sys.argv:
        ok, n, msg = verify(); print(("✅ " if ok else "❌ ") + f"{n} decisions, {msg}"); sys.exit(0 if ok else 1)
    for line in (open(PATH, encoding="utf-8").readlines()[-25:] if os.path.exists(PATH) else []):
        r = json.loads(line); print(f"{r['seq']:>5} {r['ts'][:19]} {r['stage']:<10} {r['decision']:<8} {r['reason'][:120]}")
