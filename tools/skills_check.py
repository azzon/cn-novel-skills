#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills_check.py 技能库体检(调用正确性的确定性部分)
检查:
  1) 结构五件:frontmatter规范/name=目录名/闸门/NextStep/evals/溯源
  2) 路由可达:每个叶技能在其域入口(父目录SKILL.md)中被提及(路由表覆盖)
  3) 重复检测:叶名唯一;description首8字不重复
  4) 死引用:NEXT-SKILL 目标存在
用法:python3 tools/skills_check.py   (退出码0=全过)
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "skills"

def leaves():
    out = []
    for f in sorted(ROOT.glob("**/SKILL.md")):
        out.append(f)
    return out

def main():
    files = leaves()
    names = [f.parent.name for f in files]
    entry_files = {f.parent.name: f for f in files if f.parent.parent == ROOT}
    problems = []

    # 1 结构五件
    for f in files:
        s = f.read_text(encoding="utf-8")
        if not re.match(r"^---\nname: [a-z][a-z0-9-]*\ndescription: .+?---", s, re.S):
            problems.append(f"结构: {f} frontmatter不规范")
        m = re.match(r"^---\nname: ([a-z0-9-]+)", s)
        if not m or m.group(1) != f.parent.name:
            problems.append(f"结构: {f} name≠目录名")
        for key, pat in [("闸门", "闸门|总闸"), ("NextStep", "Next Step|NEXT-SKILL"), ("evals", "evals"), ("溯源", "溯源|docs/")]:
            if not re.search(pat, s):
                problems.append(f"结构: {f} 缺{key}")

    # 2 路由可达(叶须被域入口提及;域根目录的SKILL.md即入口本身,跳过)
    for f in files:
        if f.parent.parent == ROOT:
            continue
        domain = f.parent.parent.name
        if domain not in entry_files:
            problems.append(f"路由: {f.parent.name} 无域入口(域={domain})")
            continue
        entry_s = entry_files[domain].read_text(encoding="utf-8")
        if f.parent.name not in entry_s:
            problems.append(f"路由: {domain}入口未提及叶 {f.parent.name}")

    # 3 重复
    dup = {n for n in names if names.count(n) > 1}
    if dup: problems.append(f"重复叶名: {dup}")
    descs = {}
    for f in files:
        m = re.search(r"description: (.+)", f.read_text(encoding="utf-8"))
        if m:
            head = m.group(1)[:8]
            descs.setdefault(head, []).append(f.parent.name)
    for head, ns in descs.items():
        if len(ns) > 1:
            problems.append(f"description开头重复({head}): {ns}")

    # 4 死引用
    allnames = set(names)
    for f in files:
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"(?:NEXT-SKILL[^\n]*?|调用\s*`?)(?:novel:)?(?:ideate|write|revise|audit|ops)?:([a-z-]+)", s):
            if m.group(1) not in allnames:
                problems.append(f"死引用: {f.parent.name} -> {m.group(1)}")

    print(f"技能总数: {len(files)}")
    if problems:
        print(f"问题 {len(problems)} 条:")
        for p in problems: print(" -", p)
        sys.exit(1)
    # 4.5 docs↔skill时间戳漂移(红队3:docs改了但skill没跑sync)
    for f in files:
        s = f.read_text(encoding="utf-8")
        for dm in re.finditer(r"docs/(\d+)", s):
            docfile = ROOT.parent / "docs" / f"{dm.group(1)}-"
            matches = list((ROOT.parent / "docs").glob(f"{dm.group(1)}-*.md"))
            if matches and matches[0].stat().st_mtime > f.stat().st_mtime + 60:
                problems.append(f"漂移风险: {f.parent.name} 引用docs/{dm.group(1)} 但docs更新后未跑skill-sync")
                break

    # 5 源库↔运行时一致性
    zdir = ROOT.parent / ".zcode" / "skills"
    if zdir.exists():
        for f in files:
            zfile = zdir / f.parent.name / "SKILL.md"
            if zfile.exists():
                if f.read_text(encoding="utf-8").strip() != zfile.read_text(encoding="utf-8").strip():
                    problems.append(f"漂移: {f.parent.name} 源库与.zcode副本不一致——重跑install_skills.sh")

    if not problems:
        print("体检全过:结构五件/路由可达/无重复/无死引用/源库与运行时一致")

if __name__ == "__main__":
    main()
