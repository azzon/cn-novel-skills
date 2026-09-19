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

用法(20260919用户令二批: 每章必跑全波v2+修复迭代):
  python3 tools/storm_orchestrate.py init <章文件>            # 初始化(v2角色表12×5=60agent)+prompt
  python3 tools/storm_orchestrate.py status <章文件>          # 进度
  python3 tools/storm_orchestrate.py record <章文件> <id> <score> "<问题>"   # 或 --file <jsonl>批量
  python3 tools/storm_orchestrate.py repair <章文件> --file <jsonl>          # 修复迭代批: {"id":"A1","action":..,"verify":8.0}
  python3 tools/storm_orchestrate.py aggregate <章文件>       # 汇总: 角色覆盖校验+净问题闭环判定
  python3 tools/storm_orchestrate.py gate <章文件>            # pipeline done调用
  python3 tools/storm_orchestrate.py backlog <书根>           # 债务清册(每章必须v2全波放行)
  python3 tools/storm_orchestrate.py selftest                 # 引擎自测(5断言)
硬门: ①角色覆盖(v1旧state=债务) ②Wave1净问题(<6.5)须verify>=7.0 ③守卫波≥7.0 ④迭代>3轮升级重写
"""
import sys, pathlib, json, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# v2角色注册表(20260919用户令: 每章必跑全波+角色增强+修复迭代到通过)
from storm_roles import WAVES, STORM_ROLE_VERSION, all_role_ids

VALID_ID_MSG = "有效ID: " + ", ".join(f"{w}:{'-'.join(ids[:1])}..{ids[-1]}" for w, ids in all_role_ids().items())

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
        "role_version": STORM_ROLE_VERSION,
        "waves": {},
        "repairs": [],      # 修复迭代: {"id":..,"action":..,"verify":..}——每条净问题须verify>=7.0
        "repair_iters": 0,  # 迭代批次数(>3轮=升级整场重写)
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

def cmd_record_file(target, fpath):
    """批量record: --file <jsonl> 每行 {"id":"A1","score":7.5,"issue":"..."}(终打磨: 50次手工调用降为1次)"""
    import json as _json
    rows = [l for l in pathlib.Path(fpath).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = fail = 0
    for l in rows:
        try:
            r = _json.loads(l)
            rc = cmd_record(target, r["id"], r["score"], r.get("issue", "无"))
            ok += 1 if rc == 0 else 0
            fail += 0 if rc == 0 else 1
        except Exception as e:
            print(f"  [SKIP] 行解析失败: {e}")
            fail += 1
    print(f"批量record: 成功{ok} 失败{fail}")
    return 0 if fail == 0 else 1


def cmd_record(target, agent_id, score, issue):
    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化"); return 1
    state = json.loads(sp.read_text(encoding="utf-8"))
    # W6验证修复: verdict_locked只写不读——aggregate后仍可改分而gate读旧verdict
    if state.get("verdict_locked"):
        print("❌ verdict已锁定(aggregate已跑)——改分须先重跑aggregate重算;直接record会被gate忽略")
        return 1
    # W6验证修复: 分数无范围校验(负数/100入账操纵均值)
    try:
        _sc = float(score)
    except (TypeError, ValueError):
        print(f"❌ 分数非法: {score}"); return 1
    if not (0 <= _sc <= 10):
        print(f"❌ 分数超范围(0-10): {score}"); return 1

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
        print(f"❌ Agent {agent_id} 不存在({VALID_ID_MSG})")
        return 1
    
    _tmp = sp.with_suffix(".tmp")   # W6验证:裸write_text断电=json损坏且无兜底
    _tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    _tmp.replace(sp)
    print(f"  ✅ {agent_id} score={score} issue={issue[:40]}")

    # 盲区015修复: Wave1完成时自动注入Wave2 prompt
    try:
        if agent_id.startswith("A") and wdata.get("complete"):
            _inject_wave1_results(state, target, sp)
    except Exception as _e:
        print(f"  [WARN] Wave1注入Wave2失败: {_e}")
    return 0

def _inject_wave1_results(state, target, sp):
    """Wave1完成后,把攻击结果写入Wave2的prompt(漏洞9)"""
    wave1 = state["waves"].get("1", {})
    if not wave1.get("complete"):
        return
    charges = []
    for aid in sorted(wave1["agents"].keys()):
        a = wave1["agents"][aid]
        if a["score"] is not None and a["issue"]:
            charges.append("  " + aid + "(" + a["role"] + "): " + str(a["issue"]))
    if not charges:
        return
    import re as _re
    _stem = _re.sub(r"[^\w]", "-", target.stem)[:20]   # W6验证:与agent_storm落盘名同清洗,否则exists()恒假静默失败
    wave2_file = sp.parent / "storm" / ("chapter-" + _stem + "-wave2.md")
    if wave2_file.exists():
        t = wave2_file.read_text(encoding="utf-8")
        NL = chr(10)
        inject = NL + "## Wave1攻击波的指控(你要辩护这些)" + NL + NL.join(charges) + NL
        anchor = "### Agent D1"
        if anchor in t:
            t = t.replace(anchor, inject + NL + anchor, 1)
            wave2_file.write_text(t, encoding="utf-8")
            print("  Wave1指控已注入Wave2 prompt(" + str(len(charges)) + "条)")


def cmd_aggregate(target):
    sp = storm_state_path(target)
    if sp.exists():
        # 可观测性: aggregate前备份旧state(重跑storm不再抹掉50agent个体分)
        import shutil as _sh, datetime as _dt
        _hdir = sp.parent / "storm-history"
        _hdir.mkdir(exist_ok=True)
        _sh.copy(sp, _hdir / (sp.stem + "-" + _dt.datetime.now().strftime("%m%d%H%M") + ".json"))

    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化"); return 1
    state = json.loads(sp.read_text(encoding="utf-8"))

    # v2硬门①: 角色覆盖校验——旧state(10角色v1)或角色缺失=覆盖不足,拒绝aggregate(债务)
    _want = all_role_ids()
    for wn, ids in _want.items():
        wdata = state.get("waves", {}).get(wn)
        if not wdata:
            print(f"❌ 角色覆盖不足: Wave{wn}整个缺失(角色表{STORM_ROLE_VERSION})——重新init+全波执行")
            return 1
        _missing = [i for i in ids if i not in wdata["agents"]]
        if _missing:
            print(f"❌ 角色覆盖不足: Wave{wn}缺{','.join(_missing)}(角色表{STORM_ROLE_VERSION})——v1旧审计不算数,重新init+补派")
            return 1
    if state.get("role_version") != STORM_ROLE_VERSION:
        print(f"❌ 角色表版本不符(state={state.get('role_version')} vs {STORM_ROLE_VERSION})——重新init")
        return 1

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
    
    # 盲区017修复: 分波判定——Wave1(原稿)是打回依据,Wave4(修复后)只作参考
    verdict = "放行"
    reasons = []
    
    # W5通胀修复: 任一agent≤3=灾难分,不被均分稀释,直接打回
    for wn, wdata in state["waves"].items():
        for aid, a in wdata["agents"].items():
            if a.get("score") is not None and a["score"] <= 3.0:
                if verdict == "放行":
                    verdict = "打回"
                    reasons.append(f"灾难分: {aid}({a.get('role','?')})={a['score']}≤3——单点一票否决")
    # 规则1(核心): Wave1攻击波均值≥6.0(原稿质量,不可被修复波稀释)
    w1_avg = wave_scores.get("1", 10)
    if w1_avg < 6.0:
        verdict = "打回"
        reasons.append(f"Wave1攻击波(原稿)均分{w1_avg:.1f}<6.0")
    
    # 规则1b: 全部50agent均值(参考,不作打回依据)
    if avg < 7.0:
        reasons.append(f"参考: 总均分{avg:.1f}<7.0")
    
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

    # v2硬门②: 修复迭代闭环——Wave1净问题(评分<6.5)必须逐条修复并被验证>=7.0
    repairs = state.get("repairs", [])
    _rep_map = {}
    for r in repairs:
        if float(r.get("verify", 0)) >= 7.0:
            _rep_map.setdefault(r.get("id"), []).append(r)
    w1_agents = state["waves"].get("1", {}).get("agents", {})
    _unresolved = []
    for aid in sorted(w1_agents.keys()):
        a = w1_agents[aid]
        if a.get("score") is not None and a["score"] < 6.5 and aid not in _rep_map:
            _unresolved.append(f"{aid}({a['role']})={a['score']}")
    if _unresolved:
        verdict = "打回"
        reasons.append(f"净问题未修复迭代到位({len(_unresolved)}条): {'; '.join(_unresolved[:6])}——跑 repair 命令记录修复+验证分,再重跑aggregate")
    if state.get("repair_iters", 0) > 3:
        reasons.append("警告: 修复迭代已超3轮——按修订阶梯应升级整场重写(scene-rewrite/alt-takes换方向),禁第4轮小修")
    
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
    import hashlib as _hf
    state["state_fingerprint"] = _hf.sha1(("|".join(f"{a}:{v.get('score')}" for w in state["waves"].values() for a, v in w["agents"].items()) + str(verdict)).encode()).hexdigest()[:12]
    state["verdict_score"] = round(avg, 1)
    state["verdict_locked"] = True  # 缺陷12: aggregate后锁定(防record改分不重算)
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
    
    # 红队20260919工效批: storm成本透明化(50agent×全目标≈25万字输入/章)
    try:
        _tp = pathlib.Path(target)
        _tsz = _tp.stat().st_size if _tp.exists() else 0
        _nag = len(all_scores)
        _est = (_tsz + 1200) * _nag
        print(f"\n成本估算: {_nag}agent × 目标{_tsz}B ≈ 输入{_est/10000:.1f}万字(5波全跑常态量级;峰章值得,日常章由焦点决定深挖维度)")
    except Exception:
        pass
    return 0 if verdict == "放行" else 1

def cmd_gate(target):
    """pipeline done调用: storm未完成或未放行=拒绝。v2: 角色覆盖不足(v1旧审计)=债务,同样拒绝"""
    sp = storm_state_path(target)
    if not sp.exists():
        return False, "storm未初始化"
    state = json.loads(sp.read_text(encoding="utf-8"))
    if state.get("verdict") is None:
        return False, "storm未aggregate(结果未汇总)"
    # v2硬门①(gate侧复检): 角色表版本+覆盖——旧10角色审计不算数(防绕过aggregate用旧verdict)
    if state.get("role_version") != STORM_ROLE_VERSION:
        return False, (f"storm角色表版本不符(state={state.get('role_version')} vs {STORM_ROLE_VERSION})"
                       f"——v1旧审计已作废,重新init+全波执行(债务清册: backlog)")
    _want = all_role_ids()
    for wn, ids in _want.items():
        _have = state.get("waves", {}).get(wn, {}).get("agents", {})
        _missing = [i for i in ids if i not in _have]
        if _missing:
            return False, f"storm角色覆盖不足: Wave{wn}缺{','.join(_missing)}——重新init+补派全波"
    _blk = state.get("block") or {}
    if _blk.get("章hash"):
        import hashlib as _hb, pathlib as _pb, re as _rb
        _tp = state.get("target")
        if _tp and _pb.Path(_tp).exists():
            if _hb.sha1(_pb.Path(_tp).read_bytes()).hexdigest()[:12] != _blk["章hash"]:
                return False, "块storm盖章已失效(章文在盖章后被修改)——重切分或重审该章"
            _m = _rb.search(r"第(\d+)章", _pb.Path(_tp).stem)
            if _m and not (_blk["起"] <= int(_m.group(1)) <= _blk["止"]):
                return False, "章号越出块区间——盗章盖章"
    if state["verdict"] != "放行":
        reasons = "; ".join(state.get("verdict_reasons", []))
        return False, f"storm判定={state['verdict']}({reasons})"
    return True, f"storm✅({state.get('verdict_score')}分,角色表{STORM_ROLE_VERSION})"




def cmd_repair_file(target, fpath):
    """记录修复迭代批: --file <jsonl> 每行 {"id":"A1","action":"修了什么","verify":8.2}
    verify>=7.0才算该净问题被真实验证修复(<7.0=假修复,aggregate仍打回)"""
    import json as _json
    sp = storm_state_path(target)
    if not sp.exists():
        print("❌ Storm未初始化"); return 1
    state = json.loads(sp.read_text(encoding="utf-8"))
    w1_ids = set(state.get("waves", {}).get("1", {}).get("agents", {}).keys())
    ok = fail = 0
    for l in pathlib.Path(fpath).read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        try:
            r = _json.loads(l)
            if r["id"] not in w1_ids:
                print(f"  [SKIP] {r['id']} 不是Wave1攻击id——修复只针对净问题源"); fail += 1; continue
            state["repairs"].append({"id": r["id"], "action": str(r.get("action", ""))[:300],
                                     "verify": float(r.get("verify", 0)), "verified_by": r.get("verified_by", "G11")})
            ok += 1
        except Exception as e:
            print(f"  [SKIP] 行解析失败: {e}"); fail += 1
    state["repair_iters"] = state.get("repair_iters", 0) + 1
    state["verdict_locked"] = False  # 修复批后解锁,须重跑aggregate重算
    _tmp = sp.with_suffix(".tmp")
    _tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    _tmp.replace(sp)
    print(f"修复批#{state['repair_iters']}: 录入{ok}条 失败{fail}——重跑 aggregate 重算verdict(verify>=7.0的净问题视为已修复)")
    return 0 if fail == 0 else 1


def cmd_backlog(book):
    """债务清册: 全书每章必须有v2全波storm放行——不足者列入 ledgers/storm-backlog.md"""
    book = pathlib.Path(book)
    chapters = sorted(book.glob("text" + "/" + "卷*" + "/" + "第*章.md"))
    if not chapters:
        print("未发现章节文件"); return 1
    debt, ok = [], []
    for ch in chapters:
        st = storm_state_path(ch)
        good = False
        if st.exists():
            try:
                s = json.loads(st.read_text(encoding="utf-8"))
                good = (s.get("verdict") == "放行" and s.get("role_version") == STORM_ROLE_VERSION)
            except Exception:
                good = False
        (ok if good else debt).append(ch)
    print(f"═══ Storm债务清册(角色表{STORM_ROLE_VERSION}) ═══")
    print(f"  已达标: {len(ok)}章  债务: {len(debt)}章")
    for d in debt:
        m2 = re.search(r"第(\d+)章", d.stem)
        p3 = "P0峰章" if m2 and int(m2.group(1)) % 10 == 0 else ("P1近产" if m2 and int(m2.group(1)) >= 16 else "P2存量")
        print(f"  ❌ {d.name} [{p3}]")
    if debt:
        out = book / "ledgers" / "storm-backlog.md"
        out.write_text("# Storm债务清册(v2全波60agent标准)\n\n每章必须全波审计+修复迭代到放行。\n\n- " +
                       "\n- ".join(str(d.relative_to(book)) for d in debt) + "\n", encoding="utf-8")
        print(f"\n  清册落盘: {out}——按章清偿: init→派发全波→repair记录修复→aggregate→gate")
    return 0


def cmd_selftest():
    """引擎自测: 在/tmp合成书里走完 init→record→repair→aggregate→gate 全链断言"""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        book = pathlib.Path(td) / "t"
        chp = book / "text" / "卷1"
        chp.mkdir(parents=True)
        ch = chp / "第001章.md"
        ch.write_text("#001 测试\n" + "他推门进来。" * 200, encoding="utf-8")
        def _run(*a):
            # target紧跟子命令,选项随后(record --file 的target必须在前)
            return subprocess.run([sys.executable, str(ROOT / "tools" / "storm_orchestrate.py")] + list(a),
                                  capture_output=True, text=True)
        import subprocess
        T = str(ch)
        r = _run("init", T); assert r.returncode == 0, r.stdout + r.stderr
        # 覆盖不足gate: 未record须拒
        r = _run("gate", T); assert r.returncode != 0, "空state应拒"
        # 全量record通过
        rows = []
        for wn in ("1", "2", "3", "4", "5"):
            for aid in all_role_ids()[wn]:
                rows.append({"id": aid, "score": 7.5, "issue": "无"})
        f = pathlib.Path(td) / "all.jsonl"
        f.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows), encoding="utf-8")
        r = _run("record", T, "--file", str(f)); assert r.returncode == 0, r.stdout[-500:]
        r = _run("aggregate", T); assert r.returncode == 0, "全7.5应放行: " + r.stdout[-500:]
        r = _run("gate", T); assert r.returncode == 0, r.stdout
        # 净问题打回→repair→重算放行
        _run("init", T)  # 重置
        rows = []
        for wn in ("1", "2", "3", "4", "5"):
            for aid in all_role_ids()[wn]:
                sc, iss = (5.0, "时间线穿帮") if (wn == "1" and aid == "A3") else (7.5, "无")
                rows.append({"id": aid, "score": sc, "issue": iss})
        f.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows), encoding="utf-8")
        _run("record", T, "--file", str(f))
        r = _run("aggregate", T); assert r.returncode != 0, "净问题未修复应打回"
        rf = pathlib.Path(td) / "rep.jsonl"
        rf.write_text(json.dumps({"id": "A3", "action": "修时序", "verify": 8.0}, ensure_ascii=False), encoding="utf-8")
        r = _run("repair", T, "--file", str(rf)); assert r.returncode == 0, r.stdout
        r = _run("aggregate", T); assert r.returncode == 0, "修复验证后应放行: " + r.stdout[-500:]
        # 假修复(verify<7)仍打回
        _run("init", T)
        _run("record", T, "--file", str(f))
        rf.write_text(json.dumps({"id": "A3", "action": "只声明没修", "verify": 6.0}, ensure_ascii=False), encoding="utf-8")
        _run("repair", T, "--file", str(rf))
        r = _run("aggregate", T); assert r.returncode != 0, "假修复应打回"
    print("✅ selftest 5项断言全过: 覆盖不足拒/全绿放行/净问题打回/修复验证放行/假修复打回")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    
    if cmd == "init" and len(sys.argv) > 2:
        return cmd_init(pathlib.Path(sys.argv[2]))
    elif cmd == "status" and len(sys.argv) > 2:
        return cmd_status(pathlib.Path(sys.argv[2]))
    elif cmd == "record" and "--file" in sys.argv:
        return cmd_record_file(pathlib.Path(sys.argv[2]), sys.argv[sys.argv.index("--file") + 1])
    elif cmd == "record" and len(sys.argv) > 5:
        return cmd_record(pathlib.Path(sys.argv[2]), sys.argv[3], float(sys.argv[4]), sys.argv[5])
    elif cmd == "aggregate" and len(sys.argv) > 2:
        return cmd_aggregate(pathlib.Path(sys.argv[2]))
    elif cmd == "gate" and len(sys.argv) > 2:
        ok, msg = cmd_gate(pathlib.Path(sys.argv[2]))
        print(("✅ " if ok else "❌ ") + msg)
        return 0 if ok else 1
    elif cmd == "repair" and "--file" in sys.argv:
        return cmd_repair_file(pathlib.Path(sys.argv[2]), sys.argv[sys.argv.index("--file") + 1])
    elif cmd == "backlog" and len(sys.argv) > 2:
        return cmd_backlog(sys.argv[2])
    elif cmd == "selftest":
        return cmd_selftest()
    else:
        print(__doc__); return 2

if __name__ == "__main__":
    sys.exit(main())

