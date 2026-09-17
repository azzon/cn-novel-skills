#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
number_audit.py 跨章数字恒等式审计(审计-32 N2: ch37利5800 vs ch39累计亏2200商账崩坏的根治)

原理:
  ledgers/数字账.md 登记科目流水(科目|限定|值|章)与恒等式(A = B + C)。
  本工具:
    1) 恒等式验算: 按账内值自动加总比对,不平=FAIL
    2) 同键矛盾: 同科目+同限定出现多个不同值(账内自相矛盾)=FAIL
    3) 正文抽查: 账内值在登记章的正文中找不到=WARN(账-文失对账,与card_check互补——card查卡,本工具查账)

书根感知: python3 tools/number_audit.py [书根]
"""
import re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card_check import cn2num

ROOT = pathlib.Path(__file__).resolve().parent.parent


def parse_val(s):
    s = s.strip().lstrip("亏欠负损")   # 亏五百/欠四百: 前缀剥除(审计-32)
    s = re.sub(r"(/(天|月|年|单|台|次))?(天|块|元|章|户|年|字|次|单|条|斤|台|个|米|厘米|%|点)?$", "", s.strip())   # 1993审计: "3000/天"斜杠费率   # 磨刀十八批F5: 单位后缀致解析死(恒等式空转)
    s = re.sub(r"^[正±]负?", "", s)   # 1993审计: 公差"正负0.015"类
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    v = cn2num(s)
    return float(v) if v is not None else None


def parse_ledger(path):
    """→ (flows, eqs): flows=[(科目,限定,值,章,原行)], eqs=[(目标, [(科目,限定)...], 原行)]"""
    flows, eqs = [], []
    in_eq = False
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line.startswith("## "):
            in_eq = "恒等式" in line
            continue
        if not line.startswith("- "):
            continue
        body = line[2:]
        if in_eq:
            m = re.match(r"(.+?)\s*=\s*(.+)", body)
            if m:
                target = m.group(1).strip()
                # 磨刀十八批F5: 支持减法与常数项("A = B - 2"/"A = B + C - 3")
                rhs = m.group(2).strip()
                if rhs and rhs[0] not in "+-":
                    rhs = "+" + rhs   # 首项无符号→补+(磨刀十八批: 首项被跳致恒等式只算减项)
                terms = []
                for tm in re.finditer(r"([+-])\s*([^+-]+)", rhs):
                    sign = -1 if tm.group(1) == "-" else 1
                    tok = tm.group(2).strip()
                    if re.fullmatch(r"\d+(?:\.\d+)?", tok):
                        terms.append((sign, ("__const__", tok)))          # 常数项
                    else:
                        mm = re.match(r"([^(]+?)(?:\(([^)]*)\))?$", tok)
                        terms.append((sign, (mm.group(1).strip(), (mm.group(2) or "").strip())))
                eqs.append((target, terms, line))
        else:
            parts = [p.strip() for p in body.split("|")]
            if len(parts) >= 4:
                subj, qual, val, ch = parts[0], parts[1], parts[2], parts[3]
                flows.append((subj, qual, val, ch, line))
    return flows, eqs


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    ledger = book / "ledgers" / "数字账.md"
    if not ledger.exists():
        print(f"无数字账: {ledger}——章生产时入账(见账头说明)")
        return 2
    flows, eqs = parse_ledger(ledger)

    issues, warns = [], []

    # 1) 同键矛盾(红队20260917语义修正): 累计/余额/余欠类键跨章演化是账本本职,
    #    只判"同章同键不同值"=真矛盾;演化键另验方向(累计增/余欠降),反向才FAIL
    import re as _re4
    _evol_up = _re4.compile(r"累计|余额|合计|总计|存")
    _evol_dn = _re4.compile(r"余欠|欠款|负债")
    seen = {}
    for subj, qual, val, ch, raw in flows:
        v = parse_val(val)
        if v is None:
            warns.append(f"账内值无法解析: {raw[:50]}")
            continue
        key = (subj, qual)
        if key in seen:
            pv, pch = seen[key]
            if pch == ch and pv != v:
                issues.append(f"同键矛盾: {subj}[{qual}] ch{pch}={pv:.0f} vs {ch}={v:.0f}")
            elif pch != ch and pv != v:
                if _evol_up.search(subj) and v < pv:
                    issues.append(f"演化反向: {subj}[{qual}] {pch}章={pv:.0f} → {ch}={v:.0f}(应单调不降)")
                if _evol_dn.search(subj) and v > pv:
                    issues.append(f"演化反向: {subj}[{qual}] {pch}章={pv:.0f} → {ch}={v:.0f}(欠款应递减)")
        seen[key] = (v, ch)

    # 2) 恒等式验算
    for target, keys, raw in eqs:
        tm = re.match(r"([^(]+)(?:\(([^)]*)\))?", target)
        t_key = (tm.group(1).strip(), (tm.group(2) or "").strip())
        t_val = seen.get(t_key)
        if t_val is None:
            warns.append(f"恒等式目标无账值: {raw[:60]}")
            continue
        total, ok = 0.0, True
        for sign, k in keys:
            if k[0] == "__const__":
                total += sign * float(k[1])
                continue
            kv = seen.get(k)
            if kv is None:
                warns.append(f"恒等式分项无账值: {k} in {raw[:50]}")
                ok = False
                break
            total += sign * kv[0]
        if ok:
            if abs(total - t_val[0]) > 0.5:
                issues.append(f"恒等式不平(FAIL): {target}={t_val[0]:.0f} 但分项和={total:.0f}——商账崩坏(ch37-39事故形状)")
            else:
                print(f"  ✓ 恒等式验算通过: {target}={t_val[0]:.0f} = 分项和{total:.0f}")

    # 3) 账-文抽查
    for subj, qual, val, ch, raw in flows:
        v = parse_val(val)
        if v is None:
            continue
        m_ch = re.search(r"(\d+)", ch)
        if not m_ch:
            continue
        cn = int(m_ch.group(1))
        cfs = sorted(book.glob("text/卷*/第*.md"))
        cf = next((x for x in cfs if (mm := re.search(r"第(\d+)章", x.name)) and int(mm.group(1)) == cn), None)
        if cf is None:
            continue
        body = cf.read_text(encoding="utf-8-sig")
        # 宽松: 值或其中文形式任一出现
        vs = {str(int(v))} if v == int(v) else {str(v)}
        if v == int(v) and 0 < v < 100000:
            from card_check import extract_vals
            bv = extract_vals(body)
            if v not in bv:
                warns.append(f"账值{v:.0f}({subj}|{qual})在ch{cn:03d}正文未现——账-文失对账或数字在别章")

    for l in issues:
        print(f"  [FAIL] {l}")
    for w in warns:
        print(f"  [WARN] {w}")
    if not issues and not warns:
        print("  数字账全项通过")
    print(f"\n数字审计: {'FAIL' if issues else 'PASS'}(流水{len(flows)}条/恒等式{len(eqs)}条)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
