#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
legacy_audit.py 存量修剪清单生成器(修订期专项的机器化入口)

扫描全部存量章,按四类病灶出修复清单+优先级评分:
  A 格言/判词密度   (不是X而是Y/这不是…/这叫…)       >0 即入单
  B 段落形态        段均>30字=匀速感/长段(>150字)     超标入单
  C 语气词密度      对白内 吧呢啊嘛呗哦呀嘿啦 /千字    <3 入单
  D 心理活动密度    每千字<1.0 严重缺失                <1.0 入单

优先级 = 各病灶超标幅度加权和; 输出 Markdown 清单(默认写 ledgers/修订期清单.md)

用法:
  python3 tools/legacy_audit.py [--write] [书根]
  --write: 写入 ledgers/修订期清单.md; 缺省只打印
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
APHOR_PAT = re.compile(r"(不是[^。」』]{1,12}[，。]而是|这不是[^。」』]{1,10}[，。]?是|一种叫[^。」』]{1,6}的东西|这话叫|就是道理)")
TW_PAT = re.compile(r"[吧呢啊嘛呗哦呀嘿啦]")
PSYCH_PAT = re.compile(r"(他想|她想|心想|暗想|心里|心中|心底|心知|他明白|她明白|他知道|她知道|意识到)")


def cjk(s):
    return len(re.findall(r"[\u4e00-\u9fff]", s))


def audit_chapter(fp):
    t = fp.read_text(encoding="utf-8-sig")
    n = cjk(t)
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    findings = {}

    # A 格言
    aphor = []
    for i, p in enumerate(paras):
        if "\u201c" in p:
            continue
        # 心理标记句(他知道/他想…)是人物内心判断,不是旁白判词——豁免
        if PSYCH_PAT.search(p):
            continue
        for m in APHOR_PAT.finditer(p):
            aphor.append((i, p[max(0, m.start()-12):m.end()+14]))
    findings["格言"] = aphor

    # B 段落
    plens = [cjk(p) for p in paras]
    avg = sum(plens) / len(plens) if plens else 0
    longs = [(i, l) for i, l in enumerate(plens) if l > 150]
    findings["段均超标"] = ([f"段均{avg:.1f}(>30)"] if avg > 30 else []) + \
                          [f"第{i}段{l}字(>150)" for i, l in longs]

    # C 语气词
    dia = "".join(re.findall(r"\u201c([^\u201c\u201d]+)\u201d", t))
    tw = len(TW_PAT.findall(dia)) / max(1, cjk(dia)) * 1000
    findings["语气词"] = [f"对白语气词{tw:.1f}/千字(<3)"] if tw < 3 and dia else []

    # D 心理
    psy = len(PSYCH_PAT.findall(t)) / max(1, n) * 1000
    findings["心理缺失"] = [f"心理活动{psy:.1f}/千字(<1.0)"] if psy < 1.0 else []

    # E 对话密度(与check.py #16同口径: 对白段整段/全文; <40%入单)
    dpct = sum(cjk(pp) for pp in paras if "\u201c" in pp) / max(1, n) * 100
    findings["对话不足"] = [f"对话{dpct:.0f}%(<40%)"] if dpct < 40 else []

    # 优先级: 格言条数*3 + 段超幅度 + 语气词缺幅*2 + 心理缺幅
    score = len(aphor) * 3
    score += max(0, avg - 30)
    if tw < 3 and dia:
        score += (3 - tw) * 2
    if psy < 1.0:
        score += (1.0 - psy) * 3
    score += len(longs) * 2
    if dpct < 40:
        score += (40 - dpct) * 0.5
    return n, score, findings, {"段均": round(avg, 1), "语气/千": round(tw, 1), "心理/千": round(psy, 1)}


def main():
    args = [a for a in sys.argv[1:] if a != "--write"]
    write = "--write" in sys.argv
    root = pathlib.Path(args[0]).resolve() if args else ROOT
    files = sorted(root.glob("text/卷*/第*.md"))
    if not files:
        print(f"无章节: {root}")
        return 2
    rows = []
    for f in files:
        n, score, findings, metrics = audit_chapter(f)
        rows.append((f, n, round(score, 1), findings, metrics))
    rows.sort(key=lambda x: -x[2])

    vol_sum = sum(r[2] for r in rows)
    print(f"{'章':<12}{'优先级':>6}{'段均':>6}{'语气/千':>7}{'心理/千':>7}  病灶")
    work = []
    for f, n, score, findings, m in rows:
        if score <= 0:
            continue
        kinds = "; ".join(f"{k}×{len(v) if isinstance(v, list) else v}" for k, v in findings.items() if v)
        work.append((f, score, findings, m))
        print(f"{f.name:<12}{score:>6}{m['段均']:>6}{m['语气/千']:>7}{m['心理/千']:>7}  {kinds[:60]}")
    print(f"\n待修章数: {len(work)}/{len(rows)}  优先级总和: {vol_sum:.0f}")
    print("口径: 优先级=格言×3+段超幅度+语气缺幅×2+心理缺幅×3+长段×2+对话缺幅×0.5; 从上往下修,每章完跑 check.py 复验")

    if write:
        out = root / "ledgers" / "修订期清单.md"
        out.parent.mkdir(exist_ok=True)
        lines = ["# 修订期清单(存量修剪)", "",
                 f"> 由 tools/legacy_audit.py 自动生成; 优先级=格言×3+段超幅度+语气缺幅×2+心理缺幅×3+长段×2+对话缺幅×0.5。",
                 "> 修订完成一章后: 重跑本脚本,该章自动出清单; 同步 check.py 复验。", "",
                 "| 章 | 优先级 | 病灶明细 |", "|---|---|---|"]
        for f, score, findings, m in work:
            detail = "; ".join(
                f"{k}:" + ";".join(x[1] if isinstance(x, tuple) else str(x) for x in v[:2])
                for k, v in findings.items() if v)
            lines.append(f"| {f.name} | {score:.1f} | {detail[:180]} |")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写入: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
