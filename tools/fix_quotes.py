#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_quotes.py 引号三重修复器(法医ch001事故: 18对反向弯引号逃过旧版直引号修复)

修复项:
  1) 直引号 " 与全角＂ → 中文弯引号(按全文交替)
  2) 弯引号方向状态机: 每行内 “”必须交替; 不交替处按位置强扭
  3) 反向弯引号对(”...“)随状态机一并修正

安全策略:
  - 行内弯引号总数为奇数 → 跳过该行(可能跨行对话),人工核查
  - --dry 只报告不写

用法: python3 tools/fix_quotes.py <文件.md> [--dry]
"""
import sys
from pathlib import Path

OPEN, CLOSE = "\u201c", "\u201d"
STRAIGHTS = {'"', "\uff02"}

def fix_line(line):
    """返回(修复后行, 扭向数); 引号数为奇数时返回(None, 0)表示跳过"""
    marks = [i for i, c in enumerate(line) if c in (OPEN, CLOSE)]
    if len(marks) % 2 == 1:
        return None, 0
    buf = list(line)
    flipped = 0
    for pos, i in enumerate(marks):
        want = OPEN if pos % 2 == 0 else CLOSE
        if buf[i] != want:
            buf[i] = want
            flipped += 1
    return "".join(buf), flipped

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if not args:
        print(__doc__)
        return 2
    p = Path(args[0])
    t = p.read_text(encoding="utf-8")

    # 第一遍: 直引号/全角直引号 → 弯引号(全文交替)
    out, open_next, n_straight = [], True, 0
    for ch in t:
        if ch in STRAIGHTS:
            out.append(OPEN if open_next else CLOSE)
            open_next = not open_next
            n_straight += 1
        else:
            out.append(ch)
    t = "".join(out)

    # 第二遍: 逐行方向状态机
    lines, flipped, skipped = [], 0, 0
    for line in t.split("\n"):
        if OPEN in line or CLOSE in line:
            fixed, n = fix_line(line)
            if fixed is None:
                skipped += 1
                lines.append(line)
                continue
            flipped += n
            lines.append(fixed)
        else:
            lines.append(line)
    t2 = "\n".join(lines)

    n_o, n_c = t2.count(OPEN), t2.count(CLOSE)
    paired = "配对正常" if n_o == n_c else f"不配对({n_o}开{n_c}闭)需人工检查"
    if not dry:
        p.write_text(t2, encoding="utf-8")
    tag = "[dry] " if dry else ""
    print(f"{tag}直引号转换{n_straight} 弯引号扭向{flipped} 奇数跳过行{skipped} | {paired}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
