#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voice_check.py 声口卡禁词机器门(用户核心痛点"人人说话都很装"的机器化执行)

原理:
  声口卡(story/60-圣经/声口卡.md)为每个角色登记了 禁词(绝不说的话)与口头禅(声音指纹)。
  本工具对章节正文做 对白归属判定,然后:
    - 该角色的对白里出现他的禁词 → FAIL(声口违例,遮名测试必挂)
    - 该角色对白≥5段却零口头禅 → WARN(声音过干净=没声音)

对白归属规则(v1保守):
  - 段落含 "人名+说/道/问/..." tag → 该段引号内容归属该人名
  - 无tag段落继承上一段归属(对话连写)
  - 段内出现≥2个不同tag人名 → 保守跳过该段
  - 引号外文本不计(叙述允许出现任何词)

用法:
  python3 tools/voice_check.py <章节文件.md> [--card <声口卡路径>]
  声口卡默认 story/60-圣经/声口卡.md; 书根内章节用 --card 指该书卡(多书隔离协议)
"""
import re, sys, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_CARD = ROOT / "story" / "60-圣经" / "声口卡.md"
TAG_VERBS = "说|道|问|答|嘀咕|嘟囔|喊|叫|骂|应|回|接|催|劝|笑|叹|念|哼|插嘴"
RESERVED_SECTIONS = {"聪明预算分级制", "遮名测试验收线"}


def parse_card(card_path):
    """解析声口卡 → {人名: {"口头禅": [...], "禁词": [...]}}; 跳过非人物节"""
    if not card_path.exists():
        return {}, f"声口卡不存在: {card_path}"
    text = card_path.read_text(encoding="utf-8")
    people, cur = {}, None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            name = m.group(1).strip()
            name = re.sub(r"（[^）]*）|\([^)]*\)", "", name).strip()   # 剥"（主角·法医）"注释
            cur = None if name in RESERVED_SECTIONS else name
            people.setdefault(cur, {"口头禅": [], "禁词": []})
            continue
        if cur is None:
            continue
        # 兼容两种卡格式: 主书"- **口头禅**: ['x']" / 新书"- 3个口头禅: "x""
        m2 = re.match(r"^-\s*(?:\*\*(口头禅|禁词)\*\*|\d+个(口头禅|禁词))[:：]\s*(.+)$", line.strip())
        if m2:
            field = m2.group(1) or m2.group(2)
            items = re.findall(r"[\"'“”‘’]([^\"'“”‘’]+)[\"'“”‘’]", m2.group(3))
            people[cur][field] = [x.strip() for x in items if x.strip()]
    people = {k: v for k, v in people.items() if k and (v["口头禅"] or v["禁词"])}
    return people, None


def attribute_dialogue(body, people):
    """逐行对白归属 → {人名: [(引号文本, 行首20字)]}
    行粒度(主书单换行分段/新书空行分段均兼容,大审计-18教训:勿按空行切段)"""
    names = sorted(people, key=len, reverse=True)
    result = defaultdict(list)
    alternation = []   # 最近说话人交替栈(≤2人)
    for para in body.split("\n"):
        para = para.strip()
        if not para:
            continue
        speakers = set()
        for n in names:
            if re.search(re.escape(n) + r"[^。！？\n]{0,8}(?:" + TAG_VERBS + r")", para):
                speakers.add(n)
        if len(speakers) == 1:
            cur = speakers.pop()
            if not alternation or alternation[-1] != cur:
                alternation.append(cur)
                if len(alternation) > 2:
                    alternation.pop(0)
        elif len(speakers) > 1:
            cur, alternation = None, []
        else:
            # 无tag行: 对白轮转感知——最近两人交替场景下归属"另一人"(A-B-A-B中文对话惯例)
            cur = alternation[-2] if len(alternation) == 2 else (alternation[-1] if alternation else None)
        _qraw = re.findall('“([^“”]{2,})”|「([^「」]{2,})」|"([^"]{2,})"', para)   # W6验证:原只认弯引号,「」/直引号对白不可见=禁词门全绕
        quotes = [a or b or c for a, b, c in _qraw if (a or b or c)]
        quotes = [q for tup in quotes for q in tup if q]
        if cur and quotes:
            hard = cur in speakers   # 有直接tag=硬归属; 轮转/继承=软归属
            result[cur].append((" ".join(quotes), para[:20], hard))
        elif quotes:
            alternation = []
    return result


def _negated(text_all, w):
    """禁词被否定前缀修饰(不一定/没一定)时不算说了禁词"""
    for i in range(len(text_all)):
        j = text_all.find(w, i)
        if j < 0:
            break
        if text_all[max(0, j-1):j] in ("不", "没", "未", "别", "无"):
            continue
        return False
    return True


def check(chapter, card_path=DEFAULT_CARD):
    people, err = parse_card(pathlib.Path(card_path))
    if err:
        return 2, [err], [], {}
    body = "\n".join(l for l in chapter.read_text(encoding="utf-8-sig").splitlines()
                     if l.strip() and not l.startswith("#"))
    attr = attribute_dialogue(body, people)
    issues, warns, stats = [], [], {}
    for name in sorted(attr):
        text_all = " ".join(q for q, _h, hard in attr[name])
        n_para = len(attr[name])
        n_hard = sum(1 for _q, _h, hard in attr[name] if hard)
        bad_hard = [w for w in people[name]["禁词"]
                    if any(w in q and not _negated(q, w) for q, _h, hard in attr[name] if hard)]
        soft_bad = [w for w in people[name]["禁词"]
                    if w in text_all and not _negated(text_all, w) and w not in bad_hard]
        hit = [c for c in people[name]["口头禅"] if c in text_all]
        stats[name] = {"对白段": n_para, "口头禅命中": hit, "禁词违例": bad_hard + soft_bad}
        for w in bad_hard:
            issues.append(f"声口违例: {name}说了禁词「{w}」; 声口卡规定{name}绝不说「{w}」")
        for w in soft_bad:
            warns.append(f"疑似声口违例(轮转归属,弱证据): {name}疑似说了「{w}」——请人工核对说话人")
        if n_hard >= 5 and not hit:
            warns.append(f"{name}硬归属对白{n_hard}段(共{n_para}段)零口头禅{people[name]['口头禅']}——声音过净,像在念稿")
    return (1 if issues else 0), issues, warns, stats


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    card = DEFAULT_CARD
    if "--card" in sys.argv:
        card = pathlib.Path(sys.argv[sys.argv.index("--card") + 1])
    if not args:
        print(__doc__)
        return 2
    code, issues, warns, stats = check(pathlib.Path(args[0]), card)
    for l in issues:
        print(f"  [FAIL] {l}")
    for w in warns:
        print(f"  [WARN] {w}")
    if not issues and not warns:
        print("  声口卡全项通过")
    for name, s in stats.items():
        print(f"  [{name}] 对白段{s['对白段']} 口头禅{s['口头禅命中'] or '无'} 禁词违例{s['禁词违例'] or '无'}")
    print(f"\n声口门: {'FAIL' if code else 'PASS'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
