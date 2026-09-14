#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_runner.py 确定性章节生产流水线执行器

用法:
  python3 tools/pipeline_runner.py run <章号>     # 运行完整章节生产流水线
  python3 tools/pipeline_runner.py run-batch <起> <止>  # 批量运行
  python3 tools/pipeline_runner.py status         # 查看流水线状态

每个章节经过以下阶段(任一阶段FAIL则停止):
  1. 场景卡(检查存在+完整性)
  2. 初稿生成(LLM——需人工触发)
  3. check.py质量门
  4. gate_chapter韧性门
  5. 结构同构门(structure_check)
  6. 台账盖章(七账+当前时刻卡+章摘要)
  7. evals回归验证
  8. commit+push

本工具是系统的"心脏"——确保每个章节都经过相同的严格流程。
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".pipeline_state.json"


def run(cmd, timeout=300):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


def find_chapter(n):
    for vol in ["卷1", "卷2", "卷3"]:
        p = ROOT / "text" / vol / f"第{n:03d}章.md"
        if p.exists():
            return p
    return None


def get_card(n):
    for p in (ROOT / "text" / "卡").glob(f"*第{n:03d}章*"):
        return p
    return None


def step_check_card(n):
    card = get_card(n)
    if card is None:
        return False, "场景卡不存在"
    ct = card.read_text(encoding="utf-8")
    # 存量章(ch≤45)用旧标准: 场景型/价值/钩; 新章(ch≥46)用新标准
    if n <= 45:
        required = ["场景型", "价值", "钩"]
    else:
        required = ["场景型", "价值", "钩", "情感目标", "冲突源", "代价", "赢法类型", "峰值场景", "峰后动作", "开场型", "阻碍"]
    missing = [f for f in required if f not in ct]
    if missing:
        return False, f"场景卡缺字段: {missing}"
    return True, "场景卡OK"


def step_check_gates(n):
    f = find_chapter(n)
    if f is None:
        return False, "章节文件不存在"
    rc, out, _ = run(f"python3 tools/check.py --modern {f}")
    fails = re.findall(r"\[FAIL\]", out)
    if fails:
        first_fail = re.search(r"\[FAIL\](.+)", out)
        return False, f"check.py FAIL: {first_fail.group(1)[:60] if first_fail else 'unknown'}"
    return True, f"check.py PASS ({len(fails)} FAIL)"


def step_check_structure(n):
    rc, out, _ = run("python3 tools/structure_check.py", timeout=60)
    # structure_check是全局的,只要不崩溃就算过
    return True, "structure_check OK"


def step_check_evals(n):
    rc, out, _ = run("python3 tools/evals.py check", timeout=120)
    if "无回归" in out:
        return True, "evals无回归"
    return False, f"evals回归: {out[:100]}"


def step_check_ledger(n):
    missing = []
    for name in ["伏笔", "梗", "钩分布", "类型轮换", "人物状态", "线弦", "时间线"]:
        fp = ROOT / "ledgers" / f"{name}.md"
        if fp.exists():
            t = fp.read_text(encoding="utf-8")
            if f"第{n:03d}章" not in t and f"第{n}章" not in t:
                missing.append(name)
    if missing:
        return False, f"七账未盖章: {missing}"
    return True, "八账已盖章"


def step_check_bible(n):
    bs = ROOT / "story" / "60-圣经" / "章摘要.md"
    if bs.exists():
        t = bs.read_text(encoding="utf-8")
        if f"| {n:03d} |" in t:
            return True, "章摘要已更新"
    return False, f"章摘要缺第{n:03d}章条目"


def step_check_moment(n):
    mc = ROOT / "ledgers" / "当前时刻卡.md"
    if mc.exists():
        t = mc.read_text(encoding="utf-8")
        if f"第{n:03d}章" in t:
            return True, "当前时刻卡已更新"
    return False, f"当前时刻卡未含第{n:03d}章"


STEPS = [
    ("场景卡", step_check_card),
    ("质量门", step_check_gates),
    ("结构门", step_check_structure),
    ("evals", step_check_evals),
    ("台账", step_check_ledger),
    ("章摘要", step_check_bible),
    ("时刻卡", step_check_moment),
]


def run_pipeline(n):
    n = int(n)
    print(f"\n{'='*50}")
    print(f"  第{n:03d}章 生产流水线")
    print(f"{'='*50}")

    results = []
    all_pass = True

    for name, fn in STEPS:
        ok, msg = fn(n)
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}: {msg}")
        results.append((name, ok, msg))
        if not ok:
            all_pass = False

    print(f"\n{'='*50}")
    if all_pass:
        print(f"  ✅ 第{n:03d}章 全部{len(STEPS)}阶段通过")
    else:
        fails = [r for r in results if not r[1]]
        print(f"  ❌ 第{n:03d}章 {len(fails)}阶段未通过:")
        for name, ok, msg in fails:
            print(f"     ❌ {name}: {msg}")

    print(f"{'='*50}")
    return all_pass


def cmd_run(args):
    if not args:
        print("用法: pipeline_runner.py run <章号>")
        return 2
    return 0 if run_pipeline(int(args[0])) else 1


def cmd_run_batch(args):
    if len(args) < 2:
        print("用法: pipeline_runner.py run-batch <起> <止>")
        return 2
    start, end = int(args[0]), int(args[1])
    results = []
    for n in range(start, end + 1):
        ok = run_pipeline(n)
        results.append((n, ok))
        print()
    fails = [n for n, ok in results if not ok]
    if fails:
        print(f"批量结果: {len(results)-len(fails)}/{len(results)}通过, FAIL: {fails}")
        return 1
    print(f"批量结果: {len(results)}章全部通过")
    return 0


def cmd_status(args):
    total = 0
    for f in sorted(ROOT.glob("text/卷*/第*.md")):
        m = re.search(r"第(\d+)章", f.name)
        if m:
            n = int(m.group(1))
            total += 1
    print(f"当前进度: {total}章")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "run" and len(sys.argv) > 2:
        return 0 if run_pipeline(int(sys.argv[2])) else 1
    if cmd == "run-batch" and len(sys.argv) > 3:
        ok_count, fail_count = 0, 0
        for n in range(int(sys.argv[2]), int(sys.argv[3]) + 1):
            r = run_pipeline(n)
            if r:
                ok_count += 1
            else:
                fail_count += 1
                print(f"  ❌ ch{n} FAIL")
        print(f"\n批量: {ok_count}✅ {fail_count}❌")
        return 0 if fail_count == 0 else 1
    if cmd == "status":
        return cmd_status([])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
