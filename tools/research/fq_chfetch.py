#!/usr/bin/env python3
"""Fetch fanqie reader chapters, extract obfuscated content, decode with per-page font."""
import subprocess, re, sys, os
sys.path.insert(0, '/tmp')
from fq_decode import get_font_url, decode

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

def fetch(item_ids):
    for iid in item_ids:
        path = f'/tmp/fq_ch_{iid}.html'
        if not os.path.exists(path):
            subprocess.run(['curl','-s',f'https://fanqienovel.com/reader/{iid}','-H',f'User-Agent: {UA}','-o',path], check=False)
    return item_ids

def decode_pages(paths):
    cand = {c for c in set(open('/tmp/cand_chars.txt',encoding='utf-8').read()) if ord(c)>=0x2E80}
    cand |= set('的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间重生反派全家告诉我了谁还年份月日时分数元角块')
    mapping = {}
    for path in paths:
        raw = open(path, encoding='utf-8', errors='ignore').read()
        i = raw.find('"content":"')
        k = raw.find('","', i)
        # content is a JSON string; find true end: next unescaped " followed by ,"
        j = i+11
        while True:
            j = raw.find('"', j)
            if raw[j-1] != '\\':
                break
            j += 1
        c = raw[i+11:j]
        c = c.replace('\\u003C','<').replace('\\u003E','>').replace('\\u002F','/').replace('\\n','\n').replace('\\"','"')
        pua = sorted({ch for ch in c if 0xE000 <= ord(ch) <= 0xF8FF})
        fontp = '/tmp/fq_font_cur.woff2'
        url = get_font_url(path)
        if url and pua:
            subprocess.run(['curl','-s',url,'-o',fontp], check=True)
            mp = decode(pua, fontp, cand)
            mapping.update(mp)
        # extract title
        mt = re.search(r'"title":"([^"]+)"', raw)
        title = mt.group(1) if mt else '?'
        paras = re.findall(r'<p>(.*?)</p>', c, re.S)
        dec = lambda t: ''.join(mapping.get(ch,'□') if 0xE000<=ord(ch)<=0xF8FF else ch for ch in t)
        body = [dec(p).strip() for p in paras if p.strip()]
        unk = sum(b.count('□') for b in body)
        tot = sum(len(b) for b in body)
        print(f"### {title} | paras={len(body)} chars={tot} unknown={unk}")
        print('\n'.join(body))
        print()

if __name__ == '__main__':
    ids = sys.argv[1:]
    fetch(ids)
    decode_pages([f'/tmp/fq_ch_{i}.html' for i in ids])
