#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""block_pipeline.py 章块流水线(20260919用户令三批: 块审块切,解"单元剧断裂感")

双粒度架构(对用户"先写2万字再切8-10章"提案的系统化修正):
  生成粒度=场景(卡→稿,3-5场/块,连续写作共享bundle)——单次生成禁超1场/2400字,
           LLM长文单pass质量衰减(漂移/匀速化)与去AI味目标相悖,故"块"不是生成单位;
  审计/切分粒度=章块(默认4-6章≈1.2-1.5万字,硬上限8章/2.2万字)——
           连读连贯性在块级审查,断章按张力峰值切割(duanzhang),再逐章补钩/卡/账/冷读。

块级全流程(workflows/block_production.yaml):
  start立块 → 逐场生成(scene-card/scene-draft连续写) → 块稿落 text/块/
  → check-block跨章卫生 → 块级冷读(arc-review) → 块级storm v2(60agent含连读审读官)
  → 修订迭代到放行 → duanzhang断章切分 → 逐章补卡/钩/八账/冷读 → 逐章done
  (storm用 storm-stamp 把块级放行登记到各章state——done的storm门认可块级审计)

命令:
  start <书根> <起> <止> [--title 标题]          立块(块卡骨架+字数预算+草稿文件)
  check-block <书根> <草稿文件>                  块级卫生: 跨章原样重复/段长方差/对白比/切点候选
  storm-stamp <书根> <起> <止> <块state.json>    块storm放行结果登记到各章state(done gate可用)
  status <书根>                                  块清单
"""
import sys, json, re, pathlib, collections

ROOT = pathlib.Path(__file__).resolve().parent.parent
BLOCK_MAX_CH = 8          # 硬上限: 超过=审计深度不足+退稿爆炸半径过大
BLOCK_MAX_CHARS = 22000

def _book(p):
    p = pathlib.Path(p)
    while p != p.parent and not (p / "text").is_dir():
        p = p.parent
    return p

def _block_path(book, a, b):
    return book / "story" / "30-情节" / f"块-第{a:03d}-{b:03d}章.md"

def _draft_path(book, a, b):
    return book / "text" / "块" / f"块-第{a:03d}-{b:03d}章.md"

def cmd_start(book, a, b, title=""):
    book = _book(book)
    n = b - a + 1
    if n < 2:
        print("❌ 块至少2章(单章走原逐章流水)"); return 2
    if n > BLOCK_MAX_CH:
        print(f"❌ 块超上限: {n}章(硬上限{BLOCK_MAX_CH}章)——审计深度不足,退稿爆炸半径过大;请拆块"); return 2
    bp, dp = _block_path(book, a, b), _draft_path(book, a, b)
    if bp.exists():
        print(f"❌ 块已存在: {bp}"); return 1
    budget = n * 2400
    bp.parent.mkdir(parents=True, exist_ok=True)
    bp.write_text(f"""# 章块卡 第{a:03d}-{b:03d}章（{title or '（填）'}）
<!-- generated-by:block_pipeline start —— 块级作业卡;块=审计/切分单位,生成仍按场景卡逐场 -->
- **块主题句**: （这个叙事弧讲什么,一个问句）
- **章数/字数预算**: {n}章 / {budget}±{n*200}字(硬上限{BLOCK_MAX_CHARS})
- **场景簇**: （3-5个场景卡,每场一张scene-card,连续生成共享bundle;禁单次生成整块）
- **张力曲线**: （蓄压拍→峰拍位置≈第几场→回落拍;峰拍后禁释压段）
- **切点候选**: （duanzhang断章法: 张力峰值处切割,预先标注2-3处候选;切点即章末钩,须钩型轮换）
- **跨章承接**: （与上一块末拍的接续;与下一块的门缝）
- **块级获得**: （本块总获得物;块内各章获得阶梯）
- **Forbid**: （本块禁发生;违者重写）
""", encoding="utf-8")
    dp.parent.mkdir(parents=True, exist_ok=True)
    _acc = book / "ledgers" / "块账"
    _acc.mkdir(parents=True, exist_ok=True)
    (_acc / ("blk-%03d-%03d.md" % (a, b))).write_text(
        "# 块账 %03d-%03d(切分前逐场登记,切分后回填八账;漏项=done拦截)\n\n"
        "| 场 | 预属章 | 数字/钱面 | 伏笔(埋/养/收) | 人物位移 | 时间 |\n|---|---|---|---|---|---|\n" % (a, b),
        encoding="utf-8")
    dp.write_text(f"# 块稿 第{a:03d}-{b:03d}章（{title or '（填）'}）\n\n<!-- 逐场生成后按场拼入;每场以【场N·场景卡名】分隔 -->\n", encoding="utf-8")
    print(f"✅ 立块: 第{a:03d}-{b:03d}章({n}章,预算{budget}±{n*200}字)")
    print(f"   块卡: {bp}\n   块稿: {dp}")
    print(f"   流程: 逐场scene-card→scene-draft(共享bundle,禁单次生成整块)→check-block→块级冷读→块级storm v2→修订迭代→duanzhang切分→逐章done")
    return 0

def cmd_check_block(book, draft):
    book = _book(book)
    draft = pathlib.Path(draft)
    if not draft.exists():
        print(f"❌ 块稿不存在: {draft}"); return 1
    body = draft.read_text(encoding="utf-8")
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip() and not p.strip().startswith(("#", "<!--", "【"))]
    cjk = len(re.findall(r"[\u4e00-\u9fff]", body))
    problems, warns = [], []
    # 1 体量
    if cjk > BLOCK_MAX_CHARS:
        problems.append(f"块字数{cjk}>{BLOCK_MAX_CHARS}——拆块")
    # 2 跨场原样重复(18字shingle,工程词/分隔行已滤)
    text = re.sub(r"[\s\u201c\u201d\"]+", "", body)
    seen, dups = set(), []
    for i in range(len(text) - 18):
        sh = text[i:i+18]
        if sh in seen:
            dups.append(sh)
        seen.add(sh)
    if dups:
        problems.append(f"块内原样重复{len(dups)}处(如: {dups[0][:18]})——禁补丁叠加,整场重写")
    # 3 段长方差+对白比
    lens = [len(re.findall(r"[\u4e00-\u9fff]", p)) for p in paras]
    if lens:
        avg = sum(lens) / len(lens)
        var = (sum((l - avg) ** 2 for l in lens) / len(lens)) ** 0.5
        if var < 35:
            warns.append(f"段长方差{var:.0f}(<35)——长段蓄压/超短段重音错落不足")
    dia = sum(len(p) for p in paras if p.startswith(("“", "”", '"')))
    dia_pct = dia * 100 / max(sum(lens), 1)
    if dia_pct < 38:
        warns.append(f"对白段占比{dia_pct:.0f}%(<38)——对白驱动不足")
    # 4 切点候选(duanzhang): 超短段+问句/感叹收尾的段=张力峰
    cuts = [p[:24] for p in paras if 0 < len(re.findall(r"[\u4e00-\u9fff]", p)) <= 6]
    # W11-1 章配额模拟: 破折号<=3/明喻<=3每场——块全文达标但单场超标=切出必FAIL
    for m in re.finditer(r'【场(\d)[^】]*】([\s\S]*?)(?=【场\d|$)', body):
        sc, txt = m.group(1), m.group(2)
        dash = txt.count('——')
        sim = len(re.findall(r'像[^。，!?\n]{1,10}一样|像一|仿佛|如同', txt))
        if dash > 3: problems.append(f'场{sc} 破折号{dash}处(>3)——切出为章必FAIL')
        if sim > 3: problems.append(f'场{sc} 明喻{sim}处(>3)——切出为章必FAIL')
    print(f"═══ 块级卫生: {draft.name} ({cjk}字,{len(paras)}段) ═══")
    for x in problems: print(f"  [FAIL] {x}")
    for x in warns: print(f"  [WARN] {x}")
    # 段首签名(磨刀六批): 同一首词连开≥3段=句式签名(全书指纹"陈灶生把"17章的块级防线)
    heads = collections.Counter(p[:4] for p in paras if len(re.findall(r"[\u4e00-\u9fff]", p)) >= 6)
    sig = [(h, c) for h, c in heads.items() if c >= 3]
    for h, c in sig:
        warns.append(f"段首签名「{h}」×{c}——同起手连用,轮换起手(人名/动作/器物/他)")
    if cuts:
        print(f"  切点候选(张力峰,duanzhang): {' | '.join(c[:18] for c in cuts[:5])}")
    if not problems and not warns:
        print("  全项通过")
    print("\n  下一动作: 块级冷读(arc-review)→块级storm v2(init/record/repair/aggregate)→放行后duanzhang切分")
    return 1 if problems else 0

def cmd_storm_stamp(book, a, b, block_state):
    """块storm放行结果 → 各章storm state(done的storm门认可块级审计;state里记block溯源)"""
    book = _book(book)
    bs = pathlib.Path(block_state)
    if not bs.exists():
        print(f"❌ 块storm state不存在: {bs}"); return 1
    data = json.loads(bs.read_text(encoding="utf-8"))
    if data.get("verdict") != "放行":
        print(f"❌ 块storm判定={data.get('verdict')}——放行后才可stamp"); return 1
    import storm_orchestrate as SO
    ok = 0
    for n in range(a, b + 1):
        ch = None
        for _v in (book / "text").iterdir():
            if _v.is_dir() and (_v / f"第{n:03d}章.md").exists():
                ch = _v / f"第{n:03d}章.md"; break   # 磨刀十批B1: 卷1硬编码→全卷扫描
        if not ch.exists():
            print(f"  [SKIP] 第{n:03d}章未切分落盘"); continue
        sp = SO.storm_state_path(ch)
        sp.parent.mkdir(parents=True, exist_ok=True)
        data = dict(data)
        data["target"] = str(ch)
        import hashlib as _h, datetime as _dt
        data["block"] = {"起": a, "止": b, "块state": str(bs), "溯源": "块级60agent审计覆盖本章全文",
                         "块稿hash": _h.sha1(pathlib.Path(data["target"]).read_bytes()).hexdigest()[:12] if pathlib.Path(data["target"]).exists() else None,
                         "章hash": _h.sha1(ch.read_bytes()).hexdigest()[:12],
                         "stamp_at": _dt.datetime.now().isoformat(timespec="seconds")}
        data["verdict_locked"] = True
        sp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        ok += 1
    print(f"✅ 块storm盖章: {ok}章(第{a:03d}-{b:03d})——done的storm门已认可;切分后仍须逐章check/冷读/八账/done")
    return 0

def cmd_status(book):
    book = _book(book)
    blocks = sorted((book / "story" / "30-情节").glob("块-第*.md")) if (book / "story" / "30-情节").is_dir() else []
    drafts = sorted((book / "text" / "块").glob("块-第*.md")) if (book / "text" / "块").is_dir() else []
    print(f"═══ 章块状态 ═══")
    print(f"  块卡: {len(blocks)}个  块稿: {len(drafts)}个")
    for b in blocks:
        print(f"  📦 {b.name}")
    return 0

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    if cmd == "start" and len(sys.argv) >= 5:
        title = sys.argv[sys.argv.index("--title") + 1] if "--title" in sys.argv else ""
        return cmd_start(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), title)
    if cmd == "check-block" and len(sys.argv) >= 4:
        return cmd_check_block(sys.argv[2], sys.argv[3])
    if cmd == "storm-stamp" and len(sys.argv) >= 6:
        return cmd_storm_stamp(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    if cmd == "status" and len(sys.argv) >= 3:
        return cmd_status(sys.argv[2])
    print(__doc__); return 2

if __name__ == "__main__":
    sys.exit(main())
