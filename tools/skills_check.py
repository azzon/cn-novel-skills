#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills_check.py 技能库体检 v2(调用正确性的确定性部分)
硬门(exit 1):
  1) frontmatter规范: ---\\nname: <与目录同名>\\ndescription: 非空
  2) 路由可达: 每个叶技能被其域入口SKILL.md提及
  3) 叶名唯一; description首8字不重复
  4) NEXT-SKILL死引用
  5) 三树一致性: skills/(SSOT) ↔ .zcode/skills/ ↔ .claude/skills/ 逐叶比对
软警告(仅打印,不阻塞):
  - 缺闸门/NextStep/evals/溯源 章节约定件
  - docs/NN 引用无对应文件
修复史: v1的两个bug——第5节(漂移检测)写在exit(1)之后永不执行;漂移时仍exit 0(见 audits/03)。
用法: python3 tools/skills_check.py   (退出码0=硬门全过)
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "skills"
RUNTIMES = [ROOT / ".zcode" / "skills", ROOT / ".claude" / "skills"]

def leaves(root):
    return sorted(root.glob("**/SKILL.md"))

def main():
    files = leaves(SRC)
    names = [f.parent.name for f in files]
    entry_files = {f.parent.name: f for f in files if f.parent.parent == SRC}
    problems, warnings = [], []

    # 1 frontmatter(硬)
    for f in files:
        s = f.read_text(encoding="utf-8")
        m = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: (\S.*)\n", s)
        if not m:
            problems.append(f"结构: {f.relative_to(SRC)} frontmatter须为name:+description:且name小写连字符")
        elif m.group(1) != f.parent.name:
            problems.append(f"结构: {f.parent.name} name≠目录名")
        # 软: 章节约定件
        for key, pat in [("闸门", r"闸门|总闸"), ("NextStep", r"Next Step|NEXT-SKILL"),
                         ("evals", r"evals"), ("溯源", r"溯源|docs/")]:
            if not re.search(pat, s):
                warnings.append(f"约定: {f.parent.name} 缺「{key}」件")

    # 2 路由可达(硬)
    for f in files:
        if f.parent.parent == SRC:
            continue
        domain = f.parent.parent.name
        if domain not in entry_files:
            problems.append(f"路由: {f.parent.name} 无域入口(域={domain})")
            continue
        if f.parent.name not in entry_files[domain].read_text(encoding="utf-8"):
            problems.append(f"路由: {domain}入口未提及叶 {f.parent.name}")

    # 3 重复(硬)
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        problems.append(f"重复叶名: {dup}")
    descs = {}
    for f in files:
        m = re.search(r"^description: (\S.{7})", f.read_text(encoding="utf-8"), re.M)
        if m:
            descs.setdefault(m.group(1), []).append(f.parent.name)
    for head, ns in descs.items():
        if len(ns) > 1:
            problems.append(f"description开头重复({head}): {ns}")

    # 4 NEXT-SKILL死引用(硬)
    allnames = set(names) | set(entry_files)
    for f in files:
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r"NEXT-SKILL[^\n]*?([a-z][a-z0-9-]+)\s*$", s, re.M):
            if m.group(1) not in allnames:
                problems.append(f"死引用: {f.parent.name} -> {m.group(1)}")

    # 5 docs/NN引用文件存在性(软)
    docs_dir = ROOT / "docs"
    for f in files:
        for dm in re.finditer(r"docs/(\d+)", f.read_text(encoding="utf-8")):
            if docs_dir.exists() and not list(docs_dir.glob(f"{dm.group(1)}-*.md")):
                warnings.append(f"docs引用: {f.parent.name} 引用docs/{dm.group(1)} 无对应文件")
                break

    # 6 三树一致性(硬)——v1此处逻辑写在exit之后,永不执行(audits/03 P0)
    for rt in RUNTIMES:
        tag = str(rt.relative_to(ROOT))
        if not rt.exists():
            warnings.append(f"运行时缺失: {tag}(若该端不再使用可忽略)")
            continue
        src_map = {f.parent.name: f for f in files}
        rt_leaves = {p.parent.name for p in leaves(rt) if p.parent.name not in ("ideate", "write", "revise", "audit", "ops")}
        # 仅源有 → 该端装漏
        for n in sorted(set(src_map) - rt_leaves):
            # 域入口目录在运行时以<domain>/SKILL.md形式存在,不算缺
            if not (rt / n).exists():
                problems.append(f"漂移[{tag}]: 叶 {n} 源库有、运行时缺——重跑install_skills.sh")
        # 仅运行时有 → 孤儿(源库没有=不可Install还原)
        for n in sorted(rt_leaves - set(src_map)):
            if not (rt / n / "SKILL.md").exists():
                continue
            problems.append(f"漂移[{tag}]: 叶 {n} 仅运行时有、源库缺——回灌skills/后重装")
        # 两边都有但内容不同
        for n in sorted(set(src_map) & rt_leaves):
            a = src_map[n]
            b = rt / n / "SKILL.md"
            if b.exists() and a.read_text(encoding="utf-8").strip() != b.read_text(encoding="utf-8").strip():
                problems.append(f"漂移[{tag}]: {n} 源库与运行时不一致——重跑install_skills.sh")

    print(f"技能总数(源库): {len(files)}")
    for w in warnings:
        print(f"  [WARN] {w}")
    if problems:
        print(f"问题 {len(problems)} 条(硬门):")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("体检全过:frontmatter/路由可达/无重复/无死引用/三树一致")

if __name__ == "__main__":
    main()
