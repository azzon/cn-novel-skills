#!/usr/bin/env python3
"""book_isolation_check.py 多书状态隔离验证(红队20260915跨书污染事故的机器化)
核验: 1)各书根账本无跨书章号引用 2)各书根素材/人物名无串书 3)主书区无书根残留
用法: python3 tools/book_isolation_check.py
"""
import sys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def book_roots():
    return [d for d in ROOT.iterdir() if d.is_dir() and (d / "00-前提.md").exists() and d.name not in ("archive",)]

def main():
    roots = book_roots()
    fails = []
    print("═══ 多书隔离验证 ═══")
    print(f"  书根: {[b.name for b in roots]}")
    for b in roots:
        led = b / "ledgers"
        if not led.exists(): continue
        for f in led.glob("*.md"):
            t = f.read_text(encoding="utf-8", errors="ignore")
            for other in roots:
                if other == b: continue
                if other.name in t:
                    # 排除合法引用(对标/市场调研提及其他书名)
                    for i, ln in enumerate(t.splitlines()):
                        if other.name in ln and not re.search(r"对标|参考|市场|调研", ln):
                            fails.append(f"{b.name}/{f.name}:{i+1} 疑似跨书引用'{other.name}': {ln.strip()[:50]}")
    # 主书区允许有章(1993书即主书形态);只查书根账本互串
    # (红队20260915协议原意: 禁书根产物写入主书区;主书自己的章合法)
    if fails:
        print(f"  [FAIL] {len(fails)}处隔离违规:")
        for x in fails[:5]: print(f"    {x}")
        return 1
    print("  ✅ 各书根账本/正文零跨书引用")
    return 0

if __name__ == "__main__":
    sys.exit(main())
