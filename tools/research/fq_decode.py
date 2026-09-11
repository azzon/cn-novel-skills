#!/usr/bin/env python3
"""Fanqie font obfuscation decoder: render PUA glyphs from the obfuscation woff2
and match against reference CJK font renderings by bitmap IoU."""
import subprocess, re, sys, io, os, json
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

REF = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
SZ = 64

def get_font_url(html_path):
    raw = open(html_path, encoding='utf-8', errors='ignore').read()
    m = re.search(r'src:url\((https://[^)]+?\.woff2)\)', raw)
    return m.group(1) if m else None

def load_obf_font(url, cache='/tmp/fq_font.woff2'):
    subprocess.run(['curl','-s',url,'-o',cache], check=True)
    return TTFont(cache)

def render(font, ch, size=SZ):
    try:
        img = Image.new('L', (size, size), 0)
        d = ImageDraw.Draw(img)
        d.text((8, 8), ch, font=font, fill=255)
        return img
    except Exception:
        return None

def bmp_hash(img, thresh=100):
    px = img.load()
    w, h = img.size
    bits = 0
    for y in range(h):
        for x in range(w):
            bits = (bits << 1 | (1 if px[x, y] > thresh else 0))
    return bits

def norm_crop(img, thresh=60):
    bbox = img.point(lambda p: 255 if p > thresh else 0).getbbox()
    if not bbox:
        return None
    return img.crop(bbox).resize((48, 48))

def sim(a, b):
    pa, pb = a.load(), b.load()
    inter = uni = 0
    for y in range(48):
        for x in range(48):
            va, vb = pa[x, y] > 96, pb[x, y] > 96
            if va and vb: inter += 1
            if va or vb: uni += 1
    return inter / uni if uni else 0

def decode(pua_chars, obf_font_path, candidates):
    obf = ImageFont.truetype(obf_font_path, 44)
    ref = ImageFont.truetype(REF, 44)
    mapping = {}
    # pre-render references
    ref_imgs = {}
    for ch in candidates:
        im = norm_crop(render(ref, ch))
        if im: ref_imgs[ch] = im
    for ch in pua_chars:
        im = norm_crop(render(obf, ch))
        if im is None: continue
        scored = sorted(((sim(im, rim), rch) for rch, rim in ref_imgs.items()), reverse=True)
        if scored and scored[0][0] > 0.75:
            mapping[ch] = scored[0][1]
        elif scored and scored[0][0] > 0.55 and scored[0][0] - scored[1][0] > 0.08:
            mapping[ch] = scored[0][1]  # weaker but distinctive match
    return mapping

if __name__ == '__main__':
    html_path = sys.argv[1]
    url = get_font_url(html_path)
    print('font url:', url, file=sys.stderr)
    if url:
        subprocess.run(['curl','-s',url,'-o','/tmp/fq_font.woff2'], check=True)
    # candidates: chars from a common charset + digits/punct
    cand = set(open('/tmp/cand_chars.txt', encoding='utf-8').read()) if os.path.exists('/tmp/cand_chars.txt') else set()
    cand = {c for c in cand if ord(c) >= 0x2E80}  # CJK + fullwidth punct only, no ASCII
    cand |= set('的一是了我不人在他有这上们来到时大地为子中你说生国年着就那和要她出也得里后自以会家可下而过天去能对小多然于心学么之都好看起发当没成只如事把还用第样道想作种开美总从无情己面最女但现前些所同日手又行意动方期它头经长儿回位分爱老因很给名法间')
    cand |= set('《》！？。，、；：「」『』（）《》……—·“”‘’0123456789')
    raw = open(html_path, encoding='utf-8', errors='ignore').read()
    pua = sorted({ch for ch in raw if 0xE000 <= ord(ch) <= 0xF8FF})
    print('PUA to decode:', len(pua), file=sys.stderr)
    mp = decode(pua, '/tmp/fq_font.woff2', cand)
    print(json.dumps({hex(ord(k)): v for k, v in mp.items()}, ensure_ascii=False, indent=0))
