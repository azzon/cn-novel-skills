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
        ev = " → 产物: (路径或exit码,红队20260915: 打勾不带产物引用=自证,audit会拦)" if sid in ("scene_card", "draft", "cold_read", "ledger", "memory", "done", "commit") else ""
        if typ == "script":
            rows.append(f"- [ ] {sid}({name}) [script步骤:真实执行命令后勾——预勾=审计失真(磨刀十三批H2)]{ev}")
        elif f:
            rows.append(f"- [ ] {sid}({name}) 技能: {skill} → {f.relative_to(ROOT)}{ev}")
        else:
            rows.append(f"- [ ] {sid}({name}) 技能: {skill or '(无)'}{ev}")
    book.mkdir(parents=True, exist_ok=True) if not book.exists() else None
    (book / "ledgers").mkdir(parents=True, exist_ok=True)
    rec.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"技能挂载清单已生成: {rec}")
    for r in rows:
        if r.startswith("- "):
            print(" ", r[:100])
    return 0


def cmd_audit(n, book, evidence=False):
    rec = book / "ledgers" / "技能执行记录.md"
    if not rec.exists():
        print(f"[FAIL] 无技能执行记录: {rec}——先跑 skill_protocol.py list {n}")
        return 1
    total = done = 0
    missed = []
    no_ev = []
    bad_ev = []
    toks = (f"第{n}章", f"第{n:03d}章")
    for line in rec.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("- ["):
            continue
        total += 1
        if line.startswith("- [x]"):
            done += 1
            if "→ 产物:" in line or "→产物:" in line:
                import re as _re
                m2 = _re.search(r"→\s*产物[:：]\s*([^ （(，,;；]+)", line)
                if m2:
                    ref = m2.group(1).strip().strip("，,;；")
                    if ref.startswith("(") or ref == "(路径或exit码,红队20260915:打勾不带产物引用=自证,audit会拦)":
                        no_ev.append(line[:80])
                    elif re.fullmatch(r"exit[01](\([0-9a-f]{6,}\))?", ref.lower()):
                        pass   # script步骤: exit码引用
                    else:
                        fp = (book / ref) if not ref.startswith("/") else pathlib.Path(ref)
                        if not fp.exists():
                            bad_ev.append(f"产物不存在: {ref} (来自: {line[:50]}…)")
                        elif fp.suffix == ".md" and "第" in fp.name and "章" in fp.name:
                            pass   # 章节文件本身: 存在即证据(标题用中文数字"第一章",数字token检查不适用)
                        elif fp.suffix == ".md" and not any(tk in fp.read_text(encoding="utf-8", errors="ignore")[:20000] for tk in toks):
                            bad_ev.append(f"产物未含第{n:03d}章token: {ref}")
            else:
                no_ev.append(line[:80])
        else:
            missed.append(line[:90])
    rate = done / total * 100 if total else 0
    print(f"技能执行率: {done}/{total} ({rate:.0f}%)")
    for m in missed:
        print(f"  [漏] {m}")
    if no_ev:
        print(f"  [WARN] {len(no_ev)}项打勾无产物引用(自证)——新章须按模板带'→ 产物: 路径'")
    for b in bad_ev:
        print(f"  [FAIL] 证据链断裂: {b}")
    if rate < 100:
        print("  [WARN] 执行率<100%——跳过的步骤产物按协议无效,done验收视角降级")
    if evidence and (no_ev or bad_ev):
        return 1
    return 0 if not bad_ev else 1


CARD_SKELETON = """# 场景卡 卷{vol}-第{n:03d}章（标题）
<!-- generated-by:skill_protocol gen-card —— 本卡由scene-card技能骨架生成,填空式作业;占位符未清=骨架卡(注释自身禁含占位字样,否则填好的卡过不了骨架门),scene-draft拒工 -->
- **开场型**: （四选一:对话直入|动作直入|异常直入|判断句;须与前两章错型）
- **场景型**: （单元型+压弹级）
- **情绪**: （主档:燃|泪|爽|喜|日常|紧张|沉郁|暖+情感重场:是/否;重场=是→writing-heart强制走,pipeline-chapter全装轨）
- **距离**: （叙事距离:贴身|中距|远景;高潮拍=贴身,过渡拍=远景——叙事距离.md三挡）
- **主导感官**: （单选:味|嗅|听|触|视;辅助≤2——一章一主导,五感杂拌=check.py#73）
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
- **爽点**: 兑现P（编号,利息）/充能P（编号,悬念原料）/扩散（谁围观+怎么传开;兑现拍末80-150字反应链:个人愣→全场炸→有人传话）
- **Pre**: （本场成立的前提） | **Post**: （本场结束世界新状态） | **Forbid**: （本场禁发生的事）
- **钩**: （形态,须与上两章不同——查ledgers/钩分布.md末3行）
- **获得**: （四类之一,具体物）
- **声纹**: （出场人每人一行,从声口卡抄）
- **知情状态**: （谁知道什么,与上章对表）
- **焦点**: （2-3项,本章最高优先级）
- **章级**: 普通|峰章
- **数字表**: （本章全部数字事实逐条——冷读按表验算）
- **承接**: （上一场末状态一句话+本场开场如何接）
- **代价等级**: （0=无代价/1=时间精力/2=金钱声誉/3=关系健康/4=不可逆损失——写具体数字+具体内容;每卷统计: 全卷1-2=太顺需加3-4级）
- **情绪前因**: （本拍情绪来源=前一拍的什么事件/对话/发现——写因果链,禁标签式'他很愤怒';每拍至少有前因）

- **生活层**: 细节×3（优先引素材库编号）/钱面（金额+谁的账+情绪运算）/闲笔≥60字/感官≥3通道(每通道至少1个具体感官词:味/触/嗅/听,禁只写视觉)/慢拍(查结构轮换账)/私货每人1个/家常≥1轮/记忆闪回≥1条（主角私人记忆,由本拍感官触发→"想起/那年"+具体画面30-60字,不复述情节;素材库记忆袋取,无则现造并回记）
NEXT-SKILL: write:scene-draft
"""

# 骨架占位串全集(从CARD_SKELETON自动派生;审计20260917: 原3个标记漏掉（不定式）（停在哪拍）等,旧卡未填字段过门)
SKELETON_MARKS = sorted(set(re.findall(r"（[^（）]{1,24}）", CARD_SKELETON)) | {"（填）"})


def scaffold_residue(text):
    """返回卡文本中残留的骨架占位串列表"""
    return [m for m in SKELETON_MARKS if m in text]


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
- ⑥ 流派契约: 本书流派_——本章爽感符合其引擎?_(躺赢流查: 反差成立吗/无心可信吗/三轴在场吗;经营流查: 资产表动了吗;先知系查: "正常人怎么会知道"过没过)——流派死因自查:_
- ⑦ 成对比较: 与上一章比更想读哪章,为什么
- ⑧ 代入感(三引擎): 主角有感官记忆闪回吗(气味/声音/触觉)?你觉得自己就是他吗?哪一拍你忘了自己是读者?
- ⑨ AI检测: 若不知情,你能猜出是AI写的吗?哪一段最像AI?段落长短有错落还是匀速?
- ⑩ 付费意愿: 有没有让你想截图发群的场面?哪一拍?如果下一章要付费,你掏不掏钱?为什么?
⑪ 新颖度: 这章的核心桥段/反转/冲突,你在别的书里见过吗?新版本比原版好在哪?
⑫ 代价真实度: 主角这章的每个选择,代价真实吗?是'失去了X'还是'心里不舒服'?前者是代价,后者是情绪
⑬ 对白意外度: 遮住角色的回答,你能预测下一句吗?预测不到=好;预测到了=角色变成传声筒

## 判定
- 最强段落摘录(（填）逐字引一段——范例段飞轮收割源,bundle喂给后续章): （填）
- 生活气摘录(（填）一段烟火气: 物件/钱面/跑题对话——生活型范例收割源): （填）
- 追读判定: 会翻/不会翻/勉强 + 一句理由
- 最致命问题≤3（按弃书风险排,引原文）
- 总分: _/10

---
[COLDREAD-METRICS] 章:{n:03d} 钩强度:x/10 追读:x/10 哭点:有/无 (机器行,drift-audit聚合用,数字按上评分如实填)
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
    # 红队20260919漏洞3修复: gen card加入前瞻窗口检查(防绕过cmd_next)
        _files = sorted((book / "text").rglob("第*.md")) if (book / "text").is_dir() else []
        _nums = [int(re.search(r"\d+", f.stem).group()) for f in _files if re.search(r"\d+", f.stem)]
        _maxn = max(_nums) if _nums else 0
        if _maxn > 0 and n > _maxn + 10:
            print(f"[前瞻窗口] 第{n:03d}章超出前瞻窗口(max={_maxn},窗口={_maxn+1}~{_maxn+10})")
            print(f"  滚动前瞻模式: 卡只做5-10章远;要排更远须卷末复盘+下一卷纲")
            return 1
        out = book / "卡" / f"卷{vol}-第{n:03d}章-场1.md"
        out.write_text(CARD_SKELETON.format(vol=vol, n=n), encoding="utf-8")
    elif what == "coldread":
        out = book / "audit" / f"冷读-第{n:03d}章.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(COLDREAD_SKELETON.format(n=n), encoding="utf-8")
        if book == ROOT:
            _alt = ROOT / 'story' / 'audit' / f'冷读-第{n:03d}章.md'
            _alt.parent.mkdir(exist_ok=True)
            _alt.write_text(COLDREAD_SKELETON.format(n=n), encoding='utf-8')  # P1-031
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
    # P0-001修复: 参数校验前置
    if len(sys.argv) > 3 and sys.argv[1] == "gen" and sys.argv[2] in ("card", "coldread"):
        try:
            _n = int(sys.argv[3])
            if _n <= 0:
                print(f"[参数错误] 章号{_n}无效(须≥1)")
                sys.exit(2)
        except (ValueError, IndexError):
            pass
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
    _ev = "--evidence" in rest   # 红队20260915: --evidence曾是死旗标(main不解析→done硬门空转),接线
    if "--evidence" in rest:
        rest = [a for a in rest if a != "--evidence"]
        args = [args[0]] + rest
    n = int(re.sub(r"\D", "", rest[0]) or 0) if rest else 0
    book = ROOT
    if "--book" in args:
        book = ROOT / args[args.index("--book") + 1]
    wf = args[args.index("--wf") + 1] if "--wf" in args else None
    if mode == "list":
        return cmd_list(n, book, wf)
    return cmd_audit(n, book, evidence=_ev)


if __name__ == "__main__":
    sys.exit(main())