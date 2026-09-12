#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""evals.py 全系统回归测试器(大审计-11遗留P1: evals可执行化)

长期运行的质量底线保障:
  record  — 跑全部门,记录基线 evals_baseline.json
  check   — 重跑并与基线diff,报告回归(任一章状态恶化/新FAIL/结构分布恶化)
  show    — 显示当前基线摘要

用法: python3 tools/evals.py record|check|show
铁律: 手稿是唯一权威;本工具是派生度量,只报告不修改。
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BASELINE = ROOT / "evals_baseline.json"


def run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)


def chapter_files():
    return sorted(ROOT.glob("text/卷*/第*章.md"))


def check_metrics(fp):
    """跑单章check.py,解析METRICS行"""
    r = run([sys.executable, "tools/check.py", "--modern", "--metrics", "--scene" if False else fp])
    if isinstance(fp, pathlib.Path):
        fp = str(fp)
    m = None
    status_line = ""
    for line in r.stdout.splitlines():
        if line.startswith("METRICS "):
            try:
                m = json.loads(line[len("METRICS "):])
            except json.JSONDecodeError:
                pass
        elif line.startswith("汇总:"):
            status_line = line
    fails = 0
    mm = re.search(r"FAIL (\d+)章", status_line)
    if mm:
        fails = int(mm.group(1))
    if m is None:
        m = {"file": fp, "cjk": 0, "fails": fails, "warns": 0}
    m["fails"] = fails
    return m


def collect():
    data = {"chapters": {}, "structure": {}, "skills": "", "total_cjk": 0}
    total = 0
    for f in chapter_files():
        m = check_metrics(f)
        m.pop("file", None)
        data["chapters"][f.name] = m
        total += m.get("cjk", 0)
    data["total_cjk"] = total

    sc = run([sys.executable, "tools/structure_check.py"])
    dist = {}
    for line in sc.stdout.splitlines():
        mm = re.match(r"\s+(\S+): (\d+)章 \((\d+)%\)", line)
        if mm:
            dist[mm.group(1)] = int(mm.group(3))
    data["structure"] = dist
    data["structure_raw"] = sc.stdout

    sk = run([sys.executable, "tools/skills_check.py"])
    data["skills"] = "OK" if sk.returncode == 0 else "FAIL:" + sk.stdout[-200:]

    # 全工具语法门(防坏提交: 本项目hook不查py语法,曾发生PREFIX断裂被提交)
    import py_compile
    syn = "OK"
    for tool in ["pipeline.py", "check.py", "gate_chapter.py", "structure_check.py", "skills_check.py", "evals.py"]:
        try:
            py_compile.compile(str(ROOT / "tools" / tool), doraise=True)
        except py_compile.PyCompileError as e:
            syn = f"FAIL:{tool}:{e}"
            break
    data["syntax"] = syn

    rec = run([sys.executable, "tools/gate_chapter.py", "--recompute"])
    data["recompute"] = rec.stdout.strip().splitlines()[-1] if rec.stdout else "FAIL"

    # gate new模式冒烟: tmp新章走全部门,任何崩溃(Traceback/NameError)都算回归
    # (大审计-20 P0: G8参数错位曾致新章必崩,而evals不覆盖gate new故漏检)
    tmp = ROOT / "text" / "卷1" / "第999章.md"
    tmp.write_text("第九十九章 冒烟\n\n“马哥，早。”王大龙把车支好。\n\n他把货搬下来，一块一块码齐。\n", encoding="utf-8")
    try:
        g = run([sys.executable, "tools/gate_chapter.py", "new", str(tmp)])
        data["gate_new_smoke"] = "CRASH" if "Traceback" in g.stderr or "Traceback" in g.stdout else "OK"
    finally:
        tmp.unlink(missing_ok=True)

    # bundle冒烟: 注入项不得出现"已裁剪"(注入预算健康)
    b = run([sys.executable, "tools/pipeline.py", "bundle", "2"])
    data["bundle_cropped"] = len(re.findall(r"已裁剪", b.stdout))
    return data


def cmd_record():
    data = collect()
    BASELINE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"基线已记录: {len(data['chapters'])}章 / {data['total_cjk']}字 / 结构{data['structure']} / skills={data['skills'][:20]}")
    return 0


def cmd_check():
    if not BASELINE.exists():
        print("无基线。先运行: python3 tools/evals.py record")
        return 2
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    cur = collect()
    regressions = []

    for name, old in base["chapters"].items():
        new = cur["chapters"].get(name)
        if new is None:
            regressions.append(f"{name}: 章节消失")
            continue
        if new.get("fails", 0) > old.get("fails", 0):
            regressions.append(f"{name}: FAIL {old.get('fails')}→{new.get('fails')}")
        if new.get("cjk", 0) < old.get("cjk", 0) * 0.9:
            regressions.append(f"{name}: 字数骤降 {old.get('cjk')}→{new.get('cjk')}")

    for k, old_pct in base["structure"].items():
        new_pct = cur["structure"].get(k, 0)
        if new_pct > old_pct + 10:
            regressions.append(f"结构分布恶化[{k}]: {old_pct}%→{new_pct}%")

    if base["skills"].startswith("OK") and cur["skills"].startswith("FAIL"):
        regressions.append(f"skills_check回归: {cur['skills'][:120]}")

    if base.get("gate_new_smoke") == "OK" and cur.get("gate_new_smoke") != "OK":
        regressions.append("gate new模式冒烟崩溃(门代码存在未捕获异常)")
    if base.get("syntax") == "OK" and cur.get("syntax") != "OK":
        regressions.append(f"工具语法门: {cur['syntax'][:140]}")
    if cur.get("bundle_cropped", 0) > base.get("bundle_cropped", 0):
        regressions.append(f"bundle注入出现新裁剪: {cur['bundle_cropped']}处(注入预算被突破)")

    if regressions:
        print(f"回归 {len(regressions)} 项:")
        for x in regressions:
            print(f"  [REGRESS] {x}")
        return 1
    print(f"无回归: {len(cur['chapters'])}章/{cur['total_cjk']}字, 与基线一致")
    return 0


def cmd_show():
    if not BASELINE.exists():
        print("无基线")
        return 2
    b = json.loads(BASELINE.read_text(encoding="utf-8"))
    print(f"基线: {len(b['chapters'])}章 / {b['total_cjk']}字")
    print(f"结构: {b['structure']}")
    print(f"skills: {b['skills'][:60]}")
    bad = [n for n, m in b["chapters"].items() if m.get("fails", 0) > 0]
    print(f"FAIL章: {bad if bad else '无'}")
    return 0


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("record", "check", "show"):
        print(__doc__)
        return 2
    return {"record": cmd_record, "check": cmd_check, "show": cmd_show}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
