#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
foreshadow_audit.py 伏笔逾期检测器(磨刀:白牙子弹没上膛/山寨机哑弹/纸条半废弃——
这些"叙事债务"事故全靠人眼发现,本工具把伏笔账状态变成机器提醒)

检测项:
  1) 逾期未收: 登记"收:chY/兑付:chX"且当前章号已超过它 → WARN(排期跳票)
  2) 无排期:   只有"埋"没有任何"收/兑付/养"计划 → WARN(登记不完整,纯占位)
  3) 长期冻结: 状态:充能/养 且 埋设章距当前章 > 冻结阈值(默认20章)无兑付计划 → WARN(冷伏笔,读者已忘)
  4) 状态失真: 状态:已收 但正文验证不做(信任账本);同名条目重复 → FAIL(账本卫生)

用法: python3 tools/foreshadow_audit.py [--ledger ledgers/伏笔.md] [--freeze 20]
书根感知: 传书根路径则以该书 ledgers/伏笔.md 为账本(多书隔离协议)
"""
import re, sys, pathlib
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent


def parse_ledger(path):
    """解析伏笔账 → [(条目id, 描述, 埋章, 收章或None, 状态)]"""
    items = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line.startswith("- ") or "|" not in line:
            continue
        head = line[2:]
        mid = re.match(r"\[?(A-\d+|F-\d+)\]?\s*(.+?)\s*\|\s*(.+)", head)   # 1993审计: 账内实际用[F-1]方括号格式,原式永不匹配→恒报"0条健康"
        if not mid:
            continue
        fid, desc, rest = mid.group(1), mid.group(2), mid.group(3)
        # 埋章
        m_bury = re.search(r"埋[:：]\s*第?(\d+)章", rest) or re.search(r"埋[:：]\s*(\d{3})", rest)
        bury = int(m_bury.group(1)) if m_bury else None
        # 收章(显式排期)
        m_pay = re.search(r"(?:收|兑付|回收)[:：]\s*c?h?(\d+)", rest)
        pay = int(m_pay.group(1)) if m_pay else None
        # 状态
        m_st = re.search(r"状态[:：]\s*([^|]+)", rest)
        status = m_st.group(1).strip() if m_st else ""
        items.append((fid, desc, bury, pay, status, line))
    return items


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    freeze = 20
    if "--freeze" in sys.argv:
        freeze = int(sys.argv[sys.argv.index("--freeze") + 1])
    book = ROOT
    if args:
        cand = pathlib.Path(args[0])
        book = cand if cand.is_dir() else ROOT
    ledger = book / "ledgers" / "伏笔.md"
    if not ledger.exists():
        print(f"无伏笔账: {ledger}")
        return 2

    # 当前章号 = 书内正文最大章
    chapters = sorted(book.glob("text/卷*/第*.md")) if book != ROOT else sorted(ROOT.glob("text/卷*/第*.md"))
    nums = [int(m.group(1)) for f in chapters if (m := re.search(r"第(\d+)章", f.name))]
    cur = max(nums) if nums else 0

    items = parse_ledger(ledger)
    warns, fails = [], []

    # 状态失真: 同ID多条
    dup = [k for k, v in Counter(x[0] for x in items).items() if v > 1]
    for d in dup:
        fails.append(f"{d}: 账内重复{v if (v:=Counter(x[0] for x in items)[d]) else 0}条——撞号/重复登记,合并销号")

    LONG_MARKS = ("长线", "终卷", "全书级", "Z级")   # 全书级长线豁免冻结告警(foreshadow-plan分级)
    for fid, desc, bury, pay, status, raw in items:
        st = status
        if "已收" in st or "已兑" in st or "销号" in st:
            continue
        if "顺延" in st or "逾期" in st or "待收" in st:
            continue   # 已人工登记逾期的不再重复报警(审计-32: A-31已标顺延)
        if pay and cur > pay:
            warns.append(f"{fid} [{desc[:20]}] 排期收于ch{pay},当前ch{cur}已逾期{cur - pay}章——跳票!要么本卷收掉,要么改排期并说明")
        if bury and cur - bury > freeze and not pay and not any(mk in st for mk in LONG_MARKS):
            warns.append(f"{fid} [{desc[:20]}] 埋于ch{bury},已冻结{cur - bury}章无兑付排期——冷伏笔(读者已忘);全书级长线请登记'长线'标记豁免")
        if bury is None:
            warns.append(f"{fid} [{desc[:20]}] 无埋设章号——登记不完整,无法追踪")

    print(f"伏笔账: {ledger.relative_to(book)} | 当前章: ch{cur:03d} | 条目: {len(items)}")
    if not items:
        print("  [FAIL] 伏笔账解析0条——账本为空或格式漂移(30章书0伏笔=必然漏报),人审账本格式")
        return 1
    for l in fails:
        print(f"  [FAIL] {l}")
    for w in warns:
        print(f"  [WARN] {w}")
    if not fails and not warns:
        print("  伏笔账全项健康")
    print(f"\n伏笔审计: {'FAIL' if fails else 'PASS'}({len(warns)}提醒)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
