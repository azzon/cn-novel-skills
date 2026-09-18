#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
system_readiness.py 系统就绪度仪表盘(磨刀总问: "刀磨到几成了?能不能开生产?")

汇总全部子系统健康度,输出单一判定:
  ✅ 生产就绪     — 全绿,可开新章流水
  🟡 带病可开     — 无FAIL,有提醒(修订清单内的账面工作不阻塞生产)
  🔴 先修再产     — 存在FAIL级问题(工具坏/门误伤/账本崩)

用法: python3 tools/system_readiness.py [书根]
"""
import subprocess, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = sys.executable


def run(args):
    return subprocess.run([PY] + args, capture_output=True, text=True, cwd=ROOT)


def check_block(name, args, fail_kw="FAIL]", pass_kw=None, use_rc=False):
    r = run(args)
    out = r.stdout
    if r.returncode != 0 and "Traceback" in r.stderr:
        return (name, "FAIL", f"崩溃: {r.stderr.strip().splitlines()[-1][:60]}")
    if use_rc and r.returncode not in (0, 2):  # QW-005: returncode判断(skills_check等)
        return (name, "FAIL", f"exit={r.returncode}")
    if fail_kw and fail_kw in out:
        # FAIL 数量
        n = out.count("[FAIL]")
        return (name, "FAIL", f"{n}项")
    if pass_kw and pass_kw not in out:
        return (name, "FAIL", f"无'{pass_kw}'标记")
    warns = out.count("[WARN]")
    return (name, "PASS", f"{warns}提醒" if warns else "全绿")


def main():
    args = [a for a in sys.argv[1:]]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    tag = "主书" if book == ROOT else book.name

    blocks = []
    blocks.append(check_block("存稿水位(stock_watch)", ["tools/stock_watch.py"] + ([str(book)] if book != ROOT else []), fail_kw="🔴"))
    blocks.append(check_block("口碑资产(memorable_audit)", ["tools/memorable_audit.py"] + ([str(book)] if book != ROOT else [])))
    blocks.append(check_block("多书隔离(isolation)", ["tools/book_isolation_check.py"]))
    blocks.append(check_block("全工序审计(process_audit)", ["tools/process_audit.py"] + ([str(book)] if book != ROOT else []), fail_kw="✗"))
    blocks.append(check_block("工具自测(self_test)", ["tools/self_test.py"], pass_kw="全部通过"))
    blocks.append(check_block("技能库(skills_check)", ["tools/skills_check.py"], use_rc=True))
    blocks.append(check_block("伏笔账(foreshadow_audit)", ["tools/foreshadow_audit.py", str(book)]))
    blocks.append(check_block("数字账(number_audit)", ["tools/number_audit.py", str(book)]))
    blocks.append(check_block("期待链(anticipation_audit)", ["tools/anticipation_audit.py", str(book)]))
    # 流派契约+矿产(红队20260915: book_design全软步骤,genre门必须仪表盘强制)
    blocks.append(check_block("流派契约(genre_contract)", ["tools/genre_contract.py", str(book)]))
    if book != ROOT:
        blocks.append(check_block("矿产账(goldmine_audit)", ["tools/goldmine_audit.py", str(book)]))
    else:
        blocks.append(check_block("矿产账(goldmine_audit)", ["tools/goldmine_audit.py", "story"]))

    # check.py 全量(主书45章按卷扫;书根同)
    fails, total = 0, 0
    for f in sorted(book.glob("text/卷*/第*.md")) if book != ROOT else sorted(ROOT.glob("text/卷*/第*.md")):
        r = run(["tools/check.py", "--modern", str(f)])
        total += 1
        if "[FAIL]" in r.stdout:
            fails += 1
    blocks.append(("正文质量门(check全量)", "PASS" if fails == 0 else "WARN",
                   f"{total - fails}/{total} 章零FAIL" + (f",{fails}章FAIL/豁免" if fails else "")))

    # evals
    r = run(["tools/evals.py", "check"] + ([str(book)] if book != ROOT else []))
    evals_out = r.stdout.strip().splitlines()[-1][:50] if r.stdout.strip() else "(无基线数据)"
    blocks.append(("回归基线(evals)", "PASS" if "无回归" in r.stdout else "WARN", evals_out))

    # 设计完整性(拉力审计教训: 法医书立项漏人物圣经,欲望引擎从未设计,正文"技术合格没兴趣")
    if book != ROOT:
        missing_design = []
        bible = None
        for cand in ["人物圣经.md", "story/20-人物/人物圣经.md", "声口卡.md"]:
            if (book / cand).exists():
                bible = book / cand
                break
        if bible is None:
            missing_design.append("人物圣经")
        elif bible and "ghost" not in bible.read_text(encoding="utf-8").lower() and "欲望" not in bible.read_text(encoding="utf-8") and "want" not in bible.read_text(encoding="utf-8").lower():
            missing_design.append("人物圣经缺ghost/want引擎字段")
        xianxian = book / "ledgers" / "线弦.md"
        if xianxian.exists() and "欲望线" not in xianxian.read_text(encoding="utf-8"):
            missing_design.append("线弦账无'欲望线'条目(主角私人欲望未登记)")
        blocks.append(("设计完整性(人物引擎)", "FAIL" if missing_design else "PASS",
                       "缺: " + "; ".join(missing_design) if missing_design else "人物引擎在位"))

    # 卡文对账余量
    r = run(["tools/card_check.py", "001", "--volume", "1"])
    ledger = book / "ledgers" / "卡文对账清单.md"
    if ledger.exists():
        pending = sum(1 for l in ledger.read_text(encoding="utf-8").splitlines()
                      if l.strip().startswith("- ch") and "✓" not in l and "⏸" not in l)
        card_note = f"{pending}条待清(修订期)" if pending else "已清零"
    else:
        card_note = "无清单"

    # 商业闭环(磨刀十四批: 发布工作流/反馈账/商业质量线三件在位性)
    biz = []
    if not (ROOT / "workflows" / "publish.yaml").exists():
        biz.append("publish.yaml")
    if not (book / "ledgers" / "读者反馈账.md").exists():
        biz.append("读者反馈账")
    if not (ROOT / "docs" / "商业质量线.md").exists():
        biz.append("商业质量线文档")
    blocks.append(("商业闭环(发布/反馈)", "WARN" if biz else "PASS",
                   "缺: " + ";".join(biz) + "(商用必需)" if biz else "发布链+反馈回路在位"))

    # 汇总
    print(f"═══ 系统就绪度({tag}) ═══")
    hard_fail = 0
    for name, st, note in blocks:
        icon = {"PASS": "✅", "WARN": "🟡", "FAIL": "🔴"}[st]
        if st == "FAIL":
            hard_fail += 1
        print(f"  {icon} {name}: {note}")
    print(f"  📋 卡文对账: {card_note}")
    print()
    if hard_fail:
        print(f"🔴 判定: 先修再产({hard_fail}项FAIL)")
        return 1
    hard_warn = sum(1 for _, st, _ in blocks if st == "WARN")
    if hard_warn:
        print(f"🟡 判定: 带病可开({hard_warn}项提醒;修订清单工作不阻塞新章生产,但每章归档时需跑三联动)")
    else:
        print("✅ 判定: 生产就绪")
    return 0


if __name__ == "__main__":
    sys.exit(main())
