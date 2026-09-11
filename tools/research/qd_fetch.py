#!/usr/bin/env python3
"""Fetch Qidian mobile chapter pages and extract full text from SSR HTML."""
import re, sys, subprocess, html as H, time, json, os

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

def curl(url, out):
    subprocess.run(["curl", "-s", url, "-H", f"User-Agent: {UA}", "-o", out], check=False)
    return os.path.getsize(out) if os.path.exists(out) else 0

def extract_chapter(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    # main content block
    m = re.search(r'<main id="c-\d+"[^>]*>(.*?)</main>', raw, re.S)
    if not m:
        m = re.search(r'class="content[^"]*"[^>]*>(.*?)</main>', raw, re.S)
    if not m:
        return None
    body = m.group(1)
    paras = re.findall(r'<p>(.*?)</p>', body, re.S)
    out = []
    for p in paras:
        t = re.sub(r'<[^>]+>', '', p)
        t = H.unescape(t).strip()
        if t:
            out.append(t)
    return out

def chapter_title(path):
    raw = open(path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'<title>《[^》]+》(第[^_]+)_', raw)
    return m.group(1).strip() if m else '?'

if __name__ == '__main__':
    bid = sys.argv[1]
    cids = sys.argv[2:]
    for cid in cids:
        url = f"https://m.qidian.com/chapter/{bid}/{cid}/"
        out = f"/tmp/qd_{bid}_{cid}.html"
        sz = curl(url, out)
        time.sleep(1.2)
        paras = extract_chapter(out)
        if paras:
            title = chapter_title(out)
            n = sum(len(p) for p in paras)
            print(f"### {title} | paras={len(paras)} chars={n}")
            print('\n'.join(paras))
            print()
        else:
            print(f"### FAILED {cid} size={sz}")
