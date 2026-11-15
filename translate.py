import json, re, os, requests
from concurrent.futures import ThreadPoolExecutor

SESSION = requests.Session()

def clean_ro(text):
    subs = {'ă':'a','â':'a','î':'i','ș':'s','ş':'s','ț':'t','ţ':'t',
            'Ă':'A','Â':'A','Î':'I','Ș':'S','Ş':'S','Ț':'T','Ţ':'T'}
    for k, v in subs.items():
        text = text.replace(k, v)
    return text

def protect(v):
    tokens = []
    def repl(m):
        tokens.append(m.group(0))
        return f" XTOK{len(tokens)-1}X "
    p = re.sub(r'(\\n|\^[0-9]|~[0-9]|/|\*|%|\{[^}]+\}|\[[^\]]+\])', repl, v)
    return p, tokens

def restore(text, tokens):
    for i, tok in enumerate(tokens):
        text = re.sub(rf'\s*XTOK{i}X\s*', tok, text, flags=re.IGNORECASE)
    return clean_ro(text)

def fast_gt(text):
    r = SESSION.get(
        "https://googleapis.com",
        params={"client": "gtx", "sl": "auto", "tl": "ro", "dt": "t", "q": text},
        timeout=10
    )
    r.raise_for_status()
    return "".join(seg[0] for seg in r.json()[0] if seg[0])

def make_batches(items, max_chars=2500):
    batches, cur, cur_len = [], [], 0
    for k, v in items:
        p, toks = protect(v)
        if cur and cur_len + len(p) + 7 > max_chars:
            batches.append(cur)
            cur, cur_len = [], 0
        cur.append((k, v, p, toks))
        cur_len += len(p) + 7
    if cur:
        batches.append(cur)
    return batches

def translate_batch(batch):
    joined = "\n###\n".join(x[2] for x in batch)
    try:
        res = fast_gt(joined)
        parts = re.split(r'\s*###\s*', res)
        if len(parts) == len(batch):
            return [(batch[i][0], restore(parts[i], batch[i][3])) for i in range(len(batch))]
    except Exception:
        pass
    out = []
    for k, orig, p, toks in batch:
        try:
            out.append((k, restore(fast_gt(p), toks)))
        except Exception:
            out.append((k, orig))
    return out

files = ['strings.json'] + [f'chapter{i}/strings.json' for i in range(1, 6)]
for fpath in files:
    if not os.path.exists(fpath): continue
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    str_items = [(k, v) for k, v in data.items() if isinstance(v, str) and v.strip()]
    batches = make_batches(str_items)
    done = 0
    with ThreadPoolExecutor(max_workers=20) as ex:
        for res_batch in ex.map(translate_batch, batches):
            for k, new_v in res_batch:
                data[k] = new_v
            done += 1
            print(f"{fpath}: {done}/{len(batches)} batches", end="\r")
    print(f"{fpath}: {done}/{len(batches)} DONE!      ")
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
print("ALL DONE!")
