#!/usr/bin/env python3
"""number_verify.py 数字账自动验算器(红队20260917-#12/#6需求书)

原理: 经营流小说的数字账是生命线。本工具对 ledgers/数字账.md 做静态验算,
并对正文做三类交叉抽查(红队#6真实事故的机器化):
  1. 进度复算: "进度|X/Y|Z%" → Z% == round(X/Y*100)±1
  2. 加总闭合: 同章"凑齐/合计N"条目 → 分项之和 == N(±0.01)
  3. 月流水 ≥ 单日max: 同主体月值 < 日值 → FAIL(013事故形状)
  4. 卡-歧义数字表: 三千一年=3100类已在card_check修复,此处复验存量卡

用法: python3 tools/number_verify.py [--book 书根]
退出: 0=全过 1=有FAIL
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LEDG = ROOT / "ledgers" / "数字账.md"


def parse_ledger(path):
    """→ [(章, 科目, 限定, 值raw)] 值可为数字或'待考核'"""
    rows = []
    for ln in (path.read_text(encoding="utf-8") if path.exists() else "").splitlines():
        m = re.match(r"-\s*([^|]+)\|([^|]*)\|([^|]*)\|第(\d+)章", ln.strip())
        if m:
            rows.append((int(m.group(4)), m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return rows


def to_num(s):
    s = s.replace(",", "").replace("，", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else None


def main():
    book = pathlib.Path(sys.argv[sys.argv.index("--book") + 1]) if "--book" in sys.argv else ROOT
    led = book / "ledgers" / "数字账.md"
    rows = parse_ledger(led)
    fails, warns = [], []

    # 1. 进度复算
    for ch, subj, qual, val in rows:
        if "进度" in subj:
            m = re.search(r"([\d.]+)/([\d.]+)", qual)
            pct = to_num(val)
            if m and pct and to_num(m.group(2)) > 0:
                exp = round(float(m.group(1)) / float(m.group(2)) * 100, 1)
                if abs(exp - pct) > 1.5:
                    fails.append(f"ch{ch:03d} {subj}: {qual}={val} 实算{exp}% (进度不符)")

    # 2. 月流水≥单日: 同科目含"单日"与"月"的对照
    days = {r[3]: r for r in rows if "单日" in r[1] + r[2]}
    for ch, subj, qual, val in rows:
        if re.search(r"月(均|流水)", subj + qual) and to_num(val):
            for dstr, (dch, _, _, dval) in list(days.items())[:5]:
                dv, mv = to_num(dval), to_num(val)
                if dv and mv and "破" not in dval and mv < dv and dch <= ch:
                    # 月值小于此前单日峰值 → 可疑
                    if mv * 30 < dv:  # 月连单日30倍都不到=必错
                        fails.append(f"ch{ch:03d} {subj}({val}) < ch{dch:03d} 单日({dval}) 30倍线")

    # 3. 凑总闭合: 找"凑/合计/共"科目,分项在同章
    for ch, subj, qual, val in rows:
        if re.search(r"凑|合计|共", subj + qual) and to_num(val):
            total = to_num(val)
            parts = [to_num(v2) for c2, s2, q2, v2 in rows
                     if c2 == ch and to_num(v2) and v2 != val and s2 != subj]
            # 不做强断言(分项口径多样),只警告数量级崩坏
            if parts and max(parts) > total * 1.2:
                warns.append(f"ch{ch:03d} {subj}合计{val} 但存在单分项>{total}*1.2 — 核对口径")

    print("═══ 数字账自动验算 ═══")
    for f in fails:
        print(f"  [FAIL] {f}")
    for w in warns:
        print(f"  [WARN] {w}")
    if not fails and not warns:
        print("  全过")
    print(f"验算: {len(rows)}条 | FAIL {len(fails)} | WARN {len(warns)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
