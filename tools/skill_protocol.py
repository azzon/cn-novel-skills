#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_protocol.py 技能挂载清单与执行率审计(磨刀第十二批: ch002实战技能执行率仅33%——
分析头头是道,生产全不用。把"凭记忆"变成"按单执行,机器可查")

两个模式:
  list <章号>   输出本章生产全程的技能挂载清单(从workflows/chapter_production.yaml解析),
                并初始化 ledgers/技能执行记录.md 打勾表
  audit <章号>  审计技能执行记录: 勾选率+漏项清单(done验收配套)

用法: python3 tools/skill_protocol.py list|audit <章号> [--book 书根]
"""
import re, sys, pathlib, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent

try:
    import yaml
except ImportError:
    yaml = None

WF = ROOT / "workflows" / "chapter_production.yaml"


def skill_file(skill_name):
    """技能名 → SKILL.md 路径(域扫描)"""
    if not skill_name or skill_name.startswith(("python3", "bash", "git", "根据")):
        return None
    hits = list(ROOT.glob(f"skills/**/{skill_name}/SKILL.md"))
    return hits[0] if hits else None


def steps():
    if yaml is None:
        print("需要PyYAML")
        sys.exit(2)
    wf = yaml.safe_load(WF.read_text(encoding="utf-8"))
    out = []
    for ph in wf["phases"].values():
        for st in ph.get("steps", []):
            out.append((st["id"], st.get("name", ""), st.get("type", ""), st.get("skill", "")))
    return out


def cmd_list(n, book):
    rec = book / "ledgers" / "技能执行记录.md"
    rows = ["# 技能执行记录（第%03d章）" % n, "",
            f"> 生成: {datetime.date.today()} 按workflows/chapter_production.yaml。铁律一: 没有被执行的技能等于不存在。",
            "> 每步执行前先读SKILL.md全文;完成后把 [ ] 改 [x] 并附一行产物说明。跳过=产物无效。", ""]
    for sid, name, typ, skill in steps():
        f = skill_file(str(skill))
        if typ == "script":
            rows.append(f"- [x] {sid}({name}) [script步骤:按script字段真实执行]")
        elif f:
            rows.append(f"- [ ] {sid}({name}) 技能: {skill} → {f.relative_to(ROOT)}")
        else:
            rows.append(f"- [ ] {sid}({name}) 技能: {skill or '(无)'}")
    book.mkdir(parents=True, exist_ok=True) if not book.exists() else None
    (book / "ledgers").mkdir(parents=True, exist_ok=True)
    rec.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"技能挂载清单已生成: {rec}")
    for r in rows:
        if r.startswith("- "):
            print(" ", r[:100])
    return 0


def cmd_audit(n, book):
    rec = book / "ledgers" / "技能执行记录.md"
    if not rec.exists():
        print(f"[FAIL] 无技能执行记录: {rec}——先跑 skill_protocol.py list {n}")
        return 1
    total = done = 0
    missed = []
    for line in rec.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("- ["):
            continue
        total += 1
        if line.startswith("- [x]"):
            done += 1
        else:
            missed.append(line[:90])
    rate = done / total * 100 if total else 0
    print(f"技能执行率: {done}/{total} ({rate:.0f}%)")
    for m in missed:
        print(f"  [漏] {m}")
    if rate < 100:
        print("  [WARN] 执行率<100%——跳过的步骤产物按协议无效,done验收视角降级")
        return 2
    print("  技能执行记录全勾")
    return 0


def main():
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ("list", "audit"):
        print(__doc__)
        return 2
    mode = args[0]
    n = int(re.sub(r"\D", "", args[1]) or 0)
    book = ROOT
    if "--book" in args:
        book = ROOT / args[args.index("--book") + 1]
    return cmd_list(n, book) if mode == "list" else cmd_audit(n, book)


if __name__ == "__main__":
    sys.exit(main())
