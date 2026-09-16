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
BASELINE = ROOT / "evals_baseline.json"   # 主书基线; 书根基线=<书根>/evals_baseline.json(多书隔离)


def _book(argv):
    """解析可选书根参数: evals.py record|check|show [书根]"""
    args = [a for a in argv[2:] if not a.startswith("-")]
    if args:
        root = pathlib.Path(args[0]).resolve()
        return root, root / "evals_baseline.json"
    return ROOT, BASELINE


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


def collect(book_root=ROOT):
    data = {"chapters": {}, "structure": {}, "skills": "", "total_cjk": 0}
    total = 0
    if book_root == ROOT:
        files = chapter_files()
    else:
        files = sorted(book_root.glob("text/卷*/第*.md"))
    for f in files:
        m = check_metrics(f)
        m.pop("file", None)
        data["chapters"][f.name] = m
        total += m.get("cjk", 0)
    data["total_cjk"] = total

    sc_cmd = [sys.executable, "tools/structure_check.py"]
    if book_root != ROOT:
        sc_cmd.append(str(book_root / "text"))
    sc = run(sc_cmd)   # 书根模式传书根text(审计-32:新书基线结构分布曾错读主书)
    dist = {}
    for line in sc.stdout.splitlines():
        mm = re.match(r"\s+(\S+): (\d+)章 \((\d+)%\)", line)
        if mm:
            dist[mm.group(1)] = int(mm.group(3))
    data["structure"] = dist
    data["structure_raw"] = sc.stdout

    sk = run([sys.executable, "tools/skills_check.py"])
    data["skills"] = "OK" if sk.returncode == 0 else "FAIL:" + sk.stdout[-200:]

    # 质量分并入基线(防"越写越差": 质量均分跌幅>5分=回归)
    qs_cmd = [sys.executable, "tools/quality_score.py", "--json"]
    if book_root != ROOT:
        qs_cmd.append(str(book_root))
    qs = run(qs_cmd)
    try:
        rows = json.loads(qs.stdout)
        scores = {pathlib.Path(r["file"]).name: r["score"] for r in rows if r.get("score") is not None}
        data["quality_scores"] = scores
        data["quality_avg"] = round(sum(scores.values()) / len(scores), 1) if scores else None
    except (json.JSONDecodeError, KeyError):
        data["quality_scores"], data["quality_avg"] = {}, None

    # 工具自测套件(历次事故靶测固化: cn2num/引号三态/声口归属/书根判定/数值比对)
    st = run([sys.executable, "tools/self_test.py"])
    data["self_test"] = "OK" if st.returncode == 0 else "FAIL:" + st.stdout[-200:]

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
    # 冒烟章写进存在的卷目录; 空库时目录也没了→mkdir(parents)兜底(空库清理后曾 FileNotFoundError)
    smoke_dir = (ROOT / "text" / "卷1")
    smoke_dir.mkdir(parents=True, exist_ok=True)
    tmp = smoke_dir / "第999章.md"
    tmp.write_text("第九十九章 冒烟\n\n“马哥，早。”王大龙把车支好。\n\n他把货搬下来，一块一块码齐。\n", encoding="utf-8")
    try:
        g = run([sys.executable, "tools/gate_chapter.py", "new", str(tmp)])
        data["gate_new_smoke"] = "CRASH" if "Traceback" in g.stderr or "Traceback" in g.stdout else "OK"
    finally:
        tmp.unlink(missing_ok=True)

    # bundle冒烟: 注入项不得出现"已裁剪"(注入预算健康)
    _ch = sorted((ROOT.glob("text/卷*/第*.md")), key=lambda x: x.stat().st_mtime)
    _n = max((int(m.group(1)) for f in _ch for m in [__import__("re").search(r"第(\d+)章", f.name)] if m), default=2)
    b = run([sys.executable, "tools/pipeline.py", "bundle", str(_n)])   # 红队20260915: 死写2=永远测开卷注入
    data["bundle_cropped"] = len(re.findall(r"已裁剪", b.stdout))
    return data


def cmd_record():
    book, baseline = _book(sys.argv)
    data = collect(book)
    baseline.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tag = "主书" if book == ROOT else f"书根{book.name}"
    print(f"[{tag}]基线已记录: {len(data['chapters'])}章 / {data['total_cjk']}字 / 质量均分{data.get('quality_avg')} / skills={data['skills'][:15]} 自测={str(data.get('self_test','?'))[:15]}")
    return 0


def cmd_check():
    book, baseline = _book(sys.argv)
    if not baseline.exists():
        print("无基线。先运行: python3 tools/evals.py record [书根]")
        return 2
    base = json.loads(baseline.read_text(encoding="utf-8"))
    cur = collect(book)
    # 磨刀十六批: 增量模式——基线章抽头尾各3章复验(签名级),新章全验;全量仅record时跑(千章O(N)→抽检)
    _bn = sorted(base.get("chapters", {}), key=lambda x: int(re.search(r"\d+", x).group()) if re.search(r"\d+", x) else 0)
    if len(_bn) > 12 and "--full" not in sys.argv:
        _sample = set(_bn[:3] + _bn[-3:])
        _new = set(cur["chapters"]) - set(base.get("chapters", {}))
        cur = dict(cur)
        cur["chapters"] = {k: v for k, v in cur["chapters"].items() if k in _sample or k in _new}
        base = dict(base)
        base["chapters"] = {k: v for k, v in base.get("chapters", {}).items() if k in _sample or k in _new}
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

    for k, old_pct in base.get("structure", {}).items():
        new_pct = cur["structure"].get(k, 0)
        if new_pct > old_pct + 10:
            regressions.append(f"结构分布恶化[{k}]: {old_pct}%→{new_pct}%")

    base_avg = base.get("quality_avg")
    cur_avg = cur.get("quality_avg")
    if base_avg is not None and cur_avg is not None and base_avg - cur_avg > 5:
        regressions.append(f"质量均分下滑: {base_avg}→{cur_avg}(>5分,越写越差警报)")
    base_scores = base.get("quality_scores", {})
    cur_scores = cur.get("quality_scores", {})
    for name, old_s in base_scores.items():
        new_s = cur_scores.get(name)
        if new_s is not None and new_s is not None and old_s - new_s > 8:
            regressions.append(f"单章质量骤降[{name}]: {old_s}→{new_s}(>8分)")

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
