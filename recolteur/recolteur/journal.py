"""Journal chaine SHA-256 : chaque evenement porte l'empreinte du precedent.
    python3 -m recolteur.journal --verify"""
import os, sys, json, hashlib, datetime as dt
from . import config as C

class Journal:
    def __init__(self, path=None):
        self.path = path or os.path.join(C.DATA_DIR, "journal.jsonl")
        self.seq, self.prev = 0, "0" * 64
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 262144)); tail = f.read().decode("utf-8", "ignore").strip().splitlines()
            if tail: r = json.loads(tail[-1]); self.seq, self.prev = r["seq"], r["hash"]

    def record(self, kind, t_hl, **data):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        r = {"seq": self.seq + 1, "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z", "t_hl": t_hl,
             "type": kind, "data": json.loads(json.dumps(data, default=str)), "prev": self.prev}
        r["hash"] = hashlib.sha256((self.prev + json.dumps({k: v for k, v in r.items() if k != "hash"}, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())
        self.seq, self.prev = r["seq"], r["hash"]
        return r

def verify(path):
    if not os.path.exists(path): return True, 0, "journal vide"
    prev, n = "0" * 64, 0
    for line in open(path, encoding="utf-8"):
        r = json.loads(line); h = r.pop("hash")
        if r["prev"] != prev: return False, n, f"rupture de chaine a seq {r['seq']}"
        if hashlib.sha256((prev + json.dumps(r, sort_keys=True, ensure_ascii=False)).encode()).hexdigest() != h:
            return False, n, f"empreinte invalide a seq {r['seq']}"
        prev, n = h, n + 1
    return True, n, f"chaine intacte, derniere empreinte {prev[:16]}"

if __name__ == "__main__":
    ok, n, msg = verify(os.path.join(C.DATA_DIR, "journal.jsonl"))
    print(("OK " if ok else "ECHEC ") + f"{n} evenements, {msg}"); sys.exit(0 if ok else 1)
