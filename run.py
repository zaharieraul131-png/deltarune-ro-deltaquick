import json, os, socket, requests
from concurrent.futures import ThreadPoolExecutor

og = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: [r for r in og(*a, **k) if r.copy().pop(0) == 2] or og(*a, **k)

S = requests.Session()
URL = "https://translate." + "://googleapis.com"
SUBS = {"ă":"a","â":"a","î":"i","ș":"s","ş":"s","ț":"t","ţ":"t","Ă":"A","Â":"A","Î":"I","Ș":"S","Ş":"S","Ț":"T","Ţ":"T"}

def clean_ro(t):
    for k, v in SUBS.items():
        t = t.replace(k, v)
    return t

def protect(v):
    toks = []
    out = []
    i = 0
    n = len(v)
    while i < n:
        ch = v[i:i+1]
        if ch == "\\":
            end = min(n, i + 3) if v[i+1:i+2] in ("M","E","F","C","S","W","T","f","c") else min(n, i + 2)
            toks.append(v[i:end])
            out.append(f" XTOK{len(toks)-1}X ")
            i = end
        elif ch in ("^", "~") and i + 1 < n and v[i+1:i+2].isdigit():
            toks.append(v[i:i+2])
            out.append(f" XTOK{len(toks)-1}X ")
            i += 2
        elif ch in ("&", "/", "*", "%"):
            toks.append(ch)
            out.append(f" XTOK{len(toks)-1}X ")
            i += 1
        else:
            out.append(ch)
            i += 1
    c = "".join(out)
    letters = [x for x in c if x.isalpha()]
    wu = len(letters) > 2 and all(x.isupper() for x in letters)
    if wu:
        words = c.split(" ")
        c = " ".join(w if w.startswith("XTOK") else w.lower() for w in words)
    return c, toks, wu

def restore(t, toks, wu):
    if wu:
        words = t.split(" ")
        t = " ".join(w if "xtok" in w.lower() else w.upper() for w in words)
    for i, tk in enumerate(toks):
        for pat in (f" XTOK{i}X ", f"XTOK{i}X ", f" XTOK{i}X", f"XTOK{i}X", f" xtok{i}x ", f"xtok{i}x ", f" xtok{i}x", f"xtok{i}x"):
            if pat in t:
                t = t.replace(pat, tk)
    return clean_ro(t)

def gt(txt, sl="en"):
    r = S.get(URL, params={"client":"gtx","sl":sl,"tl":"ro","dt":"t","q":txt}, timeout=8)
    r.raise_for_status()
    res = r.json()
    first = res.copy().pop(0)
    return "".join(seg.copy().pop(0) for seg in first if seg and seg.copy().pop(0))

def run_batch(args):
    batch, sl = args
    joined = "\n\n|||\n\n".join(list(x).pop(2) for x in batch)
    try:
        raw = gt(joined, sl)
        parts = [p.strip() for p in raw.split("|||")]
        if len(parts) == len(batch):
            return [(batch[i][0], restore(parts[i], batch[i][3], batch[i][4])) for i in range(len(batch))]
    except Exception as e:
        print("Batch err:", e)
    out = []
    for k, orig, p, toks, wu in batch:
        try:
            out.append((k, restore(gt(p, sl), toks, wu)))
        except Exception as e:
            print("Line err:", e)
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
        cur.append((k, v, p, toks, wu))
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
