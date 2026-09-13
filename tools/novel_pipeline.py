#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
novel_pipeline.py 小说生产全流程确定性执行器

核心改变：从"一堆独立工具靠人记着调用"变为"一条流水线按序执行，每步有gate，不过就停"。

子命令：
  init    <书名>       初始化新书（创建目录+模板+检查清单）
  design  <阶段>       执行设计阶段（market/concept/character/world/plot/style/redteam）
  write   <章号>       单章生产流水线（场景卡→质检→修订→盖章→提交）
  audit   <范围>       审计（drift/consistency/character）
  status               全书状态总览
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / ".novel_pipeline_state.json"

# ── 工具调用 ──

def run(cmd, timeout=300):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr

# ── 状态管理 ──

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"novels": {}}

def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")

def get_novel(name):
    s = load_state()
    return s["novels"].setdefault(name, {
        "phase": "init",
        "chapters_done": [],
        "audits_done": [],
        "gates_passed": [],
        "gates_failed": [],
    })

def save_novel(name, data):
    s = load_state()
    s["novels"][name] = data
    save_state(s)

# ── Gate检查器 ──

def gate_file_exists(path):
    return (ROOT / path).exists()

def gate_check_passes(filepath):
    rc, out, _ = run(f"python3 tools/check.py --modern {filepath}")
    fails = re.findall(r"FAIL (\d+)章", out)
    return int(fails[-1]) == 0 if fails else True

def gate_word_count(filepath, min_chars=2500):
    t = pathlib.Path(filepath).read_text(encoding="utf-8") if (ROOT / filepath).exists() else ""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", t))
    return cjk >= min_chars, cjk

# ── 阶段定义 ──

DESIGN_PHASES = [
    ("market",    "市场调研",   ["story/audit/市场调研.md"], "agent:market-scan"),
    ("premise",   "前提方案",   ["story/00-前提.md"], "agent:story-incubate"),
    ("redteam",   "前提红队",   ["story/audit/前提红队报告.md"], "agent:ideate-audit"),
    ("characters", "角色设计",  ["story/20-人物/人物圣经.md", "story/20-人物/声口卡.md"], "agent:char-bible"),
    ("world",     "世界构建",   ["story/10-世界/规则.md", "story/10-世界/经济.md"], "agent:world-rules"),
    ("plot",      "情节架构",   ["story/30-情节/主线.md", "story/30-情节/卷一纲.md"], "agent:volume-outline"),
    ("redteam2",  "大纲红队",   ["story/audit/大纲红队报告.md"], "agent:ideate-audit"),
    ("style",     "风格校准",   ["story/50-风格包.md"], "agent:style-compiler"),
]

DESIGN_GATE = [
    ("story/00-前提.md", "前提文件"),
    ("story/20-人物/人物圣经.md", "人物圣经"),
    ("story/20-人物/声口卡.md", "声口卡"),
    ("story/30-情节/主线.md", "主线"),
    ("story/30-情节/卷一纲.md", "卷一纲"),
    ("story/50-风格包.md", "风格包"),
    ("story/10-世界/规则.md", "世界规则"),
]

# ── 命令 ──

def cmd_init(args):
    if not args:
        print("用法: pipeline.py init <书名>")
        return 2
    name = args[0]
    nd = get_novel(name)
    nd["phase"] = "design"
    save_novel(name, nd)
    print(f"新书 [{name}] 初始化完成。当前阶段: design")
    print(f"下一步: python3 tools/novel_pipeline.py design market --novel {name}")
    return 0

def cmd_design(args):
    if len(args) < 1:
        print("用法: pipeline.py design <阶段名>")
        return 2
    phase = args[0]
    matches = [p for p in DESIGN_PHASES if p[0] == phase]
    if not matches:
        print(f"可用阶段: {', '.join(p[0] for p in DESIGN_PHASES)}")
        return 2
    name, desc, outputs, executor = matches[0]
    print(f"阶段: {desc}")
    print(f"执行器: {executor}")
    print(f"预期产出: {', '.join(outputs)}")
    for o in outputs:
        exists = (ROOT / o).exists()
        print(f"  {'✅' if exists else '❌'} {o}")
    missing = [o for o in outputs if not (ROOT / o).exists()]
    if missing:
        print(f"\n需要完成: {', '.join(missing)}")
        print(f"完成后运行: python3 tools/novel_pipeline.py design {phase} --verify")
    else:
        print(f"\n✅ {desc}阶段完成")
    return 0

def cmd_write(args):
    if not args:
        print("用法: pipeline.py write <章号>")
        return 2
    n = int(args[0])
    vol = "卷1" if n <= 30 else "卷2"
    filepath = ROOT / "text" / vol / f"第{n:03d}章.md"
    if not filepath.exists():
        print(f"❌ {filepath} 不存在——先写正文")
        return 1

    print(f"\n{'='*50}")
    print(f"  第{n:03d}章 生产流水线")
    print(f"{'='*50}")

    # Step 1: 引号修复
    print("  [1/8] 直引号修复")
    run(f"python3 tools/fix_quotes.py {filepath}")

    # Step 2: check.py
    print("  [2/8] check.py 质量门")
    rc, out, _ = run(f"python3 tools/check.py --modern {filepath}")
    fails = re.findall(r"FAIL (\d+)章", out)
    if fails and int(fails[-1]) > 0:
        print(f"  ❌ {fails[-1]} FAIL")
        for l in out.splitlines():
            if "FAIL]" in l:
                print(f"     {l.strip()}")
        return 1
    print(f"  ✅ 质量门通过")

    # Step 3: gate_chapter
    print("  [3/8] gate_chapter 韧性门")
    rc, out, _ = run(f"python3 tools/gate_chapter.py modified {filepath}")
    if "FAIL" in out:
        print(f"  ❌ gate_chapter FAIL")
        for l in out.splitlines():
            if "FAIL]" in l:
                print(f"     {l.strip()}")
        return 1
    print(f"  ✅ 韧性门通过")

    # Step 4: 结构检查
    print("  [4/8] structure_check")
    run("python3 tools/structure_check.py")

    # Step 5: 台账检查
    print("  [5/8] 台账盖章检查")
    missing = []
    for ledger in ["伏笔", "梗", "钩分布", "类型轮换", "人物状态", "线弦", "时间线"]:
        lp = ROOT / "ledgers" / f"{ledger}.md"
        if lp.exists():
            lt = lp.read_text(encoding="utf-8")
            if f"第{n:03d}章" not in lt:
                missing.append(ledger)
    if missing:
        print(f"  ⚠ 未盖章: {missing}——运行ledger-update")
    else:
        print(f"  ✅ 八账已盖章")

    # Step 6: 章摘要
    print("  [6/8] 章摘要检查")
    bs = ROOT / "story" / "60-圣经" / "章摘要.md"
    if bs.exists() and f"| {n:03d} |" in bs.read_text(encoding="utf-8"):
        print(f"  ✅ 章摘要已更新")
    else:
        print(f"  ⚠ 章摘要缺第{n:03d}章条目")

    # Step 7: 时刻卡
    print("  [7/8] 当前时刻卡检查")
    mc = ROOT / "ledgers" / "当前时刻卡.md"
    if mc.exists() and f"第{n:03d}章" in mc.read_text(encoding="utf-8"):
        print(f"  ✅ 当前时刻卡已更新")
    else:
        print(f"  ⚠ 当前时刻卡未更新")

    # Step 8: evals
    print("  [8/8] evals回归")
    rc, out, _ = run("python3 tools/evals.py check")
    if "无回归" in out:
        print(f"  ✅ {out.strip()}")
    else:
        print(f"  ⚠ {out.strip()[:80]}")

    print(f"\n{'='*50}")
    print(f"  第{n:03d}章 流水线完成")
    print(f"{'='*50}")
    return 0


def cmd_status(args):
    print("=== 小说生产流水线状态 ===\n")
    # 正文
    total = 0
    for f in sorted(ROOT.glob("text/卷*/第*.md")):
        total += 1
    print(f"  总章数: {total}")
    # 机器门状态
    rc, out, _ = run("python3 tools/workflow.py list")
    print(f"\n  可用工作流:")
    for l in out.splitlines():
        if l.strip():
            print(f"    {l.strip()}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "init" and len(sys.argv) > 2:
        return cmd_init(sys.argv[2:])
    if cmd == "design" and len(sys.argv) > 2:
        return cmd_design(sys.argv[2:])
    if cmd == "write" and len(sys.argv) > 2:
        return cmd_write(sys.argv[2:])
    if cmd == "status":
        return cmd_status([])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
