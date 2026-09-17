#!/usr/bin/env python3
"""memorable_audit.py 口碑资产盘点(set-piece只管钉桩,本工具管兑付验收)
核验: 卷纲钉的名场面→正文是否兑现?兑付章是否有扩散反应?意象锚是否复现?
用法: python3 tools/memorable_audit.py <书根>
"""
import sys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    fails, warns = [], []
    # 1) 纲内名场面清单
    outline = ""
    for c in [book/"story/30-情节/卷一纲.md", book/"story/卷一纲.md", book/"story/30-情节/卷册表.md"]:
        if c.exists(): outline = c.read_text(encoding="utf-8"); break
    setpieces = re.findall(r"名场面[：:]\s*([^\n]+)", outline)
    print(f"═══ 口碑资产盘点({book.name}) ═══")
    print(f"  纲内名场面: {len(setpieces)}个")
    # 2) 意象锚兑付
    anchors = re.findall(r"意象锚[：:]\s*([^\n]+)", outline)
    body_all = "\n".join(f.read_text(encoding="utf-8") for f in sorted((book/"text").rglob("第*.md"))) if (book/"text").exists() else ""
    for anchor_line in anchors:
        items = re.split(r"[×、+/和]", anchor_line)
        for a in items:
            a = a.strip().strip("（）()")[:6]
            if len(a) >= 2 and a in body_all:
                print(f"  ✓ 意象锚「{a}」正文已现")
            elif len(a) >= 2:
                warns.append(f"意象锚「{a}」正文未现——钉了桩没浇混凝土")
    # 3) 金句落章验证
    for m in re.finditer(r"[「\u201c]([^」\u201d]{6,20})[」\u201d]", outline):
        q = m.group(1)
        if "真章" in q or "不换" in q or "奔头" in q:
            if q in body_all:
                print(f"  ✓ 金句「{q[:12]}…」已落正文")
            else:
                fails.append(f"卷纲金句「{q[:12]}…」正文0次——出圈武器没上膛")
    print(f"  FAIL {len(fails)} | WARN {len(warns)}")
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main())
