#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workflow.py 确定性工作流执行器

用法:
  python3 tools/workflow.py status              # 查看当前工作流状态
  python3 tools/workflow.py next                # 查看下一步该做什么
  python3 tools/workflow.py check-phase <name>  # 检查某phase的gate是否通过
  python3 tools/workflow.py list                # 列出所有可用workflow

Phase类型:
  book_design      新书设计(Phase 1-6 + 终门)
  chapter_production  章节生产(每章循环)
  periodic         周期性审计(每10章/每卷末)

依赖: PyYAML(如果没有则用简易解析器)
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF_DIR = ROOT / "workflows"
STATE_FILE = ROOT / ".workflow_state.json"


def load_yaml_simple(path):
    """简易YAML解析器(不依赖PyYAML)——只提取phases/steps/gate结构"""
    wf = {"workflow": "", "phases": {}}
    current_phase = None
    current_step = None
    for line in path.read_text(encoding="utf-8").splitlines():
        ls = line.strip()
        if not ls or ls.startswith("#"):
            continue
        if ls.startswith("workflow:"):
            wf["workflow"] = ls.split(":", 1)[1].strip()
        elif ls.startswith("phase_") and ls.endswith(":"):
            pid = ls.replace(":", "").strip()
            wf["phases"][pid] = {"steps": [], "name": "", "gate": []}
            current_phase = pid
            current_step = None
        elif ls.startswith("  name:") and current_phase:
            wf["phases"][current_phase]["name"] = ls.split(":", 1)[1].strip()
        elif ls.startswith("      - id:") and current_phase:
            sid = ls.replace("- id:", "").strip()
            wf["phases"][current_phase]["steps"].append({"id": sid, "gate": []})
            current_step = len(wf["phases"][current_phase]["steps"]) - 1
        elif ls.startswith("        gate:") and current_phase and current_step is not None:
            steps = wf["phases"][current_phase]["steps"]
            steps[current_step]["gate"] = []
        elif ls.startswith("          - ") and current_phase and current_step is not None:
            steps = wf["phases"][current_phase]["steps"]
            steps[current_step]["gate"].append(ls.replace("- ", "").strip())
        elif ls.startswith("  final_gate"):
            wf["phases"]["final_gate"] = {"steps": [], "checks": []}
            current_phase = "final_gate"
        elif ls.startswith("  - \"") and current_phase == "final_gate":
            wf["phases"]["final_gate"]["checks"].append(ls.strip())
    return wf


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"current_phase": "", "completed_steps": [], "phase_results": {}}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def run_cmd(cmd, timeout=120):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return r.returncode, r.stdout, r.stderr


def check_gate_condition(condition):
    """检查单个gate条件"""
    # 文件存在检查
    if "output文件存在" in condition or ("已存在" in condition and ".md" in condition):
        # 从条件中提取文件路径
        pass
    # 简化实现: 检查关键文件是否存在
    file_checks = {
        "story/audit/市场调研.md": "市场调研",
        "story/audit/对标拆解.md": "对标拆解",
        "story/00-前提.md": "前提确认",
        "story/60-圣经/声口卡.md": "声口卡",
        "story/20-人物/人物圣经.md": "人物圣经",
        "story/30-情节/主线.md": "主线",
        "story/30-情节/卷一纲.md": "卷一纲",
        "story/50-风格包.md": "风格包",
    }
    for path, name in file_checks.items():
        if name in condition:
            return (ROOT / path).exists(), f"{name}{'✅' if (ROOT / path).exists() else '❌'}"

    # 数字检查
    mm = re.search(r"(\d+)", condition)
    if mm and "得分" in condition:
        return True, f"得分检查(需人工确认): {condition}"

    return True, condition  # 默认通过(需要人工判断的条件)


def cmd_status(wf_name):
    wf_path = WF_DIR / f"{wf_name}.yaml"
    if not wf_path.exists():
        print(f"工作流 {wf_name} 不存在")
        return 1
    wf = load_yaml_simple(wf_path)
    state = load_state()
    print(f"工作流: {wf['workflow']}")
    for pid, phase in wf["phases"].items():
        status = state["phase_results"].get(pid, "pending")
        steps = phase.get("steps", [])
        done_steps = [s for s in steps if f"{pid}.{s['id']}" in state.get("completed_steps", [])]
        print(f"  {pid}: {phase.get('name','')} [{status}] ({len(done_steps)}/{len(steps)} steps)")
    return 0


def cmd_next(wf_name):
    wf_path = WF_DIR / f"{wf_name}.yaml"
    if not wf_path.exists():
        print(f"工作流 {wf_name} 不存在")
        return 1
    wf = load_yaml_simple(wf_path)
    state = load_state()
    for pid, phase in wf["phases"].items():
        steps = phase.get("steps", [])
        for s in steps:
            key = f"{pid}.{s['id']}"
            if key not in state.get("completed_steps", []):
                print(f"下一步: [{pid}] {s.get('name', s['id'])}")
                print(f"  类型: {s.get('type', 'manual')}")
                print(f"  技能: {s.get('skill', 'N/A')}")
                if s.get("gate"):
                    print(f"  门条件:")
                    for g in s["gate"]:
                        print(f"    - {g}")
                return 0
    print("所有步骤已完成")
    return 0


def cmd_list():
    for f in sorted(WF_DIR.glob("*.yaml")):
        wf = load_yaml_simple(f)
        print(f"  {f.stem}: {wf.get('workflow', '')} ({len(wf.get('phases', {}))} phases)")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        # 列出可用workflow
        for f in sorted(WF_DIR.glob("*.yaml")):
            print(f"  {f.stem}")
        return 2
    cmd = sys.argv[1]
    if cmd == "list":
        return cmd_list()
    if len(sys.argv) < 3:
        print("用法: workflow.py <list|status|next> <workflow_name>")
        return 2
    wf_name = sys.argv[2]
    if cmd == "status":
        return cmd_status(wf_name)
    if cmd == "next":
        return cmd_next(wf_name)
    print(f"未知命令: {cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
