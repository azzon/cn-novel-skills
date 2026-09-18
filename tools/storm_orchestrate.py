#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""storm_orchestrate.py 五波风暴编排器(红队20260919: 从prompt生成→闭环强制)

解决的核心问题: agent_storm.py只生成prompt,但没有任何东西保证:
  ① AI真的派发了50个agent
  ② 结果真的被汇总
  ③ 结论真的被执行(放行/打回)

本工具实现完整闭环:
  1. init: 生成5波prompt + 状态追踪文件
  2. status: 显示当前进度(哪些agent已派发/已回报)
  3. record: AI派发agent后,记录结果(评分+致命问题)
  4. aggregate: 汇总所有结果,给出最终gate判定
  5. gate: pipeline done时调用——storm未完成=拒绝done

用法:
  python3 tools/storm_orchestrate.py init <章文件> [--book 书根]
  python3 tools/storm_orchestrate.py status <章文件>
  python3 tools/storm_orchestrate.py record <章文件> <agent_id> <score> "<致命问题>"
  python3 tools/storm_orchestrate.py aggregate <章文件>
"""
import sys, pathlib, json, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# 导入agent_storm的角色定义
from agent_storm import WAVES

def storm_state_path(target):
    """storm状态文件路径"""
    ch_match = re.search(r'第(\d+)章', target.stem)
    ch = ch_match.group(1) if ch_match else "XXX"
    book = target.parent
    while book != book.parent and not (book / "text").is_dir():
        book = book.parent
    return book / "audit" / f"storm-state-{ch}.json"

def cmd_init(target):
    sp = storm_state_path(target)
    sp.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "target": str(target),
        "started": True,
        "waves": {},
        "verdict": None,
    }
    for wn, (label, agents) in WAVES.items():
        state["waves"][str(wn)] = {
            "label": label,
            "agents": {a["id"]: {"role": a["role"], "lens": a["lens"], 
                                  "dispatched": False, "score": None, "issue": None} 
                       for a in agents},
            "complete": False,
        }
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 同时生成prompt文件
    import subprocess
    subprocess.run([sys.executable, str(ROOT/"tools/agent_storm.py"), "chapter", str(target)], 
                   capture_output=True, cwd=ROOT)
    
    print(f"✅ Storm初始化完成")
    print(f"   状态文件: {sp}")
    print(f"   Prompt文件: {sp.parent}/storm/")
    print(f"\n   下一步: 按Wave 1→5顺序,逐个派发agent:")
    for wn, (label, agents) in WAVES.items():
        prompt_file = sp.parent / "storm" / f"chapter-{target.stem[:20]}-wave{wn}.md"
        print(f"   Wave {wn} {label}: 读{prompt_file.name} → 派发{len(agents)}个Agent")
        print(f"     每个agent派发后: python3 tools/storm_orchestrate.py record {target} <agent_id> <score> '<问题>'")
    return 0

def cmd_status(target):
    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化。先跑: storm_orchestrate.py init <文件>")
        return 1
    state = json.loads(sp.read_text(encoding="utf-8"))
    
    total, dispatched, scored = 0, 0, 0
    for wn, wdata in state["waves"].items():
        w_agents = wdata["agents"]
        w_total = len(w_agents)
        w_dispatched = sum(1 for a in w_agents.values() if a["dispatched"])
        w_scored = sum(1 for a in w_agents.values() if a["score"] is not None)
        total += w_total; dispatched += w_dispatched; scored += w_scored
        status_icon = "✅" if w_scored == w_total else "⏳" if w_dispatched > 0 else "⬜"
        print(f"  {status_icon} Wave {wn} {wdata['label']}: {w_scored}/{w_total} 已回报")
    
    print(f"\n  总进度: {scored}/{total} agent已回报")
    if scored < total:
        remaining = []
        for wn, wdata in state["waves"].items():
            for aid, a in wdata["agents"].items():
                if a["score"] is None:
                    remaining.append(f"Wave{wn}:{aid}({a['role']})")
        print(f"  待完成: {', '.join(remaining[:10])}{'...' if len(remaining)>10 else ''}")
    else:
        print(f"  🎉 全部完成! 跑: storm_orchestrate.py aggregate {target}")
    return 0

def cmd_record(target, agent_id, score, issue):
    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化"); return 1
    state = json.loads(sp.read_text(encoding="utf-8"))
    
    found = False
    for wn, wdata in state["waves"].items():
        if agent_id in wdata["agents"]:
            wdata["agents"][agent_id]["dispatched"] = True
            wdata["agents"][agent_id]["score"] = float(score)
            wdata["agents"][agent_id]["issue"] = issue
            found = True
            # 检查wave是否全完成
            if all(a["score"] is not None for a in wdata["agents"].values()):
                wdata["complete"] = True
            break
    
    if not found:
        print(f"❌ Agent {agent_id} 不存在(有效ID: A1-A10,D1-D10,J1-J10,C1-C10,G1-G10)")
        return 1
    
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✅ {agent_id} score={score} issue={issue[:40]}")
    return 0

def cmd_aggregate(target):
    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化"); return 1
    state = json.loads(sp.read_text(encoding="utf-8"))
    
    # 检查完成度
    all_scores = []
    all_issues = []
    wave_scores = {}
    for wn, wdata in state["waves"].items():
        w_scores = [a["score"] for a in wdata["agents"].values() if a["score"] is not None]
        if len(w_scores) < len(wdata["agents"]):
            print(f"❌ Wave {wn} 未完成({len(w_scores)}/{len(wdata['agents'])})——先补完再aggregate")
            return 1
        wave_scores[wn] = sum(w_scores) / len(w_scores)
        all_scores.extend(w_scores)
        for a in wdata["agents"].values():
            if a["issue"] and a["issue"] != "无":
                all_issues.append(f"[{a['role']}] {a['issue']}")
    
    avg = sum(all_scores) / len(all_scores)
    
    # Gate判定
    verdict = "放行"
    reasons = []
    
    # 规则1: 均值≥7.0
    if avg < 7.0:
        verdict = "打回"
        reasons.append(f"总均分{avg:.1f}<7.0")
    
    # 规则2: 任一wave均值≤5.0
    for wn, ws in wave_scores.items():
        if ws <= 5.0:
            verdict = "打回"
            reasons.append(f"Wave{wn}均分{ws:.1f}≤5.0")
    
    # 规则3: Wave2(弃书审判官A2)给出高风险
    for wn, wdata in state["waves"].items():
        if "A2" in wdata["agents"]:
            a2 = wdata["agents"]["A2"]
            if a2["score"] is not None and a2["score"] <= 3.0:
                verdict = "打回"
                reasons.append(f"弃书审判官{a2['score']}分≤3.0(高风险)")
    
    # 规则4: Wave5守卫波未全绿
    w5 = state["waves"].get("5", {})
    if w5:
        w5_avg = wave_scores.get("5", 10)
        if w5_avg < 7.0:
            verdict = "打回"
            reasons.append(f"守卫波均分{w5_avg:.1f}<7.0")
    
    # 输出
    print(f"═══ Storm汇总: {target.name} ═══\n")
    print(f"  总均分: {avg:.1f}/10 (50 agent)")
    for wn in sorted(wave_scores.keys(), key=int):
        print(f"  Wave {wn} {state['waves'][wn]['label']}: {wave_scores[wn]:.1f}")
    print(f"\n  问题清单({len(all_issues)}项):")
    for iss in all_issues[:10]:
        print(f"    ⚠️ {iss[:60]}")
    if len(all_issues) > 10:
        print(f"    ... 共{len(all_issues)}项")
    
    if reasons:
        print(f"\n  ❌ 判定: {verdict}")
        for r in reasons:
            print(f"     原因: {r}")
    else:
        print(f"\n  ✅ 判定: {verdict}")
    
    # 保存verdict
    state["verdict"] = verdict
    state["verdict_score"] = round(avg, 1)
    state["verdict_reasons"] = reasons
    sp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # 写报告
    report = sp.parent / f"storm-report-{target.stem}.md"
    with open(report, "w", encoding="utf-8") as f:
        f.write(f"# Agent Storm报告: {target.name}\n\n")
        f.write(f"## 判定: {verdict}\n\n")
        f.write(f"## 总均分: {avg:.1f}/10\n\n")
        f.write("## 各波得分\n")
        for wn in sorted(wave_scores.keys(), key=int):
            f.write(f"- Wave {wn}: {wave_scores[wn]:.1f}\n")
        f.write(f"\n## 问题清单\n")
        for iss in all_issues:
            f.write(f"- {iss}\n")
    print(f"\n  报告: {report}")
    
    return 0 if verdict == "放行" else 1

def cmd_gate(target):
    """pipeline done调用: storm未完成或未放行=拒绝"""
    sp = storm_state_path(target)
    if not sp.exists():
        return False, "storm未初始化"
    state = json.loads(sp.read_text(encoding="utf-8"))
    if state.get("verdict") is None:
        return False, "storm未aggregate(结果未汇总)"
    if state["verdict"] != "放行":
        reasons = "; ".join(state.get("verdict_reasons", []))
        return False, f"storm判定={state['verdict']}({reasons})"
    return True, f"storm✅({state.get('verdict_score')}分)"

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    
    if cmd == "init" and len(sys.argv) > 2:
        return cmd_init(pathlib.Path(sys.argv[2]))
    elif cmd == "status" and len(sys.argv) > 2:
        return cmd_status(pathlib.Path(sys.argv[2]))
    elif cmd == "record" and len(sys.argv) > 5:
        return cmd_record(pathlib.Path(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5])
    elif cmd == "aggregate" and len(sys.argv) > 2:
        return cmd_aggregate(pathlib.Path(sys.argv[2]))
    elif cmd == "gate" and len(sys.argv) > 2:
        ok, msg = cmd_gate(pathlib.Path(sys.argv[2]))
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    else:
        print(__doc__); return 2

if __name__ == "__main__":
    sys.exit(main())
