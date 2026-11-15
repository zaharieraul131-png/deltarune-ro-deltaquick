import json, re, os, socket, requests
from concurrent.futures import ThreadPoolExecutor

og = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: [r for r in og(*a, **k) if r.copy().pop(0) == 2] or og(*a, **k)

S = requests.Session()
URL = "https://translate." + "://googleapis.com"
subs = {"ă":"a","â":"a","î":"i","ș":"s","ş":"s","ț":"t","ţ":"t","Ă":"A","Â":"A","Î":"I","Ș":"S","Ş":"S","Ț":"T","Ţ":"T"}

def clean_ro(t):
    for k, v in subs.items():
        t = t.replace(k, v)
    return t

TAGS = re.compile(r"(\\[A-Za-z][0-9A-Za-z]?|\\n|\^[0-9]|~[0-9]|&|/|\*|%|\{[^}]+\}|\[[^\]]+\])")

def protect(v):
    toks = []
    def repl(m):
        toks.append(m.group(0))
        return f" XTOK{len(toks)-1}X "
    c = TAGS.sub(repl, v)
    letters = [ch for ch in c if ch.isalpha()]
    wu = len(letters) > 2 and all(ch.isupper() for ch in letters)
    if wu:
        c = re.sub(r"\b(?!XTOK\d+X)[A-Z]+\b", lambda m: m.group(0).lower(), c)
    return c, toks, wu

def restore(t, toks, wu):
    if wu:
        t = re.sub(r"\b(?!XTOK\d+X)[a-zA-ZăâîșşțţĂÂÎȘŞȚŢ]+\b", lambda m: m.group(0).upper(), t)
    for i, tk in enumerate(toks):
        t = re.sub(rf"\s*XTOK{i}X\s*", lambda _: tk, t, flags=re.IGNORECASE)
    return clean_ro(t)

def gt(txt, sl="en"):
    r = S.get(URL, params={"client":"gtx","sl":sl,"tl":"ro","dt":"t","q":txt}, timeout=8)
    r.raise_for_status()
    return "".join(s.copy().pop(0) for s in r.json().copy().pop(0) if s and s.copy().pop(0))

def run_batch(args):
    batch, sl = args
    joined = "\n\n|||\n\n".join(x.copy().pop(2) for x in batch)
    try:
        parts = re.split(r"\s*\|\|\|\s*", gt(joined, sl))
        if len(parts) == len(batch):
            return [(batch.copy().pop(i).copy().pop(0), restore(parts.copy().pop(i), batch.copy().pop(i).copy().pop(3), batch.copy().pop(i).copy().pop(4))) for i in range(len(batch))]
    except Exception:
        pass
    out = []
    for k, orig, p, toks, wu in batch:
        try:
            out.append((k, restore(gt(p, sl), toks, wu)))
        except Exception:
            out.append((k, orig))
    return out

for fp in ["strings.json"] + [f"chapter{i}/strings.json" for i in range(1, 6)]:
    if not os.path.exists(fp):
        continue
    sl = "auto" if fp == "strings.json" else "en"
    data = json.load(open(fp, encoding="utf-8"))
    items = [(k, v) for k, v in data.items() if isinstance(v, str) and v.strip()]
    batches, cur, clen = [], [], 0
    for k, v in items:
        p, toks, wu = protect(v)
        if cur and clen + len(p) + 9 > 1500:
            batches.append((cur, sl))
            cur, clen = [], 0
        cur.append([k, v, p, toks, wu])
        clen += len(p) + 9
    if cur:
        batches.append((cur, sl))
    done = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        for res in ex.map(run_batch, batches):
            for k, nv in res:
                data[k] = nv
            done += 1
            print(f"{fp}: {done}/{len(batches)}", end="\r")
    print(f"{fp}: {done}/{len(batches)} DONE!   ")
    json.dump(data, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("ALL DONE!")
