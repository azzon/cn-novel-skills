#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_protocol.py 技能挂载清单与执行率审计(磨刀第十二批: ch002实战技能执行率仅33%——
分析头头是道,生产全不用。把"凭记忆"变成"按单执行,机器可查")

两个模式:
  list <章号>   输出本章技能挂载清单并初始化 ledgers/技能执行记录.md 打勾表
  audit <章号>  审计技能执行记录: 勾选率+漏项清单(done验收配套)
  gen card <章号> [--vol N] [--book 书根]    生成场景卡骨架(技能编译产物,填空式)
  gen coldread <章号> [--book 书根]          生成冷读报告骨架(六项量规+锚定)

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
    wf = yaml.safe_load(pathlib.Path(WF).read_text(encoding="utf-8"))
    out = []
    for ph in wf["phases"].values():
        for st in ph.get("steps", []):
            out.append((st["id"], st.get("name", ""), st.get("type", ""), st.get("skill", "")))
    return out


def cmd_list(n, book, wf_path=None):
    global WF
    if wf_path:
        WF = pathlib.Path(wf_path)
    rec = book / "ledgers" / "技能执行记录.md"
    rows = ["# 技能执行记录（第%03d章）" % n, "",
            f"> 生成: {datetime.date.today()} 按workflows/chapter_production.yaml。铁律一: 没有被执行的技能等于不存在。",
            "> 每步执行前先读SKILL.md全文;完成后把 [ ] 改 [x] 并附一行产物说明。跳过=产物无效。", ""]
    for sid, name, typ, skill in steps():
        f = skill_file(str(skill))
        if typ == "script":
            rows.append(f"- [ ] {sid}({name}) [script步骤:真实执行命令后勾——预勾=审计失真(磨刀十三批H2)]")
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


CARD_SKELETON = """# 场景卡 卷{vol}-第{n:03d}章（标题）
<!-- generated-by:skill_protocol gen-card —— 本卡由scene-card技能骨架生成,填空式作业;占位符未清=骨架卡(注释自身禁含占位字样,否则填好的卡过不了骨架门),scene-draft拒工 -->
- **开场型**: （四选一:对话直入|动作直入|异常直入|判断句;须与前两章错型）
- **场景型**: （单元型+压弹级）
- **戏剧问题**: （一个问句）
- **阻碍**: （具体的阻力量:谁/什么制度/什么短缺）
- **冲突源**: （谁与谁的利益相撞）
- **代价**: （主角本章实付什么:钱/时间/关系/风险）
- **情感目标**: （读者应感到什么）
- **价值**: 开（正/负）→收（反极,必须换极）
- **攻防**: 他要（不定式）/（对手）要（不定式）
- **beats**: ①（动名词+字数预算）|②（同）|③（同）|字数带=beats合计+600
- **进场点**: （从哪句进） | **出场点**: （停在哪拍）
- **喜剧**: 责任人（谁）+类型（docs/23编号）+一句话内容
- **爽点**: 兑现P（编号,利息）/充能P（编号,悬念原料）
- **Pre**: （本场成立的前提） | **Post**: （本场结束世界新状态） | **Forbid**: （本场禁发生的事）
- **钩**: （形态,须与上两章不同——查ledgers/钩分布.md末3行）
- **获得**: （四类之一,具体物）
- **声纹**: （出场人每人一行,从声口卡抄）
- **知情状态**: （谁知道什么,与上章对表）
- **焦点**: （2-3项,本章最高优先级）
- **章级**: 普通|峰章
- **数字表**: （本章全部数字事实逐条——冷读按表验算）
- **承接**: （上一场末状态一句话+本场开场如何接）
- **生活层**: 细节×3（优先引素材库编号）/钱面（金额+谁的账+情绪运算）/闲笔≥60字/感官≥3通道/慢拍(查结构轮换账)/私货每人1个/家常≥1轮
NEXT-SKILL: write:scene-draft
"""

COLDREAD_SKELETON = """# 冷读-第{n:03d}章（标题）
<!-- generated-by:skill_protocol gen-coldread —— 六项量规逐项引原文作证,禁空评 -->
## 锚定
- （填）劣锚样张评分: 样张一(_) 样张二(_) 样张三(_) ——任一≥7分本轮作废
- 白金锚对照: （开篇章必答:一句话说出读者心里憋着的问题;说不出=追读≤4）

## 六项量规(拆双层)
- ① 笑点/生活气会心: _次(各在第几段)
- ② 跳读点: （引原句,标时长）
- ③ 爽点兑现: 一句话说出本章"得到"什么;**兑现有人收货吗?**
- ④ 追读欲双层: 推力=弃书点（引原句）;**拉力=读者憋着的问题:_（说不出=≤4分）**;钩强度_/10
- ⑤ 对手威胁兑现: 近3章对手对主角的实际伤害:（填）;AI感硬特征逐项:_（原样重复/警句堆叠/段尾总结/情绪标注/解说笑点/隐形摄影机）
- ⑦ 成对比较: 与上一章比更想读哪章,为什么

## 判定
- 最强段落摘录(（填）逐字引一段——范例段飞轮收割源,bundle喂给后续章): （填）
- 生活气摘录(（填）一段烟火气: 物件/钱面/跑题对话——生活型范例收割源): （填）
- 追读判定: 会翻/不会翻/勉强 + 一句理由
- 最致命问题≤3（按弃书风险排,引原文）
- 总分: _/10
"""


def cmd_gen(what, n, book, vol):
    (book / "卡").mkdir(parents=True, exist_ok=True)
    if what == "card":
        if vol == 1:   # 未显式给卷: 按正文分布推期望卷(1993ch031/ch032事故: 跨卷后默认卷1落错位)
            try:
                import gate_chapter as _g
                _files = sorted((book / "text").rglob("第*.md")) if (book / "text").is_dir() else []
                _vols = _g.scan_volumes(_files)   # scan_volumes吃Path(用p.name)
                _exp = _g.expected_volume(n, _vols)
                if _exp:
                    vol = int(re.search(r"\d+", str(_exp)).group())   # expected_volume返回"卷2",归一成数字
            except Exception:
                pass
        out = book / "卡" / f"卷{vol}-第{n:03d}章-场1.md"
        out.write_text(CARD_SKELETON.format(vol=vol, n=n), encoding="utf-8")
    elif what == "coldread":
        out = book / "audit" / f"冷读-第{n:03d}章.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(COLDREAD_SKELETON.format(n=n), encoding="utf-8")
    else:
        print(f"未知产物: {what}(支持: card/coldread)")
        return 2
    print(f"骨架已生成: {out}——填空式作业,残留（填）=无效骨架卡")
    return 0


def cmd_audit_cards():
    """staged卡全查: 指纹+骨架残留(Python单点实现,替代hook的shell嵌套——shell条件是bug温床)"""
    import subprocess
    r = subprocess.run(["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-status",
                        "--diff-filter=ACMR"], capture_output=True, text=True, cwd=ROOT)
    bad = 0
    cards = []
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        for path in parts[1:]:
            if re.search(r"卡/.*第\d+章.*\.md$", path) or re.search(r"冷读-第\d+章.*\.md$", path):
                cards.append(path)
    for c in cards:
        fp = ROOT / c
        if not fp.exists():
            continue
        txt = fp.read_text(encoding="utf-8-sig")
        kind = "冷读报告" if "冷读-" in c else "场景卡"
        if any(m in txt for m in ("（填）", "（四选一", "（本章全部数字事实")):
            print(f"  [FAIL] {kind}骨架残留(占位提示语): {c}——逐字段填完(填空式作业)")
            bad += 1
        elif "generated-by:skill_protocol" not in txt:
            print(f"  [FAIL] {kind}非脚手架产物(缺generated-by指纹): {c}——从零手写=绕过技能;重跑: python3 tools/skill_protocol.py gen {'coldread' if '冷读-' in c else 'card'} <章号> --book <书根>")
            bad += 1
    if cards and not bad:
        print(f"  ✓ 脚手架产物检查通过({len(cards)}件: 指纹+无残留)")
    elif not cards:
        print("  (无staged脚手架产物)")
    return 1 if bad else 0


def main():
    args = sys.argv[1:]
    if args and args[0] == "gen":
        # gen card|coldread <章号> [--vol N] [--book 书根]
        what = args[1] if len(args) > 1 else ""
        n = int(re.sub(r"\D", "", args[2] if len(args) > 2 else "") or 0)
        vol = int(args[args.index("--vol") + 1]) if "--vol" in args else 1
        book = ROOT / args[args.index("--book") + 1] if "--book" in args else ROOT
        return cmd_gen(what, n, book, vol)
    if args and args[0] == "audit-cards":
        return cmd_audit_cards()
    if len(args) < 2 or args[0] not in ("list", "audit"):
        print(__doc__)
        return 2
    mode = args[0]
    rest = args[1:]
    n = int(re.sub(r"\D", "", rest[0]) or 0) if rest else 0
    book = ROOT
    if "--book" in args:
        book = ROOT / args[args.index("--book") + 1]
    wf = args[args.index("--wf") + 1] if "--wf" in args else None
    return cmd_list(n, book, wf) if mode == "list" else cmd_audit(n, book)


if __name__ == "__main__":
    sys.exit(main())
