#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skills_check.py 技能库体检 v3(调用正确性的确定性部分)
硬门(exit 1):
  1) frontmatter规范: ---\\nname: <与目录同名>\\ndescription: 非空
  2) 路由可达: 每个叶技能被其域入口SKILL.md提及
  3) 叶名唯一; description首8字不重复
  4) NEXT-SKILL死引用
  5) 三树一致性v3(全量): 域入口与叶全部比对;运行时孤儿(含域入口篡改)即FAIL;
     .zcode缺树=FAIL,.claude缺树=FAIL(v4升级,audits/13攻击6c)
软警告(仅打印):
  - 缺闸门/NextStep/evals/溯源 章节约定件; docs/NN引用无对应文件
用法: python3 tools/skills_check.py   (退出码0=硬门全过)
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "skills"
# (运行时树, 结构类型, 缺树是否硬FAIL)
RUNTIMES = [
    (ROOT / ".zcode" / "skills", "flat", True),
    (ROOT / ".claude" / "skills", "domain", True),
]

def main():
    files = sorted(SRC.glob("**/SKILL.md"))
    entry_files = {f.parent.name: f for f in files if f.parent.parent == SRC}
    problems, warnings = [], []

    # 1 frontmatter(硬) + 约定件(软)
    for f in files:
        s = f.read_text(encoding="utf-8-sig")
        m = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: (\S.*)\n", s)
        if not m:
            problems.append(f"结构: {f.relative_to(SRC)} frontmatter须为name:+description:且name小写连字符")
        elif m.group(1) != f.parent.name:
            problems.append(f"结构: {f.parent.name} name≠目录名")
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
        if f.parent.name not in entry_files[domain].read_text(encoding="utf-8-sig"):
            problems.append(f"路由: {domain}入口未提及叶 {f.parent.name}")

    # 3 重复(硬)
    names = [f.parent.name for f in files]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        problems.append(f"重复叶名: {dup}")
    descs = {}
    for f in files:
        m = re.search(r"^description: (\S.{7})", f.read_text(encoding="utf-8-sig"), re.M)
        if m:
            descs.setdefault(m.group(1), []).append(f.parent.name)
    for head, ns in descs.items():
        if len(ns) > 1:
            problems.append(f"description开头重复({head}): {ns}")

    # 4 NEXT-SKILL死引用(硬)
    allnames = set(names)
    for f in files:
        s = f.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"NEXT-SKILL[^\n]*?([a-z][a-z0-9-]+)\s*$", s, re.M):
            if m.group(1) not in allnames:
                problems.append(f"死引用: {f.parent.name} -> {m.group(1)}")

    # 5 docs/NN引用文件存在性(软)
    docs_dir = ROOT / "docs"
    for f in files:
        _body = f.read_text(encoding="utf-8-sig")
        # 红队docs一致性: 无前缀简写(NN合规/NN红队/NN迭代史)曾系统性绕过死引用检测
        for dm in re.finditer(r"docs/(\d+)|(?:^|[\s·/])(\d{2})(?=合规|红队|迭代|规格|对齐表)", _body):
            _num = dm.group(1) or dm.group(2)
            if docs_dir.exists() and not list(docs_dir.glob(f"{_num}-*.md")):
                warnings.append(f"docs引用: {f.parent.name} 引用docs/{_num} 无对应文件")
                break

    # 6 三树一致性v3(硬,全量: 叶+域入口;audits/13攻击6b/6c)
    # 源侧期望集合: {运行时相对路径: 源文件}
    leaf_domain = {f.parent.name: f.parent.parent.name for f in files if f.parent.parent != SRC}
    def expected_paths(struct):
        out = {}
        for f in files:
            if f.parent.parent == SRC:          # 域入口
                out[f"{f.parent.name}/SKILL.md"] = f
            elif struct == "domain":            # .claude域结构: <域>/<叶>/SKILL.md
                out[f"{leaf_domain[f.parent.name]}/{f.parent.name}/SKILL.md"] = f
            else:                               # .zcode扁平: <叶>/SKILL.md
                out[f"{f.parent.name}/SKILL.md"] = f
        return out

    for rt, struct, hard in RUNTIMES:
        tag = str(rt.relative_to(ROOT))
        if not rt.exists():
            msg = f"运行时缺失: {tag}(整树消失——安装或恢复;此为硬门)"
            (problems if hard else warnings).append(msg)
            continue
        exp = expected_paths(struct)
        rt_files = {str(p.relative_to(rt)): p for p in rt.glob("**/SKILL.md")}
        for rel, srcf in sorted(exp.items()):
            rtf = rt_files.get(rel)
            if rtf is None:
                problems.append(f"漂移[{tag}]: {rel} 源库有、运行时缺——重跑install_skills.sh")
            elif srcf.read_text(encoding="utf-8-sig").strip() != rtf.read_text(encoding="utf-8-sig").strip():
                problems.append(f"漂移[{tag}]: {rel} 内容与源库不一致——重跑install_skills.sh")
        for rel in sorted(set(rt_files) - set(exp)):
            problems.append(f"漂移[{tag}]: {rel} 运行时孤儿(源库无此SKILL.md)——回灌skills/或删除")

    print(f"技能总数(源库): {len(files)}")
    for w in warnings:
        print(f"  [WARN] {w}")
    if problems:
        print(f"问题 {len(problems)} 条(硬门):")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("体检全过:frontmatter/路由可达/无重复/无死引用/三树全量一致")

if __name__ == "__main__":
    main()
