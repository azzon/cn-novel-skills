#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
card_check.py 场景卡↔正文 数字对账器(法医ch001事故: 卡数字表有"角膜浑浊约12小时",正文修订时删丢,卡-文数字失对——以场景卡数值改正文;若卡错先改卡再过gate)

原理:
  场景卡 text/卡/卷N-第MMM章-*.md 的"数字表"字段登记本章必须出现的事实数字
  (金额/时间/比例/号码)。正文修订时数字极易漂移或丢失——机器逐条对账:
    - 条目数字在正文找不到任何形式(中文/阿拉伯) → FAIL(账实不符)
    - 数字表字段缺失 → WARN

匹配是宽松的: "两千五" 会在正文找 两千五/2500/二千五 任一形式;
"提成3%" 找 3%/百分之三; 条目中无数字的纯文字项(如"日结") → 跳过不查。

用法:
  python3 tools/card_check.py <章号>            # 自动找卡(text/卡/ 与 <书根>/卡/)
  python3 tools/card_check.py 42 --volume 2
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CN_DIG = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def cn2num(s):
    """中文数字串→数值; 口语省略: 两千五=2500/三百二=320/一万八=18000(末尾裸数字按最后单位升位)"""
    s = s.strip().rstrip("块元毛角分")
    if not s:
        return None
    total, section, digit, has, last_unit, zero_pending = 0, 0, 0, False, None, False
    for ch in s:
        if ch == "零":
            zero_pending = True   # 两万零八: 零=补位,其后裸数字是个位不升位
            continue
        if ch in CN_DIG:
            digit, has = CN_DIG[ch], True
        elif ch in CN_UNIT:
            u = CN_UNIT[ch]
            if u >= 10000:
                section = (section + digit) * u if digit else section * u
                total += section
                section, digit = 0, 0
            else:
                section += (digit or 1) * u
                digit = 0
            last_unit = ch
        else:
            return None
    if digit:
        lift = 1 if zero_pending else {"万": 1000, "千": 100, "百": 10}.get(last_unit, 1)
        section += digit * lift
    return total + section if (has or section) else None


def extract_vals(text):
    """文本→数值集合(阿拉伯+中文口语全部数值化)"""
    vals = set()
    for m in re.finditer(r"(?<!\d)-?\d+(?:\.\d+)?", text):   # W6:负号入账;W10:(?<!\d)防"3-5天"裂成[3,-5]
        try:
            vals.add(float(m.group()))
        except ValueError:
            pass
    # 口语小数2: 零点八/三点五 = d.f(审计-32: "点"字小数,用于厘米/公斤类度量)
    for m in re.finditer(r"([零一二两三四五六七八九])点([零一二三四五六七八九]+)", text):
        d = CN_DIG.get(m.group(1), 0)
        f = "".join(str(CN_DIG.get(c, 0)) for c in m.group(2))
        vals.add(round(d + float("0." + f), 3))
    # 口语小数: 一块五/两块八毛 = w.f 元(审计-32:纯整数解析器无法表达X块五)
    for m in re.finditer(r"([零一二两三四五六七八九])块([零一二三四五六七八九])(毛)?(?![包盒根支条张个只台件号栋层间元块])", text):
        # 后瞻排除量词: "两块一包"的"一"属量词不构成2.1(审计-32自我修正)
        w = CN_DIG.get(m.group(1), 0)
        f = CN_DIG.get(m.group(2), 0)
        vals.add(round(w + f * 0.1, 2))
    cn_chars = set(CN_DIG) | set(CN_UNIT)
    i = 0
    while i < len(text):
        if text[i] in cn_chars:
            j = i
            while j < len(text) and text[j] in cn_chars:
                j += 1
            # 红队20260917: "三千一年(3000元/年)"被口语截断解析成3100——数字段后紧跟
            # 时间/序数量词时,该段是时长/次序不是金额,跳过(修卡-文对账假阳性)
            if j < len(text) and text[j] in "年月天日岁位次回趟年":
                i = j
                continue
            for k in range(j, i, -1):
                v = cn2num(text[i:k])
                if v is not None and v >= 0:   # 0合法(卡载"流水0"),比对由negation规则兜底(审计-32: v>0过滤致0永远FAIL)
                    vals.add(float(v))
                    break
            i = j
        else:
            i += 1
    return vals


def find_card(n, book=None):
    """寻卡: 显式书根优先(审计-32 S3: 章号在双书都存在时,无书根寻址会错对主书的卡)"""
    roots = [pathlib.Path(book)] if book else [ROOT] + [d for d in ROOT.iterdir() if d.is_dir()]
    for root in roots:
        for cdir in (root / "text" / "卡", root / "卡"):
            if cdir.is_dir():
                for pat in sorted(cdir.glob(f"*第{n:03d}章*")):
                    return pat
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    n = int(re.sub(r"\D", "", args[0]) or 0)
    vol = 1
    if "--volume" in sys.argv:
        vol = int(sys.argv[sys.argv.index("--volume") + 1])
    book = None
    if "--book" in sys.argv:
        book = pathlib.Path(sys.argv[sys.argv.index("--book") + 1])
    card = find_card(n, book)
    if card is None:
        print(f"  [FAIL] 第{n:03d}章场景卡不存在——scene-card先于正文,无卡=流程倒置(1993ch031事故;豁免走waivers登记card门)")
        return 1
    # 骨架卡拦截: 占位符残留=卡未填,数字表必空转(1993ch031事故vacuous pass根因)
    # 注: generated-by指纹是audit-cards要求的合法标记,只判（填）残留
    ct0 = card.read_text(encoding="utf-8-sig")
    issues, warns = [], []
    # 工艺行非占位(红队技能库: scene-discipline/cool-point挂载盲区——卡上钩/爽点/生活层/焦点四行是工艺挂载的落点,占位=挂载空转)
    for _fld in ("钩", "爽点", "生活层", "焦点"):
        _m = re.search(rf"[-*]\s*\*\*{_fld}\*\*[:：]\s*(.\S*)", ct0)
        _v = _m.group(1).strip() if _m else ""
        if not _v or _v.startswith("（"):
            _msg = f"卡上「{_fld}」行未实填(占位/缺失)——工艺挂载(scene-discipline/cool-point)的落点,填了才算挂载过"
            (warns if "补录卡" in ct0 else issues).append(_msg)   # 补录卡=legacy_cards诚实欠账,降WARN;新卡FAIL
    # 红队20260919上限批: 情绪/距离/主导感官三字段——旧卡不追杀(降WARN),新卡缺=情感工程挂载空转
    for _fld2 in ("情绪", "距离", "主导感官"):
        _m2 = re.search(rf"[-*\d]\s*\*{{0,2}}{_fld2}\*{{0,2}}[:：]", ct0)   # W6验证:原仅匹配**情绪**:精确粗体,编号/无粗体变体误报
        if not _m2:
            warns.append(f"卡缺「{_fld2}」行(红队20260919新字段:情感档位/叙事距离/主导感官)——旧卡降WARN可waivers;新卡必填(skill_protocol gen card已含)")

    from skill_protocol import scaffold_residue
    _res = scaffold_residue(ct0)
    if _res:
        print(f"  [FAIL] {card.name} 骨架卡未填(残留:{''.join(_res[:3])})——先走scene-card填卡再写正文")
        return 1
    # 找正文(主书或书根)
    body_p = None
    _cands = [card.parent.parent / "text" / f"卷{vol}" / f"第{n:03d}章.md",
              ROOT / "text" / f"卷{vol}" / f"第{n:03d}章.md"]
    if book:   # --book 显式指定时书根正文绝对优先(审计-32 S3: 章号双书歧义)
        _cands.insert(0, book / "text" / f"卷{vol}" / f"第{n:03d}章.md")
    for cand in _cands:
        if cand.exists():
            body_p = cand
            break
    if body_p is None:
        print(f"  [FAIL] 正文不存在(卷{vol} 第{n:03d}章)——对账无对象")
        return 1
    ct = card.read_text(encoding="utf-8-sig")
    body = body_p.read_text(encoding="utf-8-sig")
    m = re.search(r"[-*]\s*\*\*数字表?\*\*[:：](.+)", ct)
    if not m:
        print(f"  [WARN] {card.name} 无数字表字段——建议补(法医ch001教训:数字失对账)")
        return 0
    items = [x.strip() for x in m.group(1).split("/") if x.strip()]
    # 空表拦截: 占位/无数字条目=数字表未实填(唯一合法空表=明写"无")
    items_real = [x for x in items if extract_vals(re.sub(r"（[^）]*）|\([^)]*\)", "", x))]
    if not items_real:
        if any(x == "无" or x.startswith("无(") or x.startswith("无（") or x in ("无数字", "本章无数字事实") for x in items):
            print(f"  数字表明写无数字事实({card.name})——对账跳过")
            return 0
        print(f"  [FAIL] {card.name} 数字表无有效条目(全占位或无数字)——数字表是冷读验算依据,必须实填")
        return 1
    body_vals = extract_vals(body)
    for it in items:
        it_clean = re.sub(r"（[^）]*）|\([^)]*\)", "", it)
        card_vals = extract_vals(it_clean)
        if not card_vals:
            continue
        # 小数口语变体: 卡载1.5 ↔ 正文"一块五/一块五毛"——把卡载小数展开成(整数部分,小数部分)整数对
        expanded = set()
        for v in set(card_vals):
            if v != int(v):
                w = int(v); frac = round((v - w) * 10)
                expanded.add(float(w)); expanded.add(float(frac))
                expanded.add(float(w * 10 + frac))   # 一块五毛→15角?取"一五"组合容错
        card_vals_cmp = card_vals | expanded
        body_cmp = body_vals | expanded
        missing = card_vals_cmp - body_cmp - {v for v in card_vals_cmp if v == 0}
        if card_vals_cmp and any(v == 0 for v in card_vals) and re.search(r"[没无]\s*(卖|收|开张)|分文未|一台没", body):
            missing.discard(0.0)
        if missing:
            miss = "、".join(str(int(v)) if v == int(v) else str(v) for v in sorted(missing))
            issues.append(f"第{n:03d}章正文缺卡载数值[{miss}]: {it.strip()[:30]}——卡-文失对账(修订时数字漂移?)")
    for l in issues:
        print(f"  [FAIL] {l}")
    for w in warns:
        print(f"  [WARN] {w}")
    if not issues and not warns:
        print(f"  数字表{len(items)}项全部对上({card.name})")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())