#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anticipation_audit.py 期待链空窗检测器(磨刀: ch42-45连续4章无新挂悬念靠人眼发现——钩力衰减机器化)

原理: 解析 ledgers/钩分布.md 的章末钩形态(短句重音/对话切/悬置/叙述收),按三规则报警:
  1) 平淡收连击: 连续>=2章"叙述收" → WARN(章末钩力衰减,追读掉队点)
  2) 窗口占比:   最近N章(默认10)内叙述收>40% → WARN(节奏平坡)
  3) 账缺章:     章号断档 → WARN(钩账不完整,没法审计)

书根感知: python3 tools/anticipation_audit.py [书根]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
FLAT = "叙述收"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    ledger = book / "ledgers" / "钩分布.md"
    if not ledger.exists():
        print(f"无钩分布账: {ledger}")
        return 2

    entries = []   # (章号, 形态, 原行)
    for line in ledger.read_text(encoding="utf-8-sig").splitlines():
        m = re.match(r"-\s*第(\d+)章\s*\[([^\]]+)\]", line.strip())
        if m:
            entries.append((int(m.group(1)), m.group(2).strip(), line.strip()))

    if not entries:
        print("钩账无记录")
        return 2
    entries.sort()
    warns = []

    # 3) 账缺章
    nums = [e[0] for e in entries]
    gaps = [n for n in range(nums[0], nums[-1] + 1) if n not in nums]
    if gaps:
        warns.append(f"钩账缺章: {gaps}——先补账再审计(缺章=盲区)")

    # 1) 平淡收连击
    run = []
    for n, shape, raw in entries:
        if FLAT in shape:
            run.append(n)
        else:
            if len(run) >= 2:
                warns.append(f"平淡收连击: 第{run[0]}-{run[-1]}章连续{len(run)}章叙述收——章末钩力衰减,下一章末必须挂事件钩")
            run = []
    if len(run) >= 2:
        warns.append(f"平淡收连击: 第{run[0]}-{run[-1]}章连续{len(run)}章叙述收(至最新章)——同上")

    # 2) 窗口占比
    win = entries[-10:]
    flat_n = sum(1 for e in win if FLAT in e[1])
    pct = flat_n / len(win) * 100
    if pct > 40:
        warns.append(f"近{len(win)}章叙述收形式占比{pct:.0f}%(>40%)——若其中多为强钩(悬念/危机性质)可登记waivers豁免;连击段优先补事件钩")

    # 回调资源审计(磨刀二十一批: 回调四式有研究无机器——梗闲置/爽点无回调计划双查)
    geng = book / "ledgers" / "梗.md"
    if geng.exists():
        cur_n = entries[-1][0] if entries else 0
        for line in geng.read_text(encoding="utf-8").splitlines():
            m = re.match(r"-\s*(.+?)\s*\|.*用[:：]\s*第?(\d+)(?:章[^|]*)?\s*\|\s*状态[:：]\s*(.+)", line.strip())
            if not m:
                continue
            last, st = int(m.group(2)), m.group(3)
            if "可续" in st and cur_n - last > 8:
                warns.append(f"回调资源闲置: 「{m.group(1)[:14]}」末用于第{last}章,已{cur_n-last}章未回收(>8)——回调四式挑一式兑付或改'完结'")
    pipe = book / "ledgers" / "爽点管道.md"
    if pipe.exists():
        _rows = [l for l in pipe.read_text(encoding="utf-8").splitlines() if l.startswith("| P") and "已兑" in l]
        _nopl = [l.split("|")[1].strip() for l in _rows if ("利息" not in l or l.count("|") < 8 or not l.split("|")[6].strip())]
        if _nopl:
            warns.append(f"已兑爽点缺回调/利息计划: {', '.join(_nopl[:4])}——爽点是资产不是事件,大爽当场登记回调计划(cool-point六)")

        # 红队20260919上限批: 期待链四闭环检测(此前红线全靠10章一次人工drift-audit)
        _rows_all = []
        for l in pipe.read_text(encoding="utf-8").splitlines():
            if not l.startswith("| P"):
                continue
            c = [x.strip() for x in l.split("|")]
            # c[1]=P号 c[2]=类型 c[3]=原料 c[4]=蓄压自章 c[5]=计划兑现章 c[6]=利息 c[7]=状态
            if len(c) >= 8:
                _rows_all.append(c)
        _cur = entries[-1][0] if entries else 0
        _seen = set()

        def _num(s):
            m = re.search(r"(\d+)", s or "")
            return int(m.group(1)) if m else None

        def _warn_once(key, msg):
            if key not in _seen:
                _seen.add(key)
                warns.append(msg)

        # a) 链冻结/跳票(充能中30章没提,以前只能靠人眼)
        for c in _rows_all:
            st = c[7]
            charge, plan = _num(c[4]), _num(c[5])
            if ("充能" in st or "蓄" in st) and charge and _cur - charge > 20:
                _warn_once(f"freeze{c[1]}", f"链冻结: {c[1]}「{c[3][:10]}」自第{charge}章蓄压已{_cur-charge}章未兑现(>20)——近3章内拉一拍,否则降级入库")
            if plan and "已兑" not in st and _cur > plan:
                _warn_once(f"late{c[1]}", f"链跳票: {c[1]}计划第{plan}章兑现,已到第{_cur}章——补兑或改期登记(禁无声跳票)")

        # b) 兑现空窗(连续>5章零兑现=弃书红线,drift-audit:72的机器化)
        _paid = sorted(p for p in (_num(c[5]) for c in _rows_all if "已兑" in c[7]) if p and p <= _cur)
        if _paid and _cur - _paid[-1] > 5:
            _warn_once("gap", f"兑现空窗: 末次兑现在第{_paid[-1]}章,已连{_cur-_paid[-1]}章零兑现(>5=弃书红线)——本章必须安排一次小兑现(哪怕微爽)")

        # c) 装逼七型同型连击(连续2章同型=黄牌,cool-point:10的机器化)
        _by_ch = {}
        for c in _rows_all:
            if "已兑" in c[7] and _num(c[5]):
                _by_ch.setdefault(_num(c[5]), []).append(c[2])
        _seq = sorted(_by_ch.items())
        for i in range(1, len(_seq)):
            if _seq[i][1] and _seq[i-1][1] and _seq[i][1][0] == _seq[i-1][1][0]:
                _warn_once(f"same{_seq[i][0]}{_seq[i][1][0]}",
                           f"装逼同型连击: 第{_seq[i-1][0]}-{_seq[i][0]}章连续'{_seq[i][1][0]}'——七型轮换黄牌,换型或登记waivers")
        # d) 同章双爆发(两链同章兑=互稀释)
        for ch, types in _seq:
            if len(types) >= 2:
                _warn_once(f"double{ch}", f"同章双爆发: 第{ch}章兑{len(types)}条链({','.join(t[:6] for t in types)})——双响互稀释,拆章或降级其一为辅拍")

    # 报表
    from collections import Counter
    dist = Counter(e[1] for e in entries)
    print(f"钩账: {len(entries)}章 ({entries[0][0]}-{entries[-1][0]})")
    for k, v in dist.most_common():
        print(f"  {k}: {v}章 ({v/len(entries)*100:.0f}%)")
    for w in warns:
        print(f"  [WARN] {w}")
    if not warns:
        print("  期待链健康")
    print(f"\n期待链审计: PASS({len(warns)}提醒)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
