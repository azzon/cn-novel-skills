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


def check_block(name, args, fail_kw="FAIL]", pass_kw=None):
    r = run(args)
    out = r.stdout
    if r.returncode != 0 and "Traceback" in r.stderr:
        return (name, "FAIL", f"崩溃: {r.stderr.strip().splitlines()[-1][:60]}")
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
    blocks.append(check_block("工具自测(self_test)", ["tools/self_test.py"]))
    blocks.append(check_block("技能库(skills_check)", ["tools/skills_check.py"]))
    blocks.append(check_block("伏笔账(foreshadow_audit)", ["tools/foreshadow_audit.py", str(book)]))
    blocks.append(check_block("数字账(number_audit)", ["tools/number_audit.py", str(book)]))
    blocks.append(check_block("期待链(anticipation_audit)", ["tools/anticipation_audit.py", str(book)]))

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
    blocks.append(("回归基线(evals)", "PASS" if "无回归" in r.stdout else "WARN", r.stdout.strip().splitlines()[-1][:50]))

    # 卡文对账余量
    r = run(["tools/card_check.py", "001", "--volume", "1"])
    ledger = book / "ledgers" / "卡文对账清单.md"
    if ledger.exists():
        pending = sum(1 for l in ledger.read_text(encoding="utf-8").splitlines()
                      if l.strip().startswith("- ch") and "✓" not in l and "⏸" not in l)
        card_note = f"{pending}条待清(修订期)" if pending else "已清零"
    else:
        card_note = "无清单"

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
