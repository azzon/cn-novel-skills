#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
exemplar_flywheel.py 范例段飞轮(提上限的核心机制: 模型从自己最好的文字里学)

原理: 冷读报告会引原文圈出"最强段落/白金手感段"——这些是本书自己的高光文字。
本工具把它们收割进 <书根>/风格包范例段库.md(按四型轮换: 对话/动作/情感/收尾,每型保3段),
bundle 生成下一章时注入2段匹配型——上限随写作推进自我抬升。

用法: python3 tools/exemplar_flywheel.py harvest [书根]   # 从audit/冷读-*.md收割
      python3 tools/exemplar_flywheel.py show [书根]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TYPES = {"对话": r"对话|对白|台词", "动作": r"动作|画面|白描", "情感": r"情感|心动|心头|暖|哭", "收尾": r"收尾|结尾|章末|钩"}


def classify(q):
    if re.search(r"[饭菜品摊烟钱票布碗盆摊秤]|块|毛|角", q) and not re.search(r"“", q[:5]):
        return "生活"
    if re.search(r"“", q):
        return "对话"
    if re.search(r"收|末|钩", q[:6]):
        return "收尾"
    return "情感" if re.search(r"[心头疼暖哭酸紧]", q) else "动作"


def harvest(book):
    audit = book / "audit"
    lib = book / "风格包范例段库.md"
    if not audit.is_dir():
        print(f"无audit目录: {audit}")
        return 2
    entries = []   # (章,型,段)
    for f in sorted(audit.glob("冷读-第*章.md")):
        m = re.match(r"冷读-第(\d+)章", f.name)
        ch = m.group(1) if m else "?"
        text = f.read_text(encoding="utf-8")
        # 冷读骨架的"最强段落摘录"栏(磨刀十八批新增)+行内引文「」/“”圈的高光句
        for line in text.splitlines():
            if re.match(r"-\s*(最强段落摘录|生活气摘录)", line.strip()):   # 双收割源;取最后一个"）： "或": "之后(栏说明含冒号)
                seg = re.split(r"[:：]\s*", line.strip(), maxsplit=1)[-1] if ": " in line or "：" in line else ""
                seg = re.split(r"\)\s*[:：]\s*", line.strip())[-1]   # 优先"）: "分界
                if seg and "（填）" not in seg:
                    entries.append((ch, classify(seg), seg.strip()))
        for q in re.findall(r"[「“]([^」”]{12,120})[」”]", text):
            if any(k in text[max(0, text.find(q) - 40):text.find(q)] for k in ("最强", "白金", "手感", "最好")):
                entries.append((ch, classify(q), q))
    if not entries:
        print("冷读报告未含最强段落摘录(新版冷读骨架字段)——无收割物")
        return 0
    # 库结构: 每型保最新3段,去重
    from collections import defaultdict
    byt = defaultdict(list)
    if lib.exists():
        cur_type = None
        for line in lib.read_text(encoding="utf-8").splitlines():
            m = re.match(r"## (\w+)型", line)
            if m:
                cur_type = m.group(1)
            elif line.startswith("- 第") and cur_type:
                byt[cur_type].append(line)
    seen = {re.sub(r"\W", "", l[-40:]) for v in byt.values() for l in v}
    added = 0
    for ch, tp, seg in entries:
        key = re.sub(r"\W", "", seg[-40:])
        if key in seen:
            continue
        byt[tp].append(f"- 第{ch}章 | {seg}")
        seen.add(key)
        added += 1
    out = ["# 风格包范例段库(冷读高光收割·飞轮)", "> tools/exemplar_flywheel.py 自动维护;每型保最新3段;bundle按场景型注入2段", ""]
    for tp in ("对话", "动作", "情感", "收尾", "生活"):
        out.append(f"## {tp}型")
        out.extend(byt.get(tp, [])[-3:])
        out.append("")
    lib.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"收割{added}段 → {lib.name}(现库{sum(len(v) for v in byt.values())}段)")
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = args[0] if args else "harvest"
    book = ROOT / args[1] if len(args) > 1 else ROOT
    if mode == "show":
        f = book / "风格包范例段库.md"
        print(f.read_text(encoding="utf-8") if f.exists() else "库不存在")
        return 0
    return harvest(book)


if __name__ == "__main__":
    sys.exit(main())
