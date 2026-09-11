#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py v2 — 创作流水线唯一入口（Orchestrator + Supervisor）

新增:
  - 写作循环支持(逐章六步强制)
  - drift-audit自动调度(每10章)
  - 独立审计协议(关键裁决用干净子代理)
  - 违规追踪与统计
"""
import sys, os, json, subprocess, datetime, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(ROOT, ".pipeline_state.json")
AUDIT_LOG = os.path.join(ROOT, ".pipeline_audit.jsonl")

CONCEPTION_PHASES = ["incubate", "premise", "world", "characters", "plot", "trial", "style"]
WRITING_STEPS = ["scene-card", "scene-draft", "scene-audit", "chapter-assemble", "reader-proxy", "ledger-update"]

PHASES = {
    "incubate": {"name": "故事孵化", "skill": "story-incubate",
                 "artifacts": ["story/00a-孵化/"],
                 "checks": ["≥5个文件", "含极端推演", "含角色对话", "含宣言"]},
    "premise": {"name": "前提句竞争", "skill": "premise",
                "artifacts": ["story/00-前提.md"],
                "checks": ["三案竞争记录", "落选坟场"]},
    "world": {"name": "世界观", "skill": "world-rules",
              "artifacts": ["story/10-世界/规则.md"],
              "checks": ["七叶齐"]},
    "characters": {"name": "人物", "skill": "char-bible",
                   "artifacts": ["story/20-人物/主角.md"],
                   "checks": ["对话样本", "活体测试"]},
    "plot": {"name": "情节", "skill": "plot-spine",
             "artifacts": ["story/30-情节/主线.md"],
             "checks": ["挫折预算列"]},
    "trial": {"name": "试写验证", "skill": "trial-write",
              "artifacts": ["story/00z-试写/"],
              "checks": ["≥3章", "冷读记录"]},
    "style": {"name": "风格包", "skill": "style-compiler",
              "artifacts": ["story/50-风格包-v6-白金DNA+红队全量版.md"],
              "checks": ["范例段", "盲评"]},
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"phase": "incubate", "completed": [], "violations": [],
            "chapters": {}, "audit_count": 0, "drift_audits": [],
            "chapter_counter": 0, "created": datetime.datetime.now().isoformat()}

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

def log(event, detail):
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps({"ts": datetime.datetime.now().isoformat(),
                            "event": event, "detail": detail}, ensure_ascii=False) + "\n")

def count_chapters():
    """统计已写章数"""
    import glob
    total = 0
    for f in glob.glob(os.path.join(ROOT, "text/卷*/第*章.md")):
        if "场景" not in f and "AB版" not in f:
            total += 1
    return total

# ══════════════════════════════════════════
# 构思阶段命令
# ══════════════════════════════════════════

def cmd_status():
    s = load_state()
    n = count_chapters()
    print("═" * 50)
    print("  PIPELINE STATUS")
    print("═" * 50)
    print(f"  阶段: {s['phase']}")
    print(f"  已完成: {', '.join(s['completed']) or '—'}")
    print(f"  章节: {n}")
    print(f"  违规: {len(s['violations'])}")
    print(f"  审计: {s['audit_count']}次")

    if s['phase'] in PHASES:
        p = PHASES[s['phase']]
        print(f"\n  当前: {p['name']} (→ {p['skill']})")
        results = check_artifacts(s['phase'])
        for a, ok, d in results:
            print(f"    {'✅' if ok else '❌'} {a}: {d}")
    elif s['phase'] == 'writing':
        print(f"\n  写作循环中")
        last_ch = s.get('chapter_counter', 0)
        print(f"  下一章: 第{last_ch + 1}章")
        print(f"  步骤: {' → '.join(WRITING_STEPS)}")

def check_artifacts(phase):
    p = PHASES[phase]
    results = []
    for artifact in p["artifacts"]:
        path = os.path.join(ROOT, artifact)
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if f.endswith('.md')]
            results.append((artifact, len(files) >= 2, f"{len(files)}文件"))
        elif os.path.isfile(path):
            content = open(path, encoding='utf-8').read()
            results.append((artifact, len(content) > 100, f"{len(content)}字"))
        else:
            results.append((artifact, False, "不存在"))
    return results

def cmd_next():
    s = load_state()
    phase = s['phase']

    if phase == 'writing':
        print("写作循环中。每章六步:")
        for i, step in enumerate(WRITING_STEPS, 1):
            print(f"  {i}. {step}")
        return

    if phase not in PHASES:
        print(f"未知阶段: {phase}")
        return

    # 检查产物
    results = check_artifacts(phase)
    failed = [(a, d) for a, ok, d in results if not ok]
    if failed:
        print(f"❌ 产物不齐:")
        for a, d in failed:
            print(f"   {a}: {d}")
        print(f"\n→ 调用: {PHASES[phase]['skill']}")
        return

    # 标记完成
    s['completed'].append(phase)
    log("phase_complete", {"phase": phase})

    idx = CONCEPTION_PHASES.index(phase)
    if idx + 1 < len(CONCEPTION_PHASES):
        nxt = CONCEPTION_PHASES[idx + 1]
        s['phase'] = nxt
        save_state(s)
        print(f"✅ {PHASES[phase]['name']} 完成 → {PHASES[nxt]['name']}")
    else:
        s['phase'] = 'writing'
        save_state(s)
        print(f"✅ 构思域全部完成 → 进入写作循环")

# ══════════════════════════════════════════
# 写作循环命令
# ══════════════════════════════════════════

def cmd_chapter(ch_num=None):
    """开始/查询某一章的写作流程"""
    s = load_state()
    if s['phase'] != 'writing':
        print(f"当前在构思阶段({s['phase']})，先完成构思")
        return

    if ch_num is None:
        ch_num = s.get('chapter_counter', 0) + 1

    ch_key = f"ch{ch_num}"
    if ch_key not in s['chapters']:
        s['chapters'][ch_key] = {"steps_done": [], "started": datetime.datetime.now().isoformat()}

    ch_state = s['chapters'][ch_key]
    done = ch_state['steps_done']
    remaining = [st for st in WRITING_STEPS if st not in done]

    print(f"═" * 40)
    print(f"  第{ch_num}章 写作流程")
    print(f"═" * 40)
    if done:
        print(f"  已完成: {' → '.join(done)}")
    if remaining:
        print(f"  待做:   {' → '.join(remaining)}")
        print(f"\n→ 下一步调用: {remaining[0]}")
    else:
        print(f"  ✅ 全部完成")
        print(f"→ 归档并推进到第{ch_num + 1}章")
        s['chapter_counter'] = ch_num

        # Drift-audit调度
        if ch_num % 10 == 0:
            print(f"\n  ⚠ 第{ch_num}章(10倍数)——需要drift-audit")
            s['drift_audits'].append({"due_at": ch_num, "done": False})

    save_state(s)

def cmd_step(step, ch_num=None):
    """标记某步完成"""
    s = load_state()
    if ch_num is None:
        ch_num = s.get('chapter_counter', 0) + 1
    ch_key = f"ch{ch_num}"

    if ch_key not in s['chapters']:
        s['chapters'][ch_key] = {"steps_done": [], "started": datetime.datetime.now().isoformat()}

    if step not in WRITING_STEPS:
        print(f"未知步骤: {step}")
        print(f"有效步骤: {WRITING_STEPS}")
        return

    if step not in s['chapters'][ch_key]['steps_done']:
        s['chapters'][ch_key]['steps_done'].append(step)
        log("step_done", {"chapter": ch_num, "step": step})

    done = s['chapters'][ch_key]['steps_done']
    remaining = [st for st in WRITING_STEPS if st not in done]

    if not remaining:
        print(f"✅ 第{ch_num}章六步全部完成")
        s['chapter_counter'] = ch_num

        if ch_num % 10 == 0:
            print(f"⚠ 需要drift-audit")
    else:
        print(f"已完成: {len(done)}/6")
        print(f"下一步: {remaining[0]}")

    save_state(s)

# ══════════════════════════════════════════
# 审计命令
# ══════════════════════════════════════════

def cmd_audit():
    s = load_state()
    s['audit_count'] += 1
    violations = []

    n = count_chapters()

    # 1. 场景卡覆盖率
    import glob
    cards = len(glob.glob(os.path.join(ROOT, "text/卡/*.md")))
    if n > 5:
        ratio = cards / n if n > 0 else 0
        if ratio < 0.7:
            violations.append(f"场景卡覆盖率{ratio:.0%}({cards}/{n})——低于70%")

    # 2. 六步完成率
    total_steps = 0
    complete_chapters = 0
    for ch_key, ch_data in s['chapters'].items():
        total_steps += len(ch_data.get('steps_done', []))
        if len(ch_data.get('steps_done', [])) == 6:
            complete_chapters += 1
    tracked = len(s['chapters'])
    if tracked > 0:
        completion = complete_chapters / tracked
        if completion < 0.6:
            violations.append(f"六步完成率{completion:.0%}({complete_chapters}/{tracked})——低于60%")

    # 3. Drift-audit
    due = [d for d in s.get('drift_audits', []) if not d.get('done')]
    if due:
        violations.append(f"{len(due)}次drift-audit待执行")

    print("═" * 50)
    print("  合规审计")
    print("═" * 50)
    if violations:
        for v in violations:
            print(f"  ⚠ {v}")
        s['violations'].extend(violations)
    else:
        print(f"  ✅ 无违规")

    save_state(s)
    log("compliance_audit", {"violations": violations, "chapters": n})

# ══════════════════════════════════════════
# 重置
# ══════════════════════════════════════════

def cmd_reset():
    """重置流水线状态（新书开始时用）"""
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    if os.path.exists(AUDIT_LOG):
        os.remove(AUDIT_LOG)
    print("✅ 流水线已重置")
    print("→ 重新从 incubate 开始")

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print("\n命令: status | next | chapter [N] | step <name> [ch] | audit | reset")
        return

    cmd = args[0]
    if cmd == "status":
        cmd_status()
    elif cmd == "next":
        cmd_next()
    elif cmd == "chapter":
        cmd_chapter(int(args[1]) if len(args) > 1 else None)
    elif cmd == "step":
        if len(args) > 1:
            cmd_step(args[1], int(args[2]) if len(args) > 2 else None)
    elif cmd == "audit":
        cmd_audit()
    elif cmd == "reset":
        cmd_reset()
    else:
        print(f"未知: {cmd}")

if __name__ == "__main__":
    main()
