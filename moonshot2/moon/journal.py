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
