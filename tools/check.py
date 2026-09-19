#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
章节质量检查脚本(写作宪法第十五条的机械执行)
用法:
  python3 tools/check.py text/卷1/第001章.md   # 检查单章
  python3 tools/check.py text/卷1/            # 检查目录
  python3 tools/check.py --threads text/卷1/  # 草蛇灰线追踪(docs/15):逐章命中矩阵+断线预警
输出:逐项 PASS/WARN/FAIL 与汇总。FAIL 必须修复后归档(宪法要求)。
仅用标准库。
"""
import sys, re, pathlib, statistics, json

# ---------- 规则表 ----------
# (词, 单章上限)  上限-1 表示禁用(0)
WORD_LIMITS = {
    "顿时": 1, "瞬间": 2, "不禁": 1, "不由得": 1,
    "仿佛": 2, "似乎": 2, "竟然": 2,
    "心中暗道": 2, "与此同时": 1,
    "一丝": 3, "微微": 3, "缓缓": 3, "淡淡": 3,
    "眼神闪过": 0, "嘴角勾起": 0, "瞳孔": 0, "空气凝固": 0,
    "值得一提": 0, "不得不说": 0, "命运的齿轮": 0, "注定不平凡": 0,
    "不是……而是": 1,  # 特殊:用 "不是" 后近距 "而是" 检测, 见下
}
BANNED_SENTENCES = ["眼神闪过一丝", "嘴角勾起一抹", "空气仿佛凝固", "瞳孔骤缩",
                    "命运的齿轮", "注定不平凡", "值得注意的"]
# 自我评价词(作者先笑/先感动,读者就不笑了)——文笔论五
SELF_PRAISE = ["忍俊不禁", "逗趣", "哭笑不得", "令人捧腹", "温馨", "感人至深", "催人泪下"]
# 章末总结腔侦测词(最后300字内出现即WARN)
ENDING_SUMMARY_WORDS = ["从此", "这一天", "命运的", "注定", "新的篇章", "拉开了序幕"]
SIMILE_PATTERNS = [r"像[^。!?,\n]{1,12}一样", r"如[^。!?,\n]{1,8}般", r"宛如", r"恍若", r"像[^。!?,\n]{1,12}[。,]", r"似的", r"仿佛[^。!?,\n]{1,10}", r"像是[^。!?,\n]{1,8}"]
EMOTION_TELL = r"(他|她|它|我|众人|众人)(很|十分|非常|极其)(愤怒|震惊|尴尬|高兴|悲伤|害怕|激动|感动|紧张|慌张|恐惧|绝望)"
PSYCH_V2 = re.compile(r"""(?:
        他想|她想|它想|他想道|她想到|
        他觉得|她觉得|他觉得到|
        他心想|她心想|他暗想|她暗想|暗想|
        他忽然想|她忽然想|他想到|她想到|
        心里一|心中一|心里有|心中有|心里|心中|心底|
        心知|心里清楚|心里明白|
        他明白|她明白|他知道|她知道|他意识到|她意识到|
        他发觉|她发觉|他感到|她感到|她感觉|他感觉|
        他琢磨|她琢磨|他盘算|她盘算|他寻思|她寻思|
        他记起|她记起|他想起|她想起|他回忆|她回忆|回忆起|
        他忽然明白|她忽然明白|他忽然发现|她忽然发现|他忽然察觉|她忽然察觉|
        他愣住|她愣住|愣了|怔住|怔了|一怔|一愣|
        他犹豫|她犹豫|犹豫了|迟疑|迟疑了|
        他怀疑|她怀疑|怀疑是|他猜测|猜测是|
        他害怕|她害怕|他恐惧|恐惧感|不安|焦躁|烦躁涌|
        他期待|她期待|期待着|盼着|盼望|
        他后悔|她后悔|后悔了|懊悔|悔意|
        他松了口气|松了口气|松了一口气|心安|安心|
        他紧张|她紧张|紧张得|手心出汗|后背发凉|脊背发凉|寒意|
        他震惊|她震惊|震惊得|惊愕|愕然|骇然|
        他愤怒|怒意|怒火|火气涌|气得|
        他悲伤|悲从中来|鼻子一酸|眼眶|眼睛热了|喉咙发紧|喉头一哽|
        他欣慰|欣慰地|暖意|心头一暖|
        他叹|她叹|叹了口气|叹了一口气|叹息|
        默念|默想|心里默|心中默|
        他自问|她自问|自问|扪心自问|
        一个念头|闪过|掠过心头|涌上心头|浮上心头|
        他不确定|她不确定|拿不准|琢磨不透|想不通|想不明白|
        他隐约觉得|隐约感到|隐隐觉得|隐隐感到|总觉得|总觉得哪里|
        他生出一个|生出了一丝|涌起一丝|升起一丝|
        在他心底|在她心底|内心深处|深处有个声音|
        他问自己|她问自己|问自己
    )""", re.VERBOSE)


DASH_LIMIT = 3

# 题材阈值覆盖(磨刀十四批S7: 冷峻题材被市井阈值误伤——法医书冷读8/10但质量分表面指标吃亏)
# <书根>/题材配置.md 存在则覆盖默认: - 对话下限: 30 / 语气词下限: 3 / 心理下限: 2.0
import json as _json
def _load_profile(fp):
    """沿目录向上搜题材配置(磨刀十八批S7: 书根配置须对书根内任意章节生效,不限text/一级)"""
    prof = {}
    cur = pathlib.Path(fp).resolve().parent
    for _ in range(3):   # W6验证:原5层越过书根串他书配置(书根=text的父目录);text下最多2层到书根,3层兜底
        if (cur / "text" / ".modern").exists() and not MODERN_SETTING[0]:
            MODERN_SETTING[0] = True   # 红队一致性: text/.modern只有pipeline读,check裸跑曾误FAIL"电话"
        cfg = cur / "题材配置.md"
        if cfg.exists():
            for line in cfg.read_text(encoding="utf-8").splitlines():
                m = re.match(r"-\s*(对话下限|语气词下限|心理下限|质量线)\s*[:：]\s*([\d.]+)", line.strip())
                if m:
                    prof[m.group(1)] = float(m.group(2))
            break
        cur = cur.parent
        if cur == cur.parent:
            break
    return prof
          # 破折号 ——
SIMILE_LIMIT = 3        # 明喻
GATE_VERSION = 9        # 门版本号(W新批): 每次新增门+1;done --revise读scores里该章gate_version传--gate-ver,低于当前版的章对新门降WARN(grandfathering)
SYSTEM_LINE_LIMIT = 4
MIN_CHAPTER_CJK = 1800   # 缺陷9: 章字数硬线集中定义(原分散4文件)   # 【系统台词行
NAME = ""
SCENE_MODE = [False]               # 主角名(新案角色定稿后填入;留空则跳过人名密度检查)
MODERN_SETTING = [False]           # 现代都市背景(--modern 开关,关闭时代错位检查)


# ── 声纹表派生(禁硬编码人名,audits/21) ──
def _load_voice():
    vp = pathlib.Path(__file__).resolve().parent.parent / "story" / "20-人物" / "声纹表.md"
    names, bans = [], {}
    if vp.exists():
        for line in vp.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s.startswith("|") or re.match(r"^\|[-\s|:]+\|?$", s):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 6 and cells[0] not in ("人", "", "—") and len(cells[0]) <= 4:
                nm = cells[0].strip("*# ")
                names.append(nm)
                forbid = [w.strip() for w in re.split(r"[/、,，]", cells[5]) if w.strip() and w.strip() not in ("—", "无")]
                if forbid:
                    bans[nm] = forbid
    return names, bans
VOICE_NAMES, VOICE_BANS = _load_voice()

def cjk_len(text):
    return len(re.findall(r"[\u4e00-\u9fff]", text))

def check(fp: pathlib.Path, gate_ver=None):
    MODERN_SETTING[0] = False  # P2-019: 重置进程级状态(防多书泄漏)
    global _PROFILE
    _PROFILE = _load_profile(fp)
    raw = fp.read_text(encoding="utf-8-sig")
    # 卡派生字数带与峰章(audits/21-Fix6): 卡带=唯一权威
    _m = re.search(r"第(\d+)章", fp.name)
    _card_txt = ""
    if _m:
        # 卡目录双位探测: 主书=text/卡(历史),多书=书根/卡(skill_protocol gen card 落点)——20260917检修工005事故
        for _base in (fp.parent.parent, fp.parent.parent.parent):
            _hit = sorted(pathlib.Path(_base / "卡").glob(f"*第{_m.group(1)}章*.md"))
            if _hit:
                _card_txt = _hit[0].read_text(encoding="utf-8")
                break
    # 独角戏卡面豁免(红队20260919缺陷025): 场景型含 独白/追踪/潜行/闪回/冥想/灾变
    # → 门#16(对话占比)/#18(对话场景数)跳过,改用替代配额: 感官≥5/千字 + 心理≥3/千字
    _mono_hit = re.search(r"场景型[:：]\s*([^\n]+)", _card_txt)
    _mono_exempt = bool(_mono_hit and any(
        k in _mono_hit.group(1) for k in ("独白", "追踪", "潜行", "闪回", "冥想", "灾变")))
    _peak = "峰章" in _card_txt
    _band = re.search(r"字数带[:：]?\s*(\d{4})\s*[-—~至]\s*(\d{4})", _card_txt) or re.search(r"(?<!\d)([12]\d{3})\s*[-—~至]\s*([12]\d{3})(?!\d)(?!\s*年)", _card_txt)
    _lo = int(_band.group(1)) if _band else 2400
    _hi = (5200 if _peak else (int(_band.group(2)) if _band else 2800))
    lines = raw.splitlines()
    body_lines = [l for l in lines if l.strip() and not l.startswith("#")]
    body = "\n".join(body_lines)
    n = cjk_len(body)
    issues, warns = [], []
    metrics = {"file": str(fp), "cjk": n, "dia_line_pct": 0.0, "dia_char_pct": 0.0,
               "psych_per_k": 0.0, "hook_signals": 0, "dup18": 0}

    # 1) 字数(二十二条章长硬线: <1800禁止入库;1800-2300 WARN)
    if n == 0:
        issues.append("空文件")
    elif n < 1800 and not SCENE_MODE[0]:
        issues.append(f"章级字数{n}(<{MIN_CHAPTER_CJK}硬线)——骨架未回填,禁以成稿身份入库;走beat-expand血肉遍")
    elif n < _lo and not SCENE_MODE[0]:
        warns.append(f"章级字数偏少:{n}(卡带{_lo}-{_hi}{',峰章' if _peak else ''};场景文件用 --scene 免此项)")
    elif n > _hi and not SCENE_MODE[0]:
        warns.append(f"字数超限:{n}(卡带{_lo}-{_hi}{',峰章上限5200' if _peak else ''})")
    if SCENE_MODE[0] and n < 2200:
        warns.append(f"场景字数偏少:{n}(场景带2200-3200)")

    # 2) 禁词限额
    for w, lim in WORD_LIMITS.items():
        c = body.count(w)
        if w == "不是……而是":
            c = len(re.findall(r"不是[^。!?\n]{1,20}而是", body))
        if lim == 0 and c > 0:
            issues.append(f"禁用词「{w}」出现{c}次")
        elif c > lim:
            issues.append(f"「{w}」{c}次(上限{lim})")

    # 3) 禁句
    for s in BANNED_SENTENCES:
        if s in body:
            issues.append(f"禁句「{s}」")

    # 4) 破折号
    d = body.count("——")
    if d > DASH_LIMIT:
        issues.append(f"破折号{d}处(上限{DASH_LIMIT})")

    # 5) 明喻限额
    sim = 0
    # 红队香火城隍: "神像/图像/摄像/录像/影像/画像/想象"的"像"是名词语素,非明喻词——先剥除再计数
    _body_sim = re.sub(r"(神像|塑像|雕像|图像|摄像|录像|影像|画像|想象|像样|好像话)", "", body)
    _body_sim = re.sub(r"不像", "", _body_sim)  # 红队20260917: "不像X"是否定对比非明喻,误计入明喻限额
    _spans = set()
    for p in SIMILE_PATTERNS:
        for _m in re.finditer(p, _body_sim):
            _spans.add(_m.span())   # 跨模式去重: 同段文本被多模式重复计数(香火城隍事故)
    sim = len(_spans)
    if sim > SIMILE_LIMIT:
        issues.append(f"明喻{sim}处(上限{SIMILE_LIMIT})")

    # 6) 情绪告知
    m = re.findall(EMOTION_TELL, body)
    if m:
        issues.append(f"情绪告知式写法{len(m)}处(如'他很震惊',改用行为)")

    # 7) 系统台词行数
    sysl = [l for l in body_lines if l.strip().startswith("【")]
    if len(sysl) > SYSTEM_LINE_LIMIT:
        issues.append(f"系统台词{len(sysl)}行(上限{SYSTEM_LINE_LIMIT})")

    # 8) 段落开头重复(同两字开头≥4段)
    # 红队20260917阈值校准: 15章实测10章豁免=门失效。人名/称谓段首是中文叙事常态,
    # 阈值从4上调至7(主语型开头),疑问/对话引导词仍4(真雷同形状);豁免预算制的数据依据
    opens = {}
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    for p in paras:
        k = re.sub(r'[「"\'《*—…\s]', "", p)[:2]
        if len(k) == 2:
            opens[k] = opens.get(k, 0) + 1
    for k, c in sorted(opens.items(), key=lambda x: -x[1])[:3]:
        is_subject = bool(re.match(r"^[他她达周孙王刘张严胡温白老.{1,3}]{2}$", k))
        if c >= (7 if is_subject else 4):
            warns.append(f"段落开头「{k}…」{c}次(注意句式雷同)")

    # 9) 句长方差(反均匀;std<6 视为节奏单一)
    sents = re.split(r"[。！？\uFF01\uFF1F\n]", body)   # W6验证:缺全角！？→首句长度虚高
    slens = [cjk_len(s) for s in sents if cjk_len(s) > 0]
    if len(slens) >= 20:
        sd = statistics.pstdev(slens)
        if sd < 6:
            warns.append(f"句长方差过小({sd:.1f}),节奏太均匀")

    # 10) 高频四字重复(n-gram)
    clean = re.sub(r"[^\u4e00-\u9fff]", "", body)
    grams = {}
    for i in range(len(clean) - 3):
        g = clean[i:i+4]
        grams[g] = grams.get(g, 0) + 1
    top = sorted(grams.items(), key=lambda x: -x[1])[:5]
    rep = [(g, c) for g, c in top if c >= 4]
    if rep:
        warns.append("高频四字串:" + ", ".join(f"{g}×{c}" for g, c in rep))

    # 11) 主角名密度(每千字>12 提醒;NAME为空则跳过)
    if NAME and n:
        dn = body.count(NAME) / n * 1000
        if dn > 12:
            warns.append(f"「{NAME}」密度{dn:.1f}/千字,偏高")

    # 12) 自我评价词(禁自笑/禁自评,文笔论五)
    for w in SELF_PRAISE:
        c = body.count(w)
        if c > 0:
            issues.append(f"自评词「{w}」{c}次(写效果,不写评价)")

    # 13) 段落长度方差(反匀速+反AI指纹,白金标准>50)
    #     红队20260918: AI生成文本段长方差普遍<25=平台AI检测高风险;阈值从20→35(WARN)/25(FAIL)
    #     磨刀七批: WARN阈值可配(audit/gate-tuning.json的variance_warn)——waiver高频项升级为书级参数
    _VAR_WARN = 35
    try:
        _cur13 = pathlib.Path(p).resolve().parent
        for _ in range(4):
            _tf13 = _cur13 / "audit" / "gate-tuning.json"
            if _tf13.exists():
                _VAR_WARN = float(json.loads(_tf13.read_text(encoding="utf-8")).get("variance_warn", 35)); break
            _cur13 = _cur13.parent
    except Exception:
        pass
    plens = [cjk_len(p) for p in paras]
    if len(plens) >= 12:
        psd = statistics.pstdev(plens)
        if psd < 25:
            issues.append(f"段落长度方差{psd:.0f}(<25=AI指纹高危:平台AI检测将标记;白金参考>50)——长段(80-200字)约占段落10-15%+超短段3-5个")
        elif psd < _VAR_WARN:
            warns.append(f"段落长度方差{psd:.0f}(<{_VAR_WARN:.0f}=偏AI指纹;白金参考>50)——注意长短段错落")

    # 14) 对话占比(场景化率代理,布防总表B4)
    dl = [l for l in body_lines if ('"' in l or '\u201c' in l or '「' in l or '\u201d' in l or l.strip().startswith('"'))]
    if body_lines:
        ratio = len(dl) / len(body_lines)
        metrics["dia_line_pct"] = round(ratio * 100, 1)
        if ratio < 0.10:
            warns.append(f"对话行占比{ratio:.0%}(<10%),场景化不足/平铺直叙风险")
        elif ratio > 0.75:
            warns.append(f"对话行占比{ratio:.0%}(>75%),叙述过少(像剧本不像小说)")

    # 15.5) 章内重复跨度(≥18字原样重复=补丁残留/AI复读) v2:去重叠+计数校准
    clean2 = re.sub(r"\s+", "", body)
    # 叠句豁免:⟪⟫内为刻意反复(如服务标准化问候),不参与原样重复计数
    clean2 = re.sub(r"⟪[^⟫]*⟫", "", clean2)
    seen, dup_set = set(), set()
    i = 0
    while i < len(clean2) - 18:
        span = clean2[i:i+18]
        if span in seen:
            dup_set.add(span)
            i += 18  # 跳过一个窗口长度去重叠
        else:
            seen.add(span)
            i += 1
    if len(dup_set) >= 2:
        metrics["dup18"] = len(dup_set)
        issues.append(f"章内原样重复{len(dup_set)}处(首处:「{sorted(dup_set)[0][:18]}…»)——补丁残留或复读,必须整体重写")
    elif len(dup_set) == 1:
        metrics["dup18"] = 1
        warns.append(f"章内原样重复1处(「{list(dup_set)[0][:18]}…」)——检查是否补丁残留")

    # 14.4) 装饰性修辞总密度 v2:去除与#5重复计算的模式,只加新出现的
    sim_extra = 0  # P1-018: SIMILE_PATTERNS已覆盖宛如/恍若,不重复计数
    for pat in [r"宛如", r"恍若"]:  # 观察口径:SIMILE_PATTERNS已含二者,W6验证双计——不再计入FAIL
        sim_extra += len(re.findall(pat, body))
    personif = len(re.findall(r"[推拉扛拽]着一?(?:一整个|整个)", body))
    if sim + personif > SIMILE_LIMIT:
        issues.append(f"装饰性修辞{sim+personif}处(明喻{sim}+拟人{personif},上限{SIMILE_LIMIT})——AI标志:每个描写点挂比喻;真实作者白描为主")

    # 14.5) 工程词泄漏(正文出现元层词汇=脱稿事故)
    META_WORDS = ["细纲", "情节点", "场景卡", "伏笔编号", "beat", "BEAT", "本章hook", "爽点数", "主角光环", "金手指设定"]
    meta_hits = [w for w in META_WORDS if w in body]
    if meta_hits:
        issues.append(f"工程词泄漏:{','.join(meta_hits)}(正文出现元层词汇)")

    # 14.6) 末尾截断(章节以未完结标点收束)
    tail_char = body.rstrip()[-1] if body.rstrip() else ""
    if tail_char in "，，、：（(":
        issues.append(f"疑似末尾截断(结尾字符「{tail_char}」)")

    # 14.7) 碎片化(连续6段≤8字,语料校准:短句是重拍工具不是默认)
    frag = 0; max_frag = 0
    for para in paras:
        if len(re.sub(r"\s", "", para)) <= 8:
            frag += 1; max_frag = max(max_frag, frag)
        else:
            frag = 0
    if max_frag >= 6:
        warns.append(f"碎片化:连续{max_frag}段极短段(叙述应以长句为主,短句是重拍)")

    # 15) 章末总结腔(最后300字,布防总表A5)
    tail = body[-300:]
    for w in ENDING_SUMMARY_WORDS:
        if w in tail:
            warns.append(f"章末300字出现总结腔词「{w}」(章末只许钩子或余韵)")

    # 16) 对话字数占比(口径: 对白段整段/全文——织毛衣语义,台词+引导+段内动作线;
    #     45章实测中位50%,min33% → FAIL<35/WARN<40 与历史验收水平一致)
    # 16) 对话字数占比(口径: 对白段整段/全文——织毛衣语义,台词+引导+段内动作线;
    #     45章实测中位50%,min33% → FAIL<35/WARN<40 与历史验收水平一致)
    # 20260917: 群消息【】行也算对话(检修工/群聊流适配)
    _para_list = [pp.strip() for pp in re.split(r"\n\s*\n", raw) if pp.strip()]
    dialog_chars = sum(cjk_len(pp) for pp in _para_list if "\u201c" in pp or re.match(r"^【[^】]+】", pp))
    if n > 500:
        dpct = dialog_chars / n * 100
        metrics["dia_char_pct"] = round(dpct, 1)
        _dia_fail = _PROFILE.get("对话下限", 35)
        if _mono_exempt:
            warns.append(f"独角戏章型(卡面场景型豁免):门#16跳过,当前对话占比{dpct:.0f}%——替代配额见#17/#44b")
        elif dpct < _dia_fail:
            issues.append(f"对话字数占比{dpct:.0f}%(<{_dia_fail:.0f}%,严重不足:角色必须开口说话!)")
        elif dpct < 40:
            warns.append(f"对话字数占比{dpct:.0f}%(<40%,偏低:目标40-55%;角色要多说话说废话说长话)")

    # 17) 心理活动密度(用户标准:每千字≥2处心理beat)
    # 已知局限:本检查基于标记词(心里/觉得/寻思…),而风格包v6提倡的'心理裸写'常无标记词
    # (如'不能说。打死也不能说。')——裸写密度靠冷读与场景验收人工判定,此处仅测下限
    # v2: 大幅扩充词表——覆盖身体反应/情绪动词/内心独白/记忆闪回/决策犹豫
    psych_pats = PSYCH_V2.pattern
    psych_count = len(re.findall(psych_pats, body, re.VERBOSE))
    if n > 800:
        psych_per_k = psych_count / n * 1000
        metrics["psych_per_k"] = round(psych_per_k, 2)
        _psy_warn = _PROFILE.get("心理下限", 2.0)
        if _mono_exempt:
            # 独角戏章替代配额(025): 心理≥3/千字(替代对话密度)
            if psych_per_k < 1.5:
                issues.append(f"独角戏章心理活动{psych_per_k:.1f}/千字(<1.5,豁免章硬线:≥3.0/千字——独角戏全靠心理与感官撑)")
            elif psych_per_k < 3.0:
                warns.append(f"独角戏章心理活动{psych_per_k:.1f}/千字(<3.0,豁免章替代配额)")
        elif psych_per_k < 0.5:
            issues.append(f"心理活动{psych_count}处({psych_per_k:.1f}/千字,<0.5/千字,严重缺失:白金作家≥2/千字)")
        elif psych_per_k < _psy_warn:
            warns.append(f"心理活动{psych_count}处({psych_per_k:.1f}/千字,<2.0/千字,偏少)")

    # 18) 对话场景数(≥2个独立对话场景)
    paras_all = [p.strip() for p in body.split("\n") if p.strip()]
    dialog_scenes = 0
    in_dialog = False
    for p in paras_all:
        has_q = '"' in p or '\u201c' in p or '\u300c' in p
        if has_q and not in_dialog:
            dialog_scenes += 1
            in_dialog = True
        elif not has_q and in_dialog:
            in_dialog = False
    if dialog_scenes < 2 and n > 800 and not _mono_exempt:
        issues.append(f"对话场景仅{dialog_scenes}个(<2,章内须至少2个独立对话场景;独角戏章型按卡面豁免)")

        # 19) 英文残留(连续≥3个拉丁字母)——.modern存在时跳过(科幻/现代书允许英文术语)
    if not MODERN_SETTING[0]:
        eng = re.findall(r"[A-Za-z]{3,}", body)
        if eng:
            issues.append(f"英文残留:{','.join(eng[:3])}(正文不得出现拉丁字母词)")


    # 20) 流水账叙述检测(段落开头=人名+叙述动词,连续≥3段)
    flow_starts = 0
    max_flow = 0
    flow_names = "|".join(VOICE_NAMES + ["他", "她"]) if VOICE_NAMES else "他|她"
    flow_verbs = "去|到|查|发现|找|来|回|带|递|收|写|看|听|等|送|拿|走|说|问|翻|拆|试|开"
    for p in paras_all:
        if re.match(rf"^({flow_names})({flow_verbs})", p):
            flow_starts += 1
            max_flow = max(max_flow, flow_starts)
        else:
            flow_starts = 0
    if max_flow >= 5:
        warns.append(f"流水账风险:连续{max_flow}段以'人名+动词'开头(注意用对话/白描/心理打断叙述)")

    # 21) 时代错位词(现代/外文混入正文;--modern 跳过——现代背景专用)
    if not MODERN_SETTING[0]:
        MODERN_HARD = ["手机", "电脑", "电视", "地铁", "超市", "电梯", "咖啡", "沙发"]   # 硬错位词
        MODERN_SOFT = ["照片", "电话", "公园", "公交", "卡车"]   # 民国合法词(W6验证:公园/照片晚清民国存在,FAIL冤枉)
        for w in MODERN_HARD:
            if w in body:
                issues.append(f"时代错位词「{w}」(古代背景不得出现现代词汇)")
                break
        else:
            # 20260919磨刀批: 书内年代锚定豁免——正文自含1990s锚(年份/个体户/粮票/国营/万元户)时,
            # 电话/照片/公园等民国延续词为合法,不再空转WARN(21章实测此WARN 100%靠waivers销账)
            _era_anchored = re.search(r"(19[0-9]{2}年|个体户|粮票|国营|万元户|供销社|信用社)", body)
            if not _era_anchored:
                for w in MODERN_SOFT:
                    if w in body:
                        warns.append(f"疑似时代错位词「{w}」(晚清民国可合法,按本书年代自检)")
                        break

    # 22) 角色语音同质化检测 + 23) 声纹禁词(从死代码中恢复)
    speaker_sents = {}
    current_speaker = None
    speaker_pats = {nm: nm for nm in VOICE_NAMES}
    for p in paras_all:
        for sp, pat in speaker_pats.items():
            if re.search(pat, p):
                current_speaker = sp
                break
        if current_speaker and ('"' in p or '\u201c' in p):
            quotes = re.findall(r'["\u201c]([^"\u201d]+)["\u201d]', p)
            for q in quotes:
                speaker_sents.setdefault(current_speaker, []).append(q)

    if len(speaker_sents) >= 2:
        lengths = {}
        for sp, qs in speaker_sents.items():
            all_q = "".join(qs)
            sents = [s for s in re.split(r"[。!?\n]", all_q) if len(s.strip()) > 1]
            if len(sents) >= 3:
                lengths[sp] = sum(len(s) for s in sents) / len(sents)
        if len(lengths) >= 2:
            vals = list(lengths.values())
            spread = max(vals) - min(vals)
            if spread < 3:
                sp_names = ", ".join(f"{s}({v:.0f})" for s, v in sorted(lengths.items(), key=lambda x: x[1]))
                warns.append(f"语音同质化:各角色平均句长差距仅{spread:.1f}字({sp_names})——角色对话须有声纹差异")

    # 23) 声纹禁词检测(角色说了不该说的话——降为WARN,允许"故意违例"的喜剧手法)
    for sp, bans in VOICE_BANS.items():
        in_sp = False
        narrative_run = 0
        for p in paras_all:
            # 检测到其他角色标签时重置
            for other_sp, other_pat in speaker_pats.items():
                if other_sp != sp and re.search(other_pat, p):
                    in_sp = False
                    break
            else:
                if re.search(speaker_pats.get(sp, sp), p):
                    in_sp = True
                # 连续2段无引号也重置(说话人已离场)
                if in_sp and ('"' not in p and '\u201c' not in p):
                    narrative_run += 1
                    if narrative_run >= 2:
                        in_sp = False
                elif '"' in p or '\u201c' in p:
                    narrative_run = 0
            if in_sp and ('"' in p or '\u201c' in p):
                for ban in bans:
                    if ban in p:
                        warns.append(f"声纹违例:「{sp}」说了禁词「{ban}」(若为故意喜剧手法可登记豁免)")
                        in_sp = False
                        break

    # 24) 宣言密度检测 v2:收窄词表(去家常词)+修阈值
    declaim_pats = r'["\u201c][^"\u201d]{0,20}(?:永远|从不|绝不|子子孙孙|世世代代|总有一天|这笔账.{0,6}讨到底)(?:[^"\u201d]*)["\u201d]'
    declaims = len(re.findall(declaim_pats, body))
    if declaims > 3:
        warns.append(f"宣言式对白{declaims}处(>3,红队18:126章过载)")

    # 25) 三连排比检测 v3:只检测"重复词头"式排比(A，A，A式)而非任意三逗号
    triples = len(re.findall(r'(怕[^，。]{1,6})，(怕[^，。]{1,6})，(怕[^，。]{1,6})', body))
    triples += len(re.findall(r'(他[^，。的]{1,4})，(他[^，。的]{1,4})，(他[^，。的]{1,4})[^，。]', body))
    triples += len(re.findall(r'(她[^，。的]{1,4})，(她[^，。的]{1,4})，(她[^，。的]{1,4})[^，。]', body))
    if triples > 1:
        warns.append(f"重复词头三连排比{triples}处(>1,句式固化:怕X怕Y怕Z/他A他B他C)")

    # 26) 独白长度检测 v2:统一口径为100字
    long_speeches = 0
    for m in re.finditer(r'["\u201c]([^"\u201d]{100,})["\u201d]', body):
        long_speeches += 1
    if long_speeches > 2:
        warns.append(f"超长独白{long_speeches}处(单轮>100字——对话变演讲,红队18)")

    # 27) "如你所知"式设定伪装(红队G:信息倾倒的对话化伪装,FAIL)
    info_dumps = re.findall(r'如你所知|众所周知[，,]|想必你已|你应该知道|说来话长[，,]|简单来说', body)
    if info_dumps:
        issues.append(f"设定伪装对话{len(info_dumps)}处(「如你所知」式——设定必须挂在当前麻烦上进场,禁百科式转述,红队G)")

    # 28) 心动场景死喻(红队I禁喻清单:只许动作/物证/沉默三载体)
    dead_metaphors = re.findall(r'月光如水|星辰满天|心跳加速|心跳如鼓|脸颊绯红|手心出汗|心里某处.{0,2}柔软|漏跳了一拍', body)
    if dead_metaphors:
        warns.append(f"心动死喻{len(dead_metaphors)}处({','.join(dict.fromkeys(dead_metaphors[:3]))})——换动作/物证/沉默三载体,红队I")

    # 29) 首句长度(红队E转换规则1:第一句≤10字,扔事件碎片不递画面)
    if body_lines:
        first_sent = re.split(r'[。！？\uFF01\uFF1F\n]', body_lines[0])[0]
        fl = cjk_len(first_sent)
        if fl > 25:
            warns.append(f"首句{fl}字(>25,白金开篇首句≤10字碎片式:『头七,第三夜。』式,不递画面扔事件)")

    # 30) 感叹号温差(红队E:冷叙述+热对白;叙述段感叹号占比过高=失去温差)
    dia_ex = sum(p.count('！') + p.count('!') for p in paras_all if ('"' in p or '\u201c' in p))
    nar_ex = sum(p.count('！') + p.count('!') for p in paras_all if ('"' not in p and '\u201c' not in p))
    if nar_ex > dia_ex and nar_ex > 3:
        warns.append(f"感叹号温差倒挂:叙述段{nar_ex}个 vs 对话段{dia_ex}个——感叹号应集中对话与情绪峰值,叙述保持句号(冷面)")

    # 30b) 爽感扩散门(用户战略纠偏20260917:"索然无味弃书"——爽点兑了没人围观=白爽)
    # 病灶实证: 卷一15章REACT词仅12处(0.8/章)。爽=主角赢+别人震惊,只写前半=温吞死
    # 词表双轨: 网络腔(震惊/轰动)+年代文生活腔(传开/茶馆/井台/拍大腿/念叨)——20260917二修
    _react_pat = re.compile(r"震惊|惊呆|哗然|炸了|轰动|全县|传遍|议论|傻眼|服了|倒吸|看傻|围观|打听|排队|传开|念叨|指指点点|拍大腿|将信将疑|看热闹|酒桌|茶馆|井台|人人皆知|跟着激动|一家传")
    _react_n = len(_react_pat.findall(body))
    metrics["react_density"] = round(_react_n * 1000 / max(cjk_len(body), 1), 2)
    if _react_n * 1000 / max(cjk_len(body), 1) < 1.0:
        issues.append(f"爽感扩散密度{metrics['react_density']}/千字(<1.0=温吞红线)——爽点兑现处必须有人围观/震惊/传开,装逼没人看=白装(卷一15章实测0.4/千字=索然无味根因)")

    # 30c) 转折密度门(同上:每章≥2次价值翻转,只装1事件的"全流程章"=又短又慢)
    _flip_pat = re.compile(r"(?<![冷推忘罢了])却(?!于)|竟然|忽然|没想到|谁知|反倒|一夜之间")   # W6验证:裸"却"匹配冷却/推却灌水flip
    _flip_n = len(_flip_pat.findall(body))
    metrics["flips"] = _flip_n
    if _flip_n < 2:
        issues.append(f"转折密度{_flip_n}处(<2=单事件流水章)——每章至少2次价值翻转,beats设计需含反转拍")

    # 31) 章末钩子存在性(红队D:末三行决定追读,情绪最高点切断)
    tail_lines = [l for l in body_lines[-3:] if l.strip()]
    tail_joined = "".join(tail_lines)
    hook_signals = re.findall(r'[？?！!]|——|…|突然|忽然|就在这时|却见|赫然|竟是|竟然|一声|来了|开门|转身', tail_joined)
    # 屏面语:末三行含≤10字重音段(单句成段=重音)也算钩信号
    if not hook_signals and any(cjk_len(l) <= 10 for l in tail_lines):
        hook_signals = ['<短句重音>']
    metrics["hook_signals"] = len(hook_signals)
    if tail_joined and not hook_signals:
        warns.append("章末钩子信号缺失(末三行无悬念/中断/情绪峰值信号——最后三行决定读者去留,红队D)")

    # 32) 圆满收束检测(红队D弃书首因:主角安全脱险读者心满意足就不会点下一章)
    tail200 = body[-200:]
    tidy_endings = re.findall(r'从此|尘埃落定|落下帷幕|安心地|放下心来|一切归于|终于平静|沉沉睡去', tail200)
    if tidy_endings:
        warns.append(f"章末圆满收束信号{len(tidy_endings)}处(「{tidy_endings[0]}」)——爽完必须留新悬念,禁心满意足式结尾,红队D")

    # 33) 对话节奏违例(红队C:每3-5句台词+1段动作/心理,连续>6轮纯对话=喘不过气)
    pure_dia_run = 0; max_dia_run = 0
    for p in paras_all:
        if ('"' in p or '\u201c' in p) and cjk_len(p) < 60:
            pure_dia_run += 1
            max_dia_run = max(max_dia_run, pure_dia_run)
        else:
            pure_dia_run = 0
    if max_dia_run > 6:
        warns.append(f"连续{max_dia_run}轮纯对话(>6,每3-5句台词应插入动作/心理描写——织毛衣法,红队C)")

    # 34) 直引号(正文对白必须用中文弯引号;直引号会污染对话占比等指标,audits/06;U+FF02变体audits/13)
    straight_q = body.count('"') + body.count("\uFF02")
    if straight_q > 0:
        issues.append(f"直引号{straight_q}处(含全角变体＂;对白必须用中文引号“”;先跑 python3 tools/fix_quotes.py)")

    # ── 生活气正向刻度(audits/16 R1-R8, audits/17十六~二十条, audits/19病灶②③④⑥) ──
    # 35) 物价在场律: 具体金额≥2处且场景够长(短于800字的场景豁免,由章长硬线兜底)
    #     口径: 中文/阿拉伯数字+货币单位(块元毛千万),覆盖"九千/两万八/两块五"式;排除时间量词
    if n >= 800:
        # 红队长生炉工: 货币单位表原只有块元毛,古代书的两/贯/文/石永计0——扩古代币种
        _mhits = re.findall(
            r"[一两二三四五六七八九十百千]{1,10}(?:千|万|块|元|毛|两|贯|文|石)[一两二三四五六七八九十百零点五]{0,8}"
            r"|\d+(?:\.\d+)?(?:块|元|毛|两|贯|文)", body)
        _mhits = []
        for h in re.findall(
            r"[一两二三四五六七八九十百千]{1,10}(?:千|万|块|元|毛|两|贯|文|石)[一两二三四五六七八九十百零点五]{0,8}"
            r"|\d+(?:\.\d+)?(?:块|元|毛|两|贯|文)", body):
            if "千万" in h:
                continue
            _after = body[body.find(h) + len(h):body.find(h) + len(h) + 2]   # W10: 排除词看命中串后文("三千年"后是年=时间)
            if re.match(r"年|月|日|次|遍|岁|分钟|度|号|名|个|位|回|斤|亩", _after):
                continue
            _mhits.append(h)
        money = len(_mhits)
        metrics["money_sample"] = ",".join(_mhits[:6])
        metrics["money_count"] = money
        if money == 0:
            issues.append("金额/物价0处(须≥2,至少1处参与情绪运算)——穷人的钱不经过手=生活气缺失第一现场(audits/16 R3)")
        elif money < 2:
            warns.append(f"金额/物价仅{money}处(目标≥2)——优先消耗story/素材库.md条目")

    # 36) 模糊时长(时间刻度律): "很久很久"类禁超1处
    fuzzy_dur = len(re.findall(r"很久很久|不知过了多久|过了很久|许久", body))
    metrics["fuzzy_duration"] = fuzzy_dur
    if fuzzy_dur > 1:
        issues.append(f"模糊时长词{fuzzy_dur}处(>1)——等待必须被度过:换算成秒/圈数/一支烟(audits/16 R4)")

    # 37) "不是X。是Y。"句号变体(旧检测只匹配"而是",卷3起全部句号变体逃逸,audits/19病灶⑥)
    period_var = len(re.findall(r"不是[^。!?\n]{1,14}[。\n]\s{0,2}[^。!?\n]{0,6}是", body))
    metrics["bushi_shi"] = period_var
    if period_var > 2:
        issues.append(f"「不是X。是Y。」句式{period_var}处(>2)——句式指纹,改写或删")

    # 38) 身体贴纸与情绪命名(情绪位移律)
    stickers = len(re.findall(r"喉结动|指节(发白|攥白)|腿一(下)?软|眼眶(一)?(下)?就?热|眼泪哗|浑身僵", body))
    metrics["body_stickers"] = stickers
    if stickers > 2:
        issues.append(f"身体贴纸式反应{stickers}处(>2)——身体要长在事件上(包子渣掉一裤子式),不是贴此处应有反应")
    emo_name = len(re.findall(r"(?<![要会能])是(恐惧|心疼|愤怒|悲伤|绝望|委屈)(?![的了])", body))
    if emo_name > 1:
        issues.append(f"情绪直接命名{emo_name}处(>1)——写位移(掐大腿/算账),不写结论")

    # 39) 感叹号温差(零感叹号=全冷,076-079实测全零,audits/17温差律盲区)
    ex_total = body.count("！") + body.count("!")
    metrics["exclamations"] = ex_total
    dia_ratio = metrics.get("dia_line_pct", 0)
    if ex_total == 0 and dia_ratio >= 30 and n >= 1500:
        warns.append("全章零感叹号(温差全冷)——热峰值应集中在对话与情绪拍,至少1处(口语密度律)")

    # 40) 章末形态指纹(末3行≥2个≤12字独立段=「短句重音型」,audits/19病灶①:check曾奖励此指纹)
    tail3 = [l for l in body_lines[-3:] if l.strip()]
    short_tail = sum(1 for l in tail3 if cjk_len(l) <= 12)
    shape = None
    if len(tail3) >= 2 and short_tail >= 2:
        shape = "短句重音"
    elif tail3 and ("\u201c" in tail3[-1] or '"' in tail3[-1]):
        shape = "对话切"
    elif tail3 and ("——" in tail3[-1] or "…" in tail3[-1] or "？" in tail3[-1] or "?" in tail3[-1]):
        shape = "悬置"
    else:
        shape = "叙述收"
    metrics["ending_shape"] = shape
    metrics["ending_tail"] = "|".join(t.strip()[:20] for t in tail3[-2:])

    # 41) 闲笔存在性(每章≥1处与主线无关但含具体名词的长段——启发式:含具体名词且含数字/物价的非任务段)
    has_idle = False
    idiom_pat = re.compile(r"\d|块|元|毛")
    task_pat = re.compile(r"计划|部署|收网|调查|证物|维修|柜台|收货|翻新|进货|拆机")
    for p in paras:
        if 50 <= cjk_len(p) and idiom_pat.search(p) and not task_pat.search(p):
            has_idle = True
            break
    metrics["idle_beat"] = 1 if has_idle else 0

    # 48) 对白语气词密度(大审计-28: 每个人说话都很装——缺语气词=机器对白)
    _tl_words = ["啊","呗","嘛","呃","那啥","反正","横竖","得嘞","嗯","哦","啦","呀","咧","哩","得了","行了","算了吧","咋"]
    _dialogue_text = "".join(re.findall(r"\u201c([^\u201d]*)\u201d", body))
    _dl = cjk_len(_dialogue_text)
    _tl_count = sum(_dialogue_text.count(w) for w in _tl_words)
    if _dl > 200:
        tl_per_k = round(_tl_count / _dl * 1000, 1)
        metrics["tl_per_k"] = tl_per_k
        _tl_floor = _PROFILE.get("语气词下限", 3)
        if tl_per_k < _tl_floor:
            issues.append(f"对白语气词密度{tl_per_k}/千字(<3=严重不足:机器对白)——每段对话至少一个啊/呗/嘛/那啥(dialogue-voice)")
        elif tl_per_k < max(_tl_floor * 3, 6):
            warns.append(f"对白语气词密度{tl_per_k}/千字(<{_tl_floor * 3:.0f})——对白偏干净,多加语气词/口头禅(dialogue-voice)")

    # 49) 对白完整句率(大审计-28: 碎片化不足=机器对白)
    if _dl > 200:
        _dl_sents = [s.strip() for s in re.split(r"[。！？]", _dialogue_text) if s.strip()]
        if _dl_sents:
            _complete = sum(1 for s in _dl_sents if len(s) >= 8 and re.match(r"^[我你他她它咱]", s))
            _frag_rate = round((1 - _complete / len(_dl_sents)) * 100, 1)
            metrics["dialogue_frag_rate"] = _frag_rate
            if _frag_rate < 20:
                warns.append(f"对白完整句率{_frag_rate}%碎片率(<20%碎片=太工整)——加省略主语/断句/只说半句(dialogue-voice)")

    # 50) 对白抽象名词密度(大审计-28: 哲理化对白=机器指纹)
    _abstract = ["道理","规矩","命运","人生","本事","选择","道理","底线","原则","出路","前景","格局","心态","境界"]
    _abs_count = sum(_dialogue_text.count(w) for w in _abstract)
    if _dl > 300:
        abs_per_k = round(_abs_count / _dl * 1000, 1)
        metrics["dialogue_abs_per_k"] = abs_per_k
        if abs_per_k > 12:
            issues.append(f"对白抽象名词密度{abs_per_k}/千字(>12=哲理化对白)——改成具体的事/钱/人名(dialogue-voice #50)")
        elif abs_per_k > 8:
            warns.append(f"对白抽象名词密度{abs_per_k}/千字(偏高)——少讲道理多讲事(dialogue-voice)")

    if n >= 1500 and not has_idle:
        pass  # 闲笔检查已在上方

    # 53) 无冲突检测(大审计-28根因; 审计-32: 旧词表含"但是/问题/急"高频词+any()恒真=死检查,改强词计数)
    _conflict_words = ["不行","反对","不同意","拒绝","不要","不能","失败","坏了","出事","办不成","没成","驳回","拦住","堵回","翻脸","谈崩","闹翻","卡住","凑不出","拿不出","交不起","还不上","挡驾","顶回","挑刺","堵门","回绝","作梗","刁难","使绊","落空","攥出褶","没落","对簿","失态"]
    _conflict_cnt = sum(body.count(w) for w in _conflict_words)
    metrics["conflict_hits"] = _conflict_cnt
    if n >= 1500 and _conflict_cnt == 0:
        # 审计-32实测: 对赌/封锁/挖角等叙事式冲突不落词表(ch2/7/10/17/21/23全是强冲突章零命中)——语义判定归冷读,机器只降级提示
        warns.append("全章零强冲突词——正则判不了冲突存在性(叙事式冲突不落词),冲突是否成立交冷读/场景验收人工判")
    elif n >= 1500 and _conflict_cnt <= 2:
        warns.append(f"冲突词仅{_conflict_cnt}处——检查本章阻碍是否足够具体")

    # 52) 峰后解释检测(大审计-29最高优先: 峰后必释=杀掉心头一紧)
    # 检测: 情感词(疼/哭/暖/怕/红了/热了)出现在前一段,后一段含叙述者解释动词(想明白/知道/懂了/明白了/原来/这就叫/因为)
    _emo_words = ["疼","哭","暖","怕","红了","热了","酸","堵","紧","烫","湿"]
    _explain_words = ["想明白","知道了","懂了","明白了","原来","这就叫","因为","所以","这才","这叫","有一种账","一种说不清"," 一种说不出"]
    _paras_clean = [p.strip() for p in paras if p.strip()]
    _peak_explain = 0
    for _pi in range(len(_paras_clean)-1):
        _cur = _paras_clean[_pi]
        _next = _paras_clean[_pi+1]
        _has_emo = any(w in _cur for w in _emo_words)
        _has_explain = any(w in _next for w in _explain_words)
        _is_narr = "\u201c" not in _next
        if _has_emo and _has_explain and _is_narr:
            _peak_explain += 1
    metrics["peak_explain"] = _peak_explain
    if _peak_explain >= 2:
        pass  # 已有#52

    # 54) 章末金句门(大审计-31: 每章末作者出来总结=节律指纹)
    _last_3 = [p.strip() for p in paras[-3:] if p.strip()]
    _aphor_end = 0
    for _p in _last_3:
        if "\u201c" in _p:
            continue
        if re.search(r"(一种|这个|这叫|才是|就是|都得|都得|要?知道)[^。」』]{0,15}。\s*$", _p):
            _aphor_end += 1
        if re.search(r"[^。」』]{2,8}，[^。」』]{2,8}。\s*$", _p) and cjk_len(_p) < 30:
            _aphor_end += 1
    metrics["end_aphor"] = _aphor_end
    if _aphor_end >= 1 and any(w in "".join(_last_3) for w in ["明白","道理","认","守","懂"]):
        warns.append("章末疑似金句/主题句收尾——用动作/物件/对话替代(大审计-31)")

    # 55) 排比宣言收尾门(法医ch001事故: "证明了三件事:一…二…三…"逃过#52/#54双门)
    # 模式A: 末3段序数排比(一…二…三…/一是…二是…)
    # 模式B: 末3段自觉宣言(他不是那种X/他永远不会是/从这一刻起/再也不需要…才能)
    # 模式C: 末3段"证明了/说明了/意味着N个道理(事实)"句式
    _manifesto = 0
    for _p in _last_3:
        if "\u201c" in _p:   # 人物台词里的排比不判
            continue
        if re.search(r"(一[，是].{2,40}[二，][，是]?.{2,40}三[，是])", _p) or re.search(r"(一是.{2,40}二是.{2,40})", _p):
            _manifesto += 1
        if re.search(r"(证明了?|说明了?|意味着)[^。」』]{0,8}(一件|一个|三件|三个|两个|道理|事实)", _p):
            _manifesto += 1
        if re.search(r"(他|她)[^。」』]{0,6}不是那种[^。」』]{1,12}[。.]", _p):
            _manifesto += 1
        if re.search(r"(从(这|那)(一刻|一天|天起)|永远不会再|(再也不|不再)需要[^。」』]{0,10}才能)", _p):
            _manifesto += 1
    metrics["end_manifesto"] = _manifesto
    if _manifesto >= 2:
        issues.append(f"排比宣言收尾{_manifesto}处命中(>=2=FAIL)——末章作者代言总结/序数排比/自觉宣言,三连即AI腔铁证;峰后禁释令:收在动作/物件/对话,不收在道理")
    elif _manifesto == 1:
        warns.append("末3段含1处疑似宣言句式——检查是否作者越喉说话(人物台词内豁免)")

    # 56) 工程残渣门(法医ch001冷读事故: 18对反向弯引号+破句"嘴唇，，。"+单破折号残迹"角膜—,"
    # ——比文风问题更劝退,读者解读为"没人校过")
    _rq_lines = [l for l in raw.splitlines() if l.strip().startswith("\u201d")]
    _rq_mid = len(re.findall(r"[:：][\u201d]", raw))   # 段中 ':”' 冒号接右引号(ch042事故形状,正常应为:'“')
    if _rq_lines or _rq_mid:
        issues.append(f"引号方向违例(FAIL): 行首右引号{len(_rq_lines)}行+冒号接右引号{_rq_mid}处——运行 tools/fix_quotes.py 或人工修复")
    _brk = re.findall(r"[，。；：、]{2,}", body)
    _half_dash = re.findall(r"(?<!—)—(?!—)", body)
    metrics["broken_punct"] = len(_brk)
    metrics["half_dash"] = len(_half_dash)
    if _brk:
        warns.append(f"破句/连续标点{len(_brk)}处({';'.join(_brk[:3])})——编辑残渣,占位文本未清理干净")
    if _half_dash:
        warns.append(f"单破折号残迹{len(_half_dash)}处——中文破折号应为'——'双字符,单'—'多为删除残留")

    # 57) 稿面异物+引号平衡(大审计-32 N10/N11: 孤立标点段/跨段引号悬空——零误报FAIL)
    _orphan_punct = [pp for pp in paras if re.fullmatch(r"[，。！？…—、;；,]+", pp.strip())]
    if _orphan_punct:
        issues.append(f"孤立标点段{len(_orphan_punct)}个(FAIL)——纯标点单句成段=稿面异物(ch12/15/16事故形状)")
    _qbal, _qfirst = 0, None
    for _i, _pp in enumerate(paras):
        _qbal += _pp.count("\u201c") - _pp.count("\u201d")
        if _qbal != 0 and _qfirst is None:
            _qfirst = _i + 1   # 首个失衡段(正差=缺右引号起点,负差=多右引号)
    if _qbal != 0:
        _dir = "缺右引号" if _qbal > 0 else "多右引号"
        issues.append(f"引号不闭合(可能为合法跨段对白,检查格式): 净{_dir}{abs(_qbal)}个,首异常段第{_qfirst}段——跨段悬空引号(ch45事故形状)")

    # 63) 离场者发言门(大审计-32 N4: ch35"走了的老主顾又站回来说话"事故——对话空间连续性)
    # 通用捕获(不依赖名单——ch35事故主角"老主顾"正是无名配角);排除泛指主语
    _GENERIC_SUBJ = {"人们", "大家", "众人", "两人", "三人", "他们", "她们", "两人都", "所有"}
    _exit_re = re.compile(r"^([\u4e00-\u9fa5]{2,3})[^。！？]{0,8}?(走了|出去了?|离开了?|出门|下了楼|走了出去|起身离开|告辞)[。，]")
    _speak_re = re.compile(r"^([\u4e00-\u9fa5]{2,3})[^。！？]{0,8}?(说|道|问|答|喊|叫)[了着]?[，。：]")
    _back_re = re.compile(r"^([\u4e00-\u9fa5]{2,3})[^。！？]{0,8}?(回来|进门|返回|又来|折回|走回来)[。，]")
    _muted = {}
    for _pi, _pp in enumerate(paras):
        _m = _exit_re.match(_pp)
        if _m and _m.group(1) not in _GENERIC_SUBJ:
            _muted[_m.group(1)] = _pi
            continue
        _m = _back_re.match(_pp)
        if _m and _m.group(1) in _muted:
            _muted.pop(_m.group(1), None)
            continue
        _m = _speak_re.match(_pp)
        if _m and _m.group(1) in _muted:
            _gap = _pi - _muted[_m.group(1)]
            if _gap <= 10:
                issues.append(f"离场者发言(FAIL): {_m.group(1)}已于{_gap}段前离场却又开口(ch35事故形状)——要么让人物回来,要么删这段话")
                _muted.pop(_m.group(1), None)

    # 64) 章内时间跳跃检测(大审计-32 N5: ch8从6月15直接跳8月26无过渡;WARN级——回忆/口头交代会误报,交人工)
    _ts_pat = re.compile(r"([一二两三四五六七八九十\d]{1,3})月([一二两三四五六七八九十\d]{1,3})[日号]")
    _ts_points = []
    for _pi, _pp in enumerate(paras):
        if "\u201c" in _pp:
            continue   # 对话内提到的时间不算叙事时间轴
        _m = _ts_pat.search(_pp)
        if _m:
            try:
                _mo = int(_m.group(1)) if _m.group(1).isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}.get(_m.group(1), 0)
                _dy = int(_m.group(2)) if _m.group(2).isdigit() else {"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10,"三十一":31}.get(_m.group(2), 0)
                if 1 <= _mo <= 12 and 1 <= _dy <= 31:
                    _ts_points.append((_pi, _mo * 100 + _dy, f"{_mo}月{_m.group(2)}日"))
            except ValueError:
                pass
    _TRANSITION = ("转眼", "一晃", "入夏", "入秋", "开春", "月底", "月初", "过了半天", "两个月的", "一个月后", "半个月")
    for _a, _b in zip(_ts_points, _ts_points[1:]):
        _diff = (_b[1] // 100 - _a[1] // 100) * 30 + (_b[1] % 100 - _a[1] % 100)
        if _diff > 7 or _diff < -20:   # W5: 跨年(12月→1月)负差不报=漏检
            _between = "".join(paras[_a[0]:_b[0]])
            if not any(w in _between for w in _TRANSITION):
                warns.append(f"时间跳跃: {_a[2]}→{_b[2]}(跨{_diff}天)中间无过渡交代(审计-32 N5;回忆或对话已交代的登记waivers)")

    # 62) 拼装疤检测(大审计-32 N1: 同一场景两版并存仅换人名——"XX来送饭"双版本两次成灾,
    # 18字原样重复#15/Jaccard#46/G5/G8四门全漏; 方案=段首句名词槽归一化+骨架相似度)
    import difflib as _difflib
    from collections import Counter as _Cnt2
    _names = set()
    _vc = pathlib.Path(__file__).resolve().parent.parent / "story" / "60-圣经" / "声口卡.md"
    if _vc.exists():
        _names = {m.group(1).strip() for m in re.finditer(r"^##\s*(.+?)\s*$", _vc.read_text(encoding="utf-8"), re.M)}
        _names = {re.sub(r"（[^）]*）|\([^)]*\)", "", x) for x in _names}
    _names |= {"马小丁", "崔兰", "王大龙", "苏棠", "陈会计", "罗胖子", "丁师傅", "麻老五", "老拐", "秦见微"}
    def _slot_norm(s):
        for _nm in sorted(_names, key=len, reverse=True):
            s = s.replace(_nm, "⟨名⟩")
        return re.sub(r"[\s，。！？“”—、]", "", s)
    _first_sents = []
    for _pp in paras:
        # 开头句=到首个句读符(。！？：；)——ch42事故开头句以冒号接引语,split("。")会取整段被引号过滤漏掉
        _head = re.split(r"[。！？：；]", _pp)[0]
        _hc = cjk_len(_head)
        if 10 <= _hc <= 40:
            _first_sents.append(_slot_norm(_head))
    _first_raw = []
    for _pp in paras:
        _head = re.split(r"[。！？：；]", _pp)[0]
        _hc = cjk_len(_head)
        if 10 <= _hc <= 40:
            _first_raw.append(_head)
    _frank_pairs = []
    for _i in range(len(_first_sents)):
        for _j in range(_i + 1, len(_first_sents)):
            if abs(len(_first_sents[_i]) - len(_first_sents[_j])) > 6:
                continue
            _r = _difflib.SequenceMatcher(None, _first_sents[_i], _first_sents[_j]).ratio()
            if _r >= 0.72:   # 0.72+冒号截断+10字下限(审计-32调参:截断修复后短句不再撑爆样本)
                _frank_pairs.append((_r, _i, _j))
    metrics["assembly_detail"] = [(round(r, 2), _first_raw[i][:20], _first_raw[j][:20]) for r, i, j in _frank_pairs]
    metrics["assembly_pairs"] = len(_frank_pairs)
    _hard = [x for x in _frank_pairs if x[0] >= 0.9]   # 真双版本开头近乎逐字(ch42原版100%); 0.85下"看了X一眼"动作框架仍会87%误报
    _soft = [x for x in _frank_pairs if 0.72 <= x[0] < 0.9]
    if _hard:
        _worst = max(_hard)
        issues.append(f"拼装疤{len(_hard)}对(FAIL,最高相似{_worst[0]:.0%})——同一场景两版并存仅换人名(ch42崔兰戏事故形状);人工核对段首,留一版删其余")
    elif _soft:
        warns.append(f"段首句疑似复用{_soft[0][0]:.0%}(最高)——若为'看了X一眼'类动作框架复用可豁免,若为两版场景并存则清创")

    # 58) 群体情绪标注(大审计-32 N6/红队A5: "全院炸了/所有人都愣住了"——情绪标注的群体变体,#38单数式盲区)
    GROUP_EMO = re.compile(r"(全院|全场|满?[屋院堂室厂]子?|整个[屋院堂室厂]|所有人|众人|大家)[一瞬时都皆齐]{0,3}(炸了锅?|愣住[了]?|安静[了下]*[了几]?秒?|沉默[了]?|倒吸|哗然|沸腾|屏住|鸦雀无声)")
    _group_emo = len(GROUP_EMO.findall(body))
    metrics["group_emo"] = _group_emo
    if _group_emo >= 2:
        issues.append(f"群体情绪标注{_group_emo}处(>=2=FAIL)——'全院炸了/所有人都愣住了'是情绪告知的群体变体;写具体的人的具体反应")
    elif _group_emo == 1:
        warns.append("群体情绪标注1处(群像高潮场面可豁免,登记waivers)")

    # 59) 笑声标注公式(大审计-32 N7/红队A6: "被X逗笑了"=替笑点打分,解说笑点变体)
    LAUGH_PAT = re.compile(r"([被把][^，。！？\u201c\u201d]{1,6}逗[得的了]?笑了?|逗[得了]?[他她它众人][^，。]{0,6}笑了?)")
    _laugh = len(LAUGH_PAT.findall(body))
    metrics["laugh_tag"] = _laugh
    if _laugh >= 2:
        issues.append(f"笑声标注{_laugh}处(>=2=FAIL)——'被逗笑了'是解说笑点:删标注让下一句人物反应自己接住")
    elif _laugh == 1:
        warns.append("笑声标注1处(检查是否解说笑点)")

    # 60) 身体反应配额(大审计-32 N8: 同章同一身体仪表复用>=3次,如ch16手抖×4)
    BODY_PAT = re.compile(r"手[指腕]?[一又再都发直]?抖|指尖[发颤抖]|腿一?软|后背发?凉|鼻[子头]一酸|眼眶一?热|呼吸一滞|心口一?紧|胃里一沉|喉结滚动|攥[紧出]")
    from collections import Counter as _Counter
    # 归一化: 剥掉修饰助词(手一抖/手又抖/手发抖→手抖)——ch16事故正是靠变体措辞绕过同token判定
    _body_cnt = _Counter(re.sub(r"[一又再都直着了个]", "", m.group()) for m in BODY_PAT.finditer(body))
    _body_over = [f"{k}×{v}" for k, v in _body_cnt.items() if v >= 3]
    metrics["body_top"] = dict(_body_cnt.most_common(5))
    if _body_over:
        issues.append(f"身体反应复用(FAIL): {'、'.join(_body_over)}(同章同仪表>=3次)——身体反应轮换表:同一紧张仪表一章最多2次")

    # 61) Excel朗读腔(大审计-32 N12/红队确认: 报表数字成串朗读,ch45事故形状)
    _excel_hits = 0
    for _q in re.findall(r"\u201c([^\u201c\u201d]{20,})\u201d", body):
        _cl = [c for c in re.split(r"[。！？]", _q) if c.strip()]
        _numc = [c for c in _cl if cjk_len(c) <= 10 and re.search(r"(利|亏|赚|流水|合计|进账|出账|成本|单价)[^，。]{0,3}[一二两三四五六七八九十百千万零\d点]+|[一二两三四五六七八九十百千万零\d点]+[块元]", c)]
        if len(_numc) >= 4 or (len(_numc) >= 3 and "合计" in _q):
            _excel_hits += 1
    metrics["excel_dialog"] = _excel_hits
    if _excel_hits >= 1:
        issues.append(f"报表对白{_excel_hits}段(FAIL)——数字成串朗读=给对账程序看的数(ch45事故);真人只报总数+一个细节,其余进叙述")

    if _peak_explain >= 2:
        issues.append(f"峰后解释{_peak_explain}处(>=2=FAIL,大审计-29:峰后必释=杀掉心头一紧)——情感峰值后下一段必须是动作/物件/沉默,禁叙述者解释")

    # 51) 场景深度检测(大审计-28根因: 概述代替场景=读者无画面感)
    # 统计具体动作动词密度(拆/拧/按/推/焊/擦/切/倒/塞/挂/抽/掰/踹/拽/搓/抹/摁/戳)
    _action_verbs = ["拆","拧","按","推","焊","擦","切","倒","塞","挂","抽","掰","踹","拽","搓","抹","摁","戳","夹","舀","舖","搭","掰","拨"]
    _action_count = sum(body.count(v) for v in _action_verbs)
    action_per_k = round(_action_count / n * 1000, 1) if n > 0 else 0
    metrics["action_per_k"] = action_per_k
    if n >= 1500 and action_per_k < 5:
        warns.append(f"场景深度不足: 动作动词密度{action_per_k}/千字(<5)——概述代替了场景,读者无画面感(大审计-28根因)")
    if n >= 1500 and not has_idle:
        warns.append("未检出闲笔段(≥50字含具体名词且不挂任务词)——每章≥1处过日子内容(audits/16 R2,热粥案条款)")

    # 46) 近似重复(大审计-11:变体逃逸拼接残留)——段间shingle Jaccard>0.85=FAIL
    def _shingles(s, k=10):
        c = re.sub(r"⟪[^⟫]*⟫", "", s)  # 继承#15的⟪⟫刻意反复豁免(大审计-18 D4)
        c = re.sub(r"[\s，。！？；：、“”]", "", c)   # W6验证:原从原s重算覆盖⟪⟫剥除=豁免死亡
        return {c[i:i+k] for i in range(max(0, len(c)-k+1))}
    def _jac(a, b):
        u = len(a | b)
        return len(a & b) / u if u else 0.0  # 真Jaccard(大审计-18 D3: 原为重叠系数,度量错标)
    near_pairs = []
    for i in range(len(paras)):
        si = _shingles(paras[i])
        if len(si) < 3:
            continue
        for j in range(i+1, len(paras)):
            sj = _shingles(paras[j])
            if len(sj) < 3:
                continue
            j = _jac(si, sj)
            if j > 0.85:
                near_pairs.append((i, j, round(j, 2)))
    metrics["near_dup"] = len(near_pairs)
    if near_pairs:
        i, j, r = near_pairs[0]
        issues.append(f"近似重复段{len(near_pairs)}处(Jaccard={r})——变体拼接残留,必须整体清创(大审计-11 #46)")

    # 47) 金额算术器(大审计-11:钱面矛盾零机器)——同章同名科目出现两个不同值=FAIL
    import collections as _col
    _fig = re.compile(r"(流水|毛利|净利|净剩|基金|学费|房租|存款|货款|本金|账上)([一二三四五六七八九十百千两0-9点零]+)")
    def _zh2int(s):
        """中文口语数字→int; 末尾裸数字按最后单位升位(两千五=2500,与card_check.cn2num同口径,审计:两工具不一致致假阳假阴)"""
        s = s.strip()
        if not s:
            return None
        total, section, digit, has, last_unit, zero_pending = 0, 0, 0, False, None, False
        for ch in s:
            if ch == "零":
                zero_pending = True   # 两万零八=20008: 零后裸数字不升位(审计-32)
                continue
            if ch in "零一二两三四五六七八九":
                digit = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}[ch]
                has = True
            elif ch in "十百千万亿":
                u = {"十":10,"百":100,"千":1000,"万":10000,"亿":100000000}[ch]
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
            lift = 1 if zero_pending else {"万":1000, "千":100, "百":10}.get(last_unit, 1)
            section += digit * lift
        return total + section if (has or section) else None



    # 43) 段落形态刻度(红队20260918修复: 均值豁免长段,消除与门13互相否决的振荡)
    #     段均只对<80字段落计算(长段=蓄压工具,不计入日常节奏);长段配额从≤3放宽到≤12(80-200字区间)
    para_lens = [cjk_len(x) for x in paras]
    if para_lens:
        short_lens = [L for L in para_lens if L < 80]  # 豁免长段
        avg_pl = sum(short_lens) / max(len(short_lens), 1)
        long_n = sum(1 for L in para_lens if L >= 80)
        metrics["avg_para_len"] = round(avg_pl, 1)
        metrics["long_paras"] = long_n
        if avg_pl > 34:
            warns.append(f"短段均值{avg_pl:.0f}(<80字段均,规格≤30)——多留短句段")
        if long_n > 12:
            warns.append(f"长段{long_n}个(≥80字,规格≤12)——全章匀速感超标")

    # 44b) 感官词密度(深度AI检测核心特征,红队20260919):
    #      GPTZero/朱雀检测器重点特征——AI文本缺乏感官锚点,人类写作每千字≥5个感官词
    _sense_pat = re.compile(r"闻到|听到|看到|看见|摸|尝|烫|凉|冰|热|酸|甜|咸|涩|腥|刺鼻|刺眼|刺耳|粗糙|光滑|柔软|坚硬|油腻|干涩|潮湿|发霉|发馊|发烫|冰凉|滚烫|火辣|酥麻|发痒|发疼|扎手|硌手|硌牙|咯牙|呛|噎|腥味|糊味|焦味|烟味|土腥|铁锈味|汗味|药味|消毒水")
    _sense_n = len(_sense_pat.findall(body))
    metrics["sense_per_k"] = round(_sense_n * 1000 / max(cjk_len(body), 1), 1)
    _sense_floor = 5.0 if _mono_exempt else 3.0
    if n > 1200 and _sense_n * 1000 / max(cjk_len(body), 1) < _sense_floor:
        _mono_tag = "独角戏章替代配额" if _mono_exempt else "深度AI特征:缺乏感官锚点"
        warns.append(f"感官词密度{metrics['sense_per_k']}/千字(<{_sense_floor}={_mono_tag};人类白金>5)——每千字至少{int(_sense_floor)}个具体感官词(味/触/嗅/听,如'浆糊味''冰凉''硌手')")

    # 44c) 对话标签多样性(红队20260919: 连续"他说"=AI指纹)
    _tag_repeats = len(re.findall(r"他[说问道]”[^“]{0,50}“[^“]{0,50}”他[说问道]", body))
    _tag_he_shuo = len(re.findall(r"他说", body))
    metrics["said_count"] = _tag_he_shuo
    if _tag_he_shuo > 5 and n > 1000:
        warns.append(f"\"他说\"{_tag_he_shuo}次(>5=AI标签单调)——用动作/停顿/语气替代(把笔搁了/半天没吭声/应了一声)")
    if _tag_repeats and n > 1000:
        warns.append(f"连续\"他说\"往返{_tag_repeats}处(问-答-他说复读机式标签)——拆一轮插动作(W6验证:此计数原为死代码)")

    # 44d) 句长突发性(深度AI检测: 人类写作长短句剧烈切换)
    if len(slens) >= 10:
        _bursts = [abs(slens[i] - slens[i-1]) for i in range(1, len(slens))]
        _burst_avg = sum(_bursts) / max(len(_bursts), 1)
        metrics["burstiness"] = round(_burst_avg, 1)
        if _burst_avg < 5:
            warns.append(f"句长突发性{_burst_avg:.1f}(<5=AI匀速特征;人类参考>8)——长短句剧烈切换(一个5字短句后接一个30字长句)")

    # 盲区001修复: 金额一致性检查(同章同名科目两个不同值=FAIL)
    _money_entries = {}
    for _mm in re.finditer(r'(本金|利息|余额|欠款|缺口|收入|支出|手术费|工分)[^0-9]{0,4}([0-9.]+)', body):
        _subj = _mm.group(1)
        _val = float(_mm.group(2))
        if _subj in _money_entries and abs(_money_entries[_subj] - _val) > 0.01:
            issues.append(f'金额矛盾: {_subj}出现{_money_entries[_subj]}和{_val}两个不同值——商业文数字穿帮')
        _money_entries[_subj] = _val

    # 45) 记忆碎片注入(代入感引擎,红队20260918): 每千字≥1条感官记忆闪回
    #     启发式: 含气味/声音/触觉/视觉记忆词的段落,且不挂当前任务词
    _mem_pat = re.compile(r"想起.{0,10}(味|声|光|触|温度|气味|声音|画面)|记得.{0,10}(味|声|触)|小时候.{0,20}(味|声|热|冷)|那年.{0,15}(味|声|雪|雨|热)|上辈子.{0,10}(味|声)|熟悉的.{0,8}(味|声|触)")
    # 磨刀五批(20260919): 门致模板化修复——21章实测"忽然想起"被门奖励成16章签名句。
    # 多形态认可: 闪回可以用对话引出/器物触发/身体反应呈现,不必都写"想起";
    # 房间纹反作弊: 命中audit/book-tics.txt签名词组的记忆句不计入(堵"复写同一句过门")
    _mem_pat2 = re.compile(r"(祖父|师父|母亲|谭伯|老李)曾?(说|提|念)过[^。]{0,18}(味|声|热|冷|香|规矩|手艺)|那一[年天晚]他?还(小|在)[^。]{0,12}(味|声|热|冷)|一[闻听摸看]到[^。]{2,10}就想起|记得清清楚楚")
    _mem_n = len(_mem_pat.findall(body)) + len(_mem_pat2.findall(body))
    try:
        _tics_f = BOOK.parent / "audit" / "book-tics.txt" if False else None
    except Exception:
        _tics_f = None
    # 从被检文件向上回溯书根(支持 灶火1993/text/卷1/第NNN章.md 等布局)
    _tics_path = None
    try:
        _cur = pathlib.Path(p).resolve().parent
        for _ in range(4):
            _cand = _cur / "audit" / "book-tics.txt"
            if _cand.exists(): _tics_path = _cand; break
            _cur = _cur.parent
    except Exception:
        pass
    if _tics_path:
        _tics = [l.strip() for l in _tics_path.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("[")]
        if _tics:
            _hit_tic = sum(1 for m in _mem_pat.findall(body) if any(t in "".join(m) for t in _tics))
            _mem_n = max(0, _mem_n - _hit_tic)
    metrics["mem_fragments"] = _mem_n
    _mem_per_k = _mem_n * 1000 / max(cjk_len(body), 1)
    metrics["mem_per_k"] = round(_mem_per_k, 2)
    if n > 1500 and _mem_per_k < 0.5:
        warns.append(f"记忆碎片{ _mem_n}处({_mem_per_k:.1f}/千字,<0.5=代入感缺失)——每千字至少1条主角感官记忆闪回(气味/声音/触觉/画面,非情节)")

    # 46) 社交货币场面(付费意愿引擎,红队20260918): 每3章至少1个"读者会截图"的高光拍
    #     启发式: 含拍桌/倒吸/炸了/围观/议论/全群/全场/都愣了/鸦雀无声/同时的段落数
    _social_pat = re.compile(r"拍桌|拍腿|倒吸|炸了|轰动|全场|全群|都愣了|鸦雀无声|同时看|齐刷刷|哄一声|一起笑|哄堂|鼓掌|掌声|愣住|看傻|哗然|截图|发群|评论区|讨论|热议|话题|传开|围观|议论")
    _social_n = len(_social_pat.findall(body))
    metrics["social_beats"] = _social_n
    if n > 1500 and _social_n < 2:
        warns.append(f"社交货币拍{_social_n}处(<2=付费意愿弱)——每章至少2个'读者会截图发群'的高光时刻(拍桌/全场愣住/围观炸了)")

    # 47) 超短段存在性(反AI指纹,红队20260918): 每章≥2个≤5字独立段
    _ultrashort = [p for p in paras if 0 < cjk_len(p) <= 5]
    metrics["ultrashort_paras"] = len(_ultrashort)
    if n > 1200 and len(_ultrashort) < 2:
        warns.append(f"超短段{len(_ultrashort)}个(<2=AI指纹匀速感)——每章至少2个独立成段的超短句(≤5字,如'有了。''就是它。')")

    # 80) 排比三连/同头超短段连发(磨刀五批20260919: 全书指纹报告实测镜像句癖"白的。白的。还是白的。")
    _tri_comma = re.findall(r"([\u4e00-\u9fff]{2,5})，\1，", body)
    _run = 0; _tri_para = False
    for _p in paras:
        _L = cjk_len(_p)
        if 0 < _L <= 6:
            _run += 1
            if _run >= 3: _tri_para = True; break
        else: _run = 0
    metrics["triple_repeat"] = len(_tri_comma) + (1 if _tri_para else 0)
    if _tri_comma or _tri_para:
        warns.append(f"排比三连/同头超短段连发({'，'.join(_tri_comma[:1]) or '超短段×3'})——镜像句癖,跨章复用=全书签名")

    # 81) 章末金句连收(末两段连续警句=说教感,A9实测峰章11句金句/4000字)
    if len(paras) >= 2:
        _aph = re.compile(r"(不是[^。]{1,14}(是|而是)|，才是|就得|就会|才值钱|就得等|睡得着觉|醒着$|不得羞)")
        if _aph.search(paras[-1]) and _aph.search(paras[-2]):
            warns.append("章末金句连收(末两段连续警句)——说教感,末段收在动作/物件/对话")

    # 44) 旁白判词刻度(冷读3期: 收束腔逐章加重)——启发式:段尾抽象总结句式,只计数进METRICS
    aphor_pat = re.compile(
        r"(不是[^。」』]{1,14}[,，]?(是|而是)[^。」』]{1,24}。$)"
        r"|(这(就是|才是)|(才)是(这家人|这条街|这个家|生意|日子|手艺|年代)[^。」』]{0,14}。$)"
        r"|(压着的?不是[^。」』]{1,10}[,，]?是[^。」』]{1,20}。$)"
        r"|(有些[^。」』]{2,10}[,，]?[^。」』]{0,4}(说一遍|不用回头|就够了|忘不了|替谁)[^。」』]{0,12}[。！？]$)"
        r"|(像(把|一颗|一(枚|颗))[^。」』]{1,8}(钉|扣子|雷)[^。」』]{0,10}。$)"
        r"|(一个(道理|理|意思)[^。」』]{0,20}。$)"
    )
    aphor_n = sum(1 for x in paras if not ("\u201c" in x) and aphor_pat.search(x.strip()))
    metrics["aphor_endings"] = aphor_n
    if aphor_n >= 2:
        issues.append(f"旁白判词句{aphor_n}处(≥2即FAIL,大审计-11:写了没强制+阈值错)——删旁白总结,画面已把话说完")

    # 42) 时代语言穿帮(年代文专用: text/.era2005存在时激活; audits/20-E)
    #     2005后网络语混入正文=事实级出戏; 1发WARN,≥2发FAIL
    if (pathlib.Path(__file__).resolve().parent.parent / "text" / ".era2005").exists():
        ANACHRONISM = ["微信","朋友圈","扫码","二维码","内卷","躺平","佛系","破防",
                       "社死","绝绝子","yyds","YYDS","拿捏","凡尔赛","干饭","打工人",
                       "给力","点赞","带货","热搜","刷屏","吐槽"]
        anachron = [w for w in ANACHRONISM if w in body]
        if len(anachron) >= 2:
            issues.append(f"时代语言穿帮:{','.join(anachron)}——2005年不存在这些词(素材库J区负册)")
        elif len(anachron) == 1:
            warns.append(f"疑似时代穿帮词「{anachron[0]}」——核对素材库J区语言年代学")

    status = "FAIL" if issues else ("WARN" if warns else "PASS")
    metrics["status"] = status
    metrics["fails"] = len(issues)
    metrics["warns"] = len(warns)

    # 65) 编辑残渣(1993ch032事故: "那个'哦'——不对，那个算盘声"——作者自我更正句流入正文,
    # 付费读者回翻找不到"哦"直接判定校稿失职)
    _scars = re.findall(r"——不对[，,]|（不对[，,）]|[〔\[]原文[〕\]]|——应为|（原文如此）", body)
    if _scars:
        issues.append(f"编辑残渣{len(_scars)}处(「{_scars[0][:8]}…」)——自我更正句流入正文,按最终稿改写")

    # 66) 日期顺序(1993ch032事故: 初九段落排在初七之前)——同族时序词乱序WARN,近处有回忆标记则豁免
    _time_toks = [(mm.start(), mm.group(1)) for mm in re.finditer(r"初([一二三四五六七八九十]{1,2}|\d{1,2})", body)]
    
    def _cn_day(x):
        _m = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10, "十一": 11, "十二": 12, "十三": 13, "十四": 14, "十五": 15, "十六": 16, "十七": 17, "十八": 18, "十九": 19, "二十": 20, "廿一": 21, "廿二": 22, "廿三": 23, "廿四": 24, "廿五": 25, "廿六": 26, "廿七": 27, "廿八": 28, "廿九": 29, "三十": 30}
        return _m.get(x, int(x) if x.isdigit() else None)
    _vals = [(pos, _cn_day(x)) for pos, x in _time_toks]
    _vals = [(pos, v) for pos, v in _vals if v]
    _inversions = 0
    for _i in range(1, len(_vals)):
        _pos, _v = _vals[_i]
        _prevs = [pv for pp, pv in _vals[:_i] if pv > _v]
        if _prevs and not re.search(r"(想起|记得|回忆|那是|当时|回到)$", body[max(0, _pos-8):_pos]):
            _inversions += 1
    if _inversions:
        warns.append(f"时序词疑似乱序{_inversions}处(后文'初N'小于前文)——核对叙事时间线或补回忆标记")

    # ═══ 红队20260919文笔上限批(#67-#74,全WARN级): "不AI"之上还要"写得好" ═══

    # 67) 泛动词密度(白金动词力: 蹭/挪/杵/瞟 vs 走/看/说淹死画面)——bigram词表防"走廊/好看"误伤
    _narr_paras = [p for p in paras_all if "\u201c" not in p and '"' not in p]   # W6验证:原用_para_list(空行分段),单换行排版时恒空=门静默失效
    _narr_txt = "".join(_narr_paras)
    _weak_v = len(re.findall(r"走进|走出|走来|走到|说道|说了|说话|看了|看着|看向|站起|站住|坐下|拿起|放下|转头|点头|摇头|回头|走了|站了|坐了|看了看|想了一下", _narr_txt))
    if _narr_txt and n > 800:
        _wv_k = _weak_v / max(cjk_len(_narr_txt), 1) * 1000
        if _wv_k > 12:
            warns.append(f"泛动词密度{_wv_k:.0f}/千字(>12:走/看/说系淹没画面,白金用蹭/挪/杵/瞟)——修: line-polish轴1+工艺载药包动词轮换处方")

    # 68) 段尾虚词轻尾(汉语重音在句尾,"了/的/着"收段=整段泄气)
    _tail_weak = 0
    _tail_total = 0
    for _p in paras_all:
        if cjk_len(_p) < 6:
            continue
        _tail_total += 1
        _clean = re.sub(r"[。！？…\u201d\u300d\u300f\"\s]+$", "", _p)
        if re.search(r"(了|的|着|呢|吧|吗|啊|起来|下去|过来)$", _clean):
            _tail_weak += 1
    if _tail_total >= 8 and _tail_weak / _tail_total > 0.45:
        warns.append(f"段尾虚词轻尾{_tail_weak}/{_tail_total}段(>45%:'了/的/着'收段=重音丢失,段末应落名词/动词/数字)——修: line-polish轴3")

    # 69) 段首连接词依赖(此时/接着/然后开段=段段顺滑=段段可跳)
    _conn_heads = sum(1 for _p in paras_all if re.match(r"^(此时|这时|接着|然后|于是|随后|紧接着|与此同时|只见)", _p))
    if _conn_heads >= 4:
        warns.append(f"段首连接词开段{_conn_heads}次(≥4:此时/接着/然后=软开头依赖)——修: 段首三式轮换(动作直入/对白直入/短判断),scene-draft")

    # 70) 单段超长(手机屏十行无喘息——300字巨段方差门测不出)
    _mega = sum(1 for _p in paras_all if cjk_len(_p) >= 250)
    if _mega:
        warns.append(f"超长段{_mega}段(单段≥250字,手机屏十行无喘息)——修: 拆段或插动作拍,tighten")

    # 71) 指代堆积(这个/那个>6/千字=具体名词失业)
    _demon = len(re.findall(r"这个|那个|这些|那些|这种|那种", body))
    _dem_k = _demon / max(n, 1) * 1000
    if _dem_k > 6:
        warns.append(f"指代词密度{_dem_k:.0f}/千字(>6:这个/那个堆积,换具体名词)——修: line-polish轴1")

    # 72) 喻体复读(同章两次"像秤"式意象自我重复;复用#5明喻切片,剥名词语素假像)
    _sim_spans = set()
    _body_sim2 = re.sub(r"(神像|塑像|雕像|图像|摄像|录像|影像|画像|想象|像样|好像话|不像)", "", body)
    for _p2 in SIMILE_PATTERNS:
        for _m2 in re.finditer(_p2, _body_sim2):
            _sim_spans.add(_m2.span())
    _tenor_roots = {}
    for _s2, _e2 in _sim_spans:
        _frag = _body_sim2[_s2:_e2]
        _mtenor = re.search(r"像(?:是)?", _frag)   # W10: "像是秤砣"原取"是秤"
        if not _mtenor:
            continue   # W6验证:宛如/恍若无尾标记,frag[:4]='宛如'→root恒'宛如'误聚类;只对"像X"式提取喻体
        _tenor = _frag[_mtenor.end():].strip("一样般的的")
        _root = _tenor[:2]
        if len(_root) >= 2 and not re.match(r"^[\d一二三四五六七八九十]", _root):
            _tenor_roots[_root] = _tenor_roots.get(_root, 0) + 1
    _dup_sim = {k: v for k, v in _tenor_roots.items() if v >= 2}
    if _dup_sim:
        warns.append(f"喻体复读{len(_dup_sim)}组({','.join(list(_dup_sim)[:3])}×2)——同章同喻体=意象自我重复,换喻体或删——修: line-polish轴1喻检三问")

    # 73) 感官通道过载(五感杂拌:地板门#44b防缺,此门防滥——一章一主导感官)
    _ch_lex = {
        "嗅味": r"闻到|气味|味道|腥|糊味|焦味|烟味|土腥|铁锈味|汗味|药味|消毒水|香喷喷|臭",
        "听觉": r"听到|听见|声响|声音|轰|嗡|吱呀|窸窣|咔哒|哐当|噼啪",
        "触觉": r"摸到|摸着|烫|凉|冰凉|硌|粗糙|滑腻|潮湿|发麻|酥麻|扎手",
        "视觉": r"看见|看到|瞧见|目光|视线|盯着|瞟",
    }
    _ch_hit = sum(1 for pat in _ch_lex.values() if re.search(pat, body))
    if _ch_hit >= 4 and metrics.get("sense_per_k", 0) > 12:
        warns.append(f"感官通道{_ch_hit}/4全开且密度{metrics.get('sense_per_k')}/千字(>12:五感杂拌=各通道浅尝辄止)——修: 一章一主导感官(卡2.7),scene-audit核对")

    # 74) 对白标签动作轮换枯竭(躲开"他说"后改用"他笑了/皱眉/点头"三件套复读)
    _labels = [x for x in re.findall(r"([\u4e00-\u9fff]{1,4})(?:说道|问道|答道|笑道|叹道|骂道|嚷道|喊道)(?=[。:,])", "".join(_para_list)) if x[-2:] not in ("小说","传说","话本","评书") and len(x) <= 4]   # W6验证:词尾"小说。"吞入污染top标签
    if len(_labels) >= 8:
        from collections import Counter as _Ctr
        _top_label, _top_n = _Ctr(_labels).most_common(1)[0]
        if _top_n / len(_labels) > 0.4:
            warns.append(f"标签动作枯竭:'{_top_label}'占{_top_n}/{len(_labels)}(>40%:标签成了新指纹)——修: dialogue-voice标签动作池(每角色5个专属)")

    # ═══ 红队20260919十波批: 文本卫生四门(#75-78,全WARN) ═══
    # 75) 错别字高置信(的地得/在再误用——只收高置信模式防误报)
    _typos = re.findall(r"跑的飞快|走的太急|说的太难听|在也|在说一遍|应当做主|想再法", body)
    if _typos:
        warns.append(f"疑似错别字{len(_typos)}处({','.join(_typos[:3])})——'的/得''再/在'核查,fix_quotes族工具不管错字")
    # 76) 全角半角混排
    _fw = re.findall(r"[０-９Ａ-Ｚａ-ｚ]|[\u4e00-\u9fa5][,.:;!?]", body)
    if len(_fw) > 3:
        warns.append(f"全角半角混排{len(_fw)}处(全角数字字母/汉字后半角标点)——统一半角数字+全角标点")
    # 77) 省略号变体归一
    _ell = re.findall(r"\.\.\.|。{2,}|(?<!\u2026)…(?!\u2026)|····", body)   # W10: 原正则把规范双省略号第二颗误报
    if _ell:
        warns.append(f"省略号变体{len(_ell)}处(…/.../。。。。)——规范为中文双省略号'……'")
    # 78) 破折号变体
    _dash = re.findall(r"--|－－|———", body)
    if _dash:
        warns.append(f"破折号变体{len(_dash)}处(--/－－/———)——规范为中文双破折号'——'")
    # 79) 感叹问号连用(排版规范:情绪堆叠=AI指纹)
    _bang = re.findall(r"[！！]{2,}|[？？]{2,}|！\?|\?！|!!|\?\?", body)
    if len(_bang) >= 2:
        warns.append(f"感叹问号连用{len(_bang)}处(！！/？！堆叠=情绪靠标点不靠内容)——留一处最强的,其余改句式")
    # grandfathering(W新批): 存量章(gate_ver<当前版)重测时,非核心FAIL降WARN——修旧章一个错字不再被新门拦死
    if gate_ver is not None and gate_ver < GATE_VERSION:
        _CORE = ("字数硬线", "骨架", "引号", "章末", "拼装疤", "金额", "时代错位词", "章级字数", "泄漏", "重复段")
        _kept, _gf = [], []
        for _msg in issues:
            if any(k in _msg for k in _CORE):
                _kept.append(_msg)
            else:
                _gf.append(_msg)
        if _gf:
            issues[:] = _kept
            warns.append(f"[grandfathering] 门版本{gate_ver}→{GATE_VERSION}间新增门的{len(_gf)}项FAIL已降WARN(修旧章不拦死);新版全量过门跑: scores --recompute")
            metrics["grandfathered"] = len(_gf)
    return fp, n, status, issues, warns, metrics


def threads_mode(folder: pathlib.Path):
    """草蛇灰线追踪(docs/15):读取 threads.txt,输出逐章命中矩阵与断线预警。"""
    tfile = pathlib.Path(__file__).parent / "threads.txt"
    rows = []
    if tfile.exists():
        for line in tfile.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                rows.append((parts[0], parts[1]))
    files = sorted(folder.glob("*.md")) if folder.is_dir() else [folder]
    if not files or not rows:
        print("无可扫描章节或 threads.txt 为空")
        return 0
    # 命中矩阵
    print(f"{'灰线':<10}" + "".join(f"{f.stem[-3:]:>5}" for f in files))
    matrix = {}
    for kw, name in rows:
        counts = []
        for f in files:
            body = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                             if l.strip() and not l.startswith("#"))
            counts.append(body.count(kw))
        matrix[len(matrix)] = (name, counts)   # W6验证:同名灰线dict键覆盖致zip错位
        print(f"{kw:<10}" + "".join(f"{c:>5}" for c in counts))
    # 断线预警:某灰线最近GAP_LIMIT章未出现(且此前出现过)
    GAP_LIMIT = 10
    print("\n断线预警(超过%d章未现):" % GAP_LIMIT)
    warned = False
    for (kw, name), counts in zip(rows, matrix.values()):
        appeared = [i for i, c in enumerate(counts) if c > 0]
        if appeared and len(counts) - 1 - appeared[-1] >= GAP_LIMIT:
            print(f"  [WARN] 「{kw}」({name})已有{len(counts)-1-appeared[-1]}章未出现——安排变奏复现(间隔5-15章律)")
            warned = True
        if not appeared:
            print(f"  [待埋] 「{kw}」({name})全书尚未首次出现")
    if not warned:
        print("  无")
    return 0

def baseline_mode(fp: pathlib.Path):
    """中文AI味四指标(B2建议自建基线):四字词密度/逻辑胶水密度/句长变异系数/对话语气词密度。"""
    body = "\n".join(l for l in fp.read_text(encoding="utf-8-sig").splitlines()
                     if l.strip() and not l.startswith("#"))
    n = cjk_len(body)
    if n < 200:
        print("文本太短(<200字),基线无意义"); return 0
    fourgrams = len(re.findall(r"[\u4e00-\u9fff]{4}", body))
    glue = sum(body.count(w) for w in ["然而","因此","因为","所以","于是","但是","虽然","尽管","总之","综上","与此同时","不得不说","值得一提的是"])
    sents = [cjk_len(s) for s in re.split(r"[。！？\n]", body) if cjk_len(s) > 0]
    cv = (statistics.pstdev(sents) / statistics.mean(sents) * 100) if len(sents) >= 10 and statistics.mean(sents) else 0
    dia = "".join(re.findall(r"[\u201c]([^\u201d]*)[\u201d]", body))
    mood = sum(dia.count(w) for w in ["啊","呗","嘛","呗","得了","行吧","得了吧","嚯","啧","嗯","哦","诶","嘿"])
    dn = cjk_len(dia) or 1
    print(f"=== AI味四指标 [{fp.name}] {n}字 ===")
    print(f"四字词密度: {fourgrams/n*1000:.1f}/千字")
    print(f"逻辑胶水: {glue/n*1000:.2f}/千字 (>2.0=翻译腔超标)")
    print(f"句长变异系数: {cv:.0f}% (<30%=节奏过匀)")
    print(f"对话语气词: {mood/dn*100:.1f}% (<3%=对话无人味)")
    return 0


def main():
    args = sys.argv[1:]
    if "--baseline" in args:
        args = [a for a in args if a != "--baseline"]
        if not args or not pathlib.Path(args[0]).exists():
            print("需要文件参数"); return 2
        return baseline_mode(pathlib.Path(args[0]))
    scene_mode = "--scene" in args
    if scene_mode:
        args = [a for a in args if a != "--scene"]
        SCENE_MODE[0] = True
    metrics_mode = "--metrics" in args
    if metrics_mode:
        args = [a for a in args if a != "--metrics"]
    if "--modern" in args:
        # 现代都市背景:关闭时代错位词检查(该检查仅用于古风背景)
        args = [a for a in args if a != "--modern"]
        global MODERN_SETTING
        MODERN_SETTING[0] = True
    _gv = None
    if "--gate-ver" in args:
        _gi = args.index("--gate-ver")
        try:
            _gv = int(args[_gi + 1])
        except (ValueError, IndexError):
            _gv = None
        args = args[:_gi] + args[_gi + 2:]   # grandfathering: 剥除参数对(须在文件校验守卫前)
    if not args or args[0] in ("-h","--help"):
        print(__doc__); return 2
    for a in args:
        if a.startswith("--"): continue
        if not pathlib.Path(a).exists():
            if re.fullmatch(r"\d+", a):
                # 1993审计事故: 章号当路径→"文件不存在"→批量扫空转成"全过零报警"
                print(f"参数「{a}」是章号不是文件——check.py只收文件路径(例: text/卷1/第{int(a):03d}章.md 或 书根/text/卷N/第NNN章.md)")
            else:
                print(f"文件不存在: {a}")
            return 2
    if args[0] == "--threads":
        if len(args) < 2:
            print("用法: check.py --threads <目录>"); return 2
        if len(args) < 2:
            print("用法: check.py --threads <目录>"); return 2
        return threads_mode(pathlib.Path(args[1]))
    files = []   # _gv已在守卫前剥除解析
    for a in args:
        p = pathlib.Path(a)
        if p.is_dir():
            files += sorted(p.glob("*.md"))
        else:
            files.append(p)
    total_fail = 0
    total_warn = 0
    for fp in files:
        fp, n, status, issues, warns, metrics = check(fp, gate_ver=_gv)
        print(f"\n=== {fp.name} [{n}字] {status} ===")
        for i in issues: print(f"  [FAIL] {i}")
        for w in warns:  print(f"  [WARN] {w}")
        if not issues and not warns: print("  全项通过")
        if metrics_mode:
            print("METRICS " + json.dumps(metrics, ensure_ascii=False))
        total_fail += 1 if issues else 0
        total_warn += len(warns)
    print(f"\n汇总:{len(files)}章,FAIL {total_fail}章,WARN {total_warn}条")
    if total_warn:
        print("WARN处置纪律(法医ch001教训:重复段WARN被静默放过→冷读事故): 归档前每条WARN必须"
              "修复或在ledgers/waivers.md登记豁免——只看FAIL不算过门")
    return 1 if total_fail else 0

if __name__ == "__main__":
    sys.exit(main())
