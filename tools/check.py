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
DASH_LIMIT = 3          # 破折号 ——
SIMILE_LIMIT = 3        # 明喻
SYSTEM_LINE_LIMIT = 4   # 【系统台词行
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

def check(fp: pathlib.Path):
    raw = fp.read_text(encoding="utf-8-sig")
    # 卡派生字数带与峰章(audits/21-Fix6): 卡带=唯一权威
    _m = re.search(r"第(\d+)章", fp.name)
    _card_txt = ""
    if _m:
        for _c in pathlib.Path(fp.parent.parent / "卡").glob(f"*第{_m.group(1)}章*.md"):
            _card_txt = _c.read_text(encoding="utf-8")
            break
    _peak = "峰章" in _card_txt
    _band = re.search(r"(\d{4})\s*[-—~至]\s*(\d{4})", _card_txt)
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
        issues.append(f"章级字数{n}(<1800硬线)——骨架未回填,禁以成稿身份入库;走beat-expand血肉遍")
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
    for p in SIMILE_PATTERNS:
        sim += len(re.findall(p, body))
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
    opens = {}
    paras = [p.strip() for p in body.split("\n") if p.strip()]
    for p in paras:
        k = re.sub(r'[「"\'《*—…\s]', "", p)[:2]
        if len(k) == 2:
            opens[k] = opens.get(k, 0) + 1
    for k, c in sorted(opens.items(), key=lambda x: -x[1])[:3]:
        if c >= 4:
            warns.append(f"段落开头「{k}…」{c}次(注意句式雷同)")

    # 9) 句长方差(反均匀;std<6 视为节奏单一)
    sents = re.split(r"[。!?\n]", body)
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

    # 13) 段落长度方差(反匀速,布防总表B3)
    plens = [cjk_len(p) for p in paras]
    if len(plens) >= 12:
        psd = statistics.pstdev(plens)
        if psd < 20:
            warns.append(f"段落长度方差过小({psd:.0f}),段落匀速感(注意长短段错落)")

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
        issues.append(f"章内原样重复{len(dup_set)}处(首处:「{list(dup_set)[0][:18]}…»)——补丁残留或复读,必须整体重写")
    elif len(dup_set) == 1:
        metrics["dup18"] = 1
        warns.append(f"章内原样重复1处(「{list(dup_set)[0][:18]}…」)——检查是否补丁残留")

    # 14.4) 装饰性修辞总密度 v2:去除与#5重复计算的模式,只加新出现的
    sim_extra = 0
    for pat in [r"宛如", r"恍若"]:  # 只加#5未覆盖的
        sim_extra += len(re.findall(pat, body))
    personif = len(re.findall(r"[推拉扛拽]着一?(?:一整个|整个)", body))
    if sim + sim_extra + personif > SIMILE_LIMIT:
        issues.append(f"装饰性修辞{sim+sim_extra+personif}处(明喻{sim+sim_extra}+拟人{personif},上限{SIMILE_LIMIT})——AI标志:每个描写点挂比喻;真实作者白描为主")

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

    # 16) 对话字数占比(用户标准:真人白金作家对话≥40-50%)
    dialog_str = "".join(re.findall(r'["\u201c]([^"\u201d]*)["\u201d]', body))
    dialog_chars = cjk_len(dialog_str)
    if n > 500:
        dpct = dialog_chars / n * 100
        metrics["dia_char_pct"] = round(dpct, 1)
        if dpct < 25:
            issues.append(f"对话字数占比{dpct:.0f}%(<25%,严重不足:角色必须开口说话!)")
        elif dpct < 30:
            warns.append(f"对话字数占比{dpct:.0f}%(<40%,偏低:目标40-55%;角色要多说话说废话说长话)")

    # 17) 心理活动密度(用户标准:每千字≥2处心理beat)
    # 已知局限:本检查基于标记词(心里/觉得/寻思…),而风格包v6提倡的'心理裸写'常无标记词
    # (如'不能说。打死也不能说。')——裸写密度靠冷读与场景验收人工判定,此处仅测下限
    # v2: 大幅扩充词表——覆盖身体反应/情绪动词/内心独白/记忆闪回/决策犹豫
    psych_pats = r"""(?:
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
    )"""
    psych_count = len(re.findall(psych_pats, body, re.VERBOSE))
    if n > 800:
        psych_per_k = psych_count / n * 1000
        metrics["psych_per_k"] = round(psych_per_k, 2)
        if psych_per_k < 0.5:
            issues.append(f"心理活动{psych_count}处({psych_per_k:.1f}/千字,<1.0/千字,严重缺失:白金作家≥2/千字)")
        elif psych_per_k < 2.0:
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
    if dialog_scenes < 2 and n > 800:
        issues.append(f"对话场景仅{dialog_scenes}个(<2,章内须至少2个独立对话场景)")

    # 19) 英文残留(连续≥3个拉丁字母,时代错位)
    en_hits = re.findall(r"[a-zA-Z]{3,}", re.sub(r"\b(?:CSI|now|BEAT|beat)\b", "", body))
    if en_hits:
        issues.append(f"英文残留:{','.join(en_hits[:5])}(正文不得出现拉丁字母词)")

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
        MODERN_WORDS = ["照片", "电话", "手机", "电脑", "电视", "咖啡", "沙发", "卡车", "地铁", "公园", "超市", "公交", "电梯"]
        for w in MODERN_WORDS:
            if w in body:
                issues.append(f"时代错位词「{w}」(古代背景不得出现现代词汇)")
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
        warns.append(f"心动死喻{len(dead_metaphors)}处({','.join(set(dead_metaphors[:3]))})——换动作/物证/沉默三载体,红队I")

    # 29) 首句长度(红队E转换规则1:第一句≤10字,扔事件碎片不递画面)
    if body_lines:
        first_sent = re.split(r'[。!?\n]', body_lines[0])[0]
        fl = cjk_len(first_sent)
        if fl > 25:
            warns.append(f"首句{fl}字(>25,白金开篇首句≤10字碎片式:『头七,第三夜。』式,不递画面扔事件)")

    # 30) 感叹号温差(红队E:冷叙述+热对白;叙述段感叹号占比过高=失去温差)
    dia_ex = sum(p.count('！') + p.count('!') for p in paras_all if ('"' in p or '\u201c' in p))
    nar_ex = sum(p.count('！') + p.count('!') for p in paras_all if ('"' not in p and '\u201c' not in p))
    if nar_ex > dia_ex and nar_ex > 3:
        warns.append(f"感叹号温差倒挂:叙述段{nar_ex}个 vs 对话段{dia_ex}个——感叹号应集中对话与情绪峰值,叙述保持句号(冷面)")

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
        _mhits = re.findall(
            r"[一两二三四五六七八九十百千]{1,10}(?:千|万|块|元|毛)[一两二三四五六七八九十百零点五]{0,8}"
            r"|\d+(?:\.\d+)?(?:块|元|毛)", body)
        _mhits = [h for h in _mhits
                  if "千万" not in h and not re.search(r"年|月|日|次|遍|岁|分钟|度|号|名|个|位|回", h)]
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
        if tl_per_k < 3:
            issues.append(f"对白语气词密度{tl_per_k}/千字(<3=严重不足:机器对白)——每段对话至少一个啊/呗/嘛/那啥(dialogue-voice)")
        elif tl_per_k < 8:
            warns.append(f"对白语气词密度{tl_per_k}/千字(<8)——对白偏干净,多加语气词/口头禅(dialogue-voice)")

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

    # 53) 无冲突检测(大审计-28根因: 没有阻碍=没有场景=读者弃书)
    _conflict_words = ["不行","反对","不行","不同意","等等","问题","麻烦","不对","不行","但是","可是","拒绝","不要","不行","不能","还没","还没","失败","坏了","出事","急"]
    _has_conflict = any(w in body for w in _conflict_words)
    if n >= 1500 and not _has_conflict:
        issues.append("无冲突检测: 全章没有任何角色表达反对/遇到困难/面临阻碍——没有冲突就没有场景(大审计-28根因)")

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
    if _rq_lines:
        issues.append(f"行首右引号{len(_rq_lines)}行(FAIL)——引号方向反了(事故形状:'”对话。‘'),运行 tools/fix_quotes.py 或人工修复")
    _brk = re.findall(r"[，。；：、]{2,}", body)
    _half_dash = re.findall(r"(?<!—)—(?!—)", body)
    metrics["broken_punct"] = len(_brk)
    metrics["half_dash"] = len(_half_dash)
    if _brk:
        warns.append(f"破句/连续标点{len(_brk)}处({';'.join(_brk[:3])})——编辑残渣,占位文本未清理干净")
    if _half_dash:
        warns.append(f"单破折号残迹{len(_half_dash)}处——中文破折号应为'——'双字符,单'—'多为删除残留")

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
        c = re.sub(r"[\s，。！？；：、“”]", "", s)
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
        """中文数字→数值(大审计-18 D5: 只比字符串则'四千五'与'4500'互为假阴假阳)"""
        m = {"零":0,"一":1,"二":2,"两":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
        if s.isdigit():
            return int(float(s))
        total, num, ok = 0, 0, False
        for ch in s:
            if ch in m:
                num, ok = m[ch], True
            elif ch == "十":
                total += (num or 1) * 10; num = 0; ok = True
            elif ch == "百":
                total += (num or 1) * 100; num = 0; ok = True
            elif ch == "千":
                total += (num or 1) * 1000; num = 0; ok = True
            elif ch == "万":
                total += (num or 1) * 10000; num = 0; ok = True
        return total + num if ok else None
    _acc = _col.defaultdict(set)
    for _mm in _fig.finditer(body):
        _v = _zh2int(_mm.group(2))
        if _v is not None:
            _acc[_mm.group(1)].add(_v)
    _bad = {k: sorted(v) for k, v in _acc.items() if len(v) > 1}
    metrics["money_conflict"] = len(_bad)
    if _bad:
        issues.append(f"金额科目数值冲突{_bad}——同章同科目出现不同数值(大审计-11 #47数值化),对齐数字表")

    # 43) 段落形态刻度(漂移审计2期: 17-20章段均>30红/长段超配)——只进METRICS+WARN,不FAIL
    para_lens = [cjk_len(x) for x in paras]
    if para_lens:
        avg_pl = sum(para_lens) / len(para_lens)
        long_n = sum(1 for L in para_lens if L >= 110)
        metrics["avg_para_len"] = round(avg_pl, 1)
        metrics["long_paras"] = long_n
        if avg_pl > 34:
            warns.append(f"段均字数{avg_pl:.0f}(规格≤30,漂移审计2期)——长段拆分/多留短句段")
        if long_n > 6:
            warns.append(f"长段{long_n}个(≥110字,规格≤3)——整章匀速感超标,拆段")

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
        matrix[name] = counts
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
    sents = [cjk_len(s) for s in re.split(r"[。!?\n]", body) if cjk_len(s) > 0]
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
    if not args or args[0] in ("-h","--help"):
        print(__doc__); return 2
    for a in args:
        if a.startswith("--"): continue
        if not pathlib.Path(a).exists():
            print(f"文件不存在: {a}"); return 2
    if args[0] == "--threads":
        if len(args) < 2:
            print("用法: check.py --threads <目录>"); return 2
        if len(args) < 2:
            print("用法: check.py --threads <目录>"); return 2
        return threads_mode(pathlib.Path(args[1]))
    files = []
    for a in args:
        p = pathlib.Path(a)
        if p.is_dir():
            files += sorted(p.glob("*.md"))
        else:
            files.append(p)
    total_fail = 0
    total_warn = 0
    for fp in files:
        fp, n, status, issues, warns, metrics = check(fp)
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
