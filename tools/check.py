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
import sys, re, pathlib, statistics

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

def cjk_len(text):
    return len(re.findall(r"[\u4e00-\u9fff]", text))

def check(fp: pathlib.Path):
    raw = fp.read_text(encoding="utf-8")
    lines = raw.splitlines()
    body_lines = [l for l in lines if l.strip() and not l.startswith("#")]
    body = "\n".join(body_lines)
    n = cjk_len(body)
    issues, warns = [], []

    # 1) 字数
    if n == 0:
        issues.append("空文件")
    elif n < 2300 and not SCENE_MODE[0]:
        warns.append(f"章级字数偏少:{n}(章带2500-3200;场景文件请用 --scene 免此项)")
    elif n > 3600 and not SCENE_MODE[0]:
        warns.append(f"字数超限:{n}(目标2500-3200,黄金三章上限3500)")
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
    dl = [l for l in body_lines if ('"' in l or '"' in l or '「' in l or '"' in l or l.strip().startswith('"'))]
    if body_lines:
        ratio = len(dl) / len(body_lines)
        if ratio < 0.10:
            warns.append(f"对话行占比{ratio:.0%}(<10%),场景化不足/平铺直叙风险")
        elif ratio > 0.75:
            warns.append(f"对话行占比{ratio:.0%}(>75%),叙述过少(像剧本不像小说)")

    # 15.5) 章内重复跨度(≥18字原样重复=补丁残留/AI复读) v2:去重叠+计数校准
    clean2 = re.sub(r"\s+", "", body)
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
        issues.append(f"章内原样重复{len(dup_set)}处(首处:「{list(dup_set)[0][:18]}…»)——补丁残留或复读,必须整体重写")
    elif len(dup_set) == 1:
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
    if tail_char in ",,、:“(“":
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
        if dpct < 15:
            issues.append(f"对话字数占比{dpct:.0f}%(<25%,严重不足:真人白金作家≥45%;信息交付须场景化勿叙述概述)")
        elif dpct < 35:
            warns.append(f"对话字数占比{dpct:.0f}%(<35%,偏低:目标≥45%)")

    # 17) 心理活动密度(用户标准:每千字≥2处心理beat)
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
    en_hits = re.findall(r"[a-zA-Z]{3,}", re.sub(r"CSI|now|BEAT|beat", "", body))
    if en_hits:
        issues.append(f"英文残留:{','.join(en_hits[:5])}(正文不得出现拉丁字母词)")

    # 20) 流水账叙述检测(段落开头=人名+叙述动词,连续≥3段)
    flow_starts = 0
    max_flow = 0
    flow_names = "陈更|他|文渊|墨鸦|闻人霜|樊大|白老爷|崔一笔|严堂丞|杜推官|齐有德|文先生|她"
    flow_verbs = "去|到|查|发现|找|来|回|带|递|收|写|看|听|等|送|拿|走|说|问|翻|拆|试|开"
    for p in paras_all:
        if re.match(rf"^({flow_names})({flow_verbs})", p):
            flow_starts += 1
            max_flow = max(max_flow, flow_starts)
        else:
            flow_starts = 0
    if max_flow >= 5:
        warns.append(f"流水账风险:连续{max_flow}段以'人名+动词'开头(注意用对话/白描/心理打断叙述)")

    # 21) 时代错位词(现代/外文混入正文)
    MODERN_WORDS = ["照片", "电话", "手机", "电脑", "电视", "咖啡", "沙发", "卡车", "地铁", "公园", "超市", "公交", "电梯"]
    for w in MODERN_WORDS:
        if w in body:
            issues.append(f"时代错位词「{w}」(古代背景不得出现现代词汇)")

    # 22) 角色语音同质化检测 + 23) 声纹禁词(从死代码中恢复)
    speaker_sents = {}
    current_speaker = None
    speaker_pats = {
        "樊大": r"樊大(?:说|道|问|喊|嚷|吼|叫|回)",
        "闻人霜": r"闻人霜|闻姑娘",
        "墨鸦": r"墨鸦",
        "文渊": r"文渊|文先生|文总管",
        "白老爷": r"白老爷|白圭",
        "崔一笔": r"崔一笔|崔老|老崔",
        "钱通宝": r"钱通宝|钱掌柜",
        "严堂丞": r"严堂丞|堂丞",
    }
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
    VOICE_BANS = {
        "樊大": ["可谓", "然也", "诚如"],
        "闻人霜": ["可能", "也许", "大概", "好像"],
        "陈更": ["差不多", "无所谓"],
        "墨鸦": ["高兴", "难过", "害怕", "咱们"],
        "文渊": ["他娘的", "混账", "放屁"],
    }
    for sp, bans in VOICE_BANS.items():
        in_sp = False
        for p in paras_all:
            if re.search(speaker_pats.get(sp, sp), p):
                in_sp = True
            if in_sp and ('"' in p or '\u201c' in p):
                for ban in bans:
                    if ban in p:
                        warns.append(f"声纹违例:「{sp}」说了禁词「{ban}」(若为故意喜剧手法可登记豁免)")
                        in_sp = False
                        break
            elif in_sp and not p.strip():
                in_sp = False

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

    status = "FAIL" if issues else ("WARN" if warns else "PASS")
    return fp, n, status, issues, warns


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

def main():
    args = sys.argv[1:]
    scene_mode = "--scene" in args
    if scene_mode:
        args = [a for a in args if a != "--scene"]
        SCENE_MODE[0] = True
    if not args or args[0] in ("-h","--help"):
        print(__doc__); return 2
    for a in args:
        if a.startswith("--"): continue
        if not pathlib.Path(a).exists():
            print(f"文件不存在: {a}"); return 2
    if args[0] == "--threads":
        return threads_mode(pathlib.Path(args[1]))
    files = []
    for a in args:
        p = pathlib.Path(a)
        if p.is_dir():
            files += sorted(p.glob("*.md"))
        else:
            files.append(p)
    total_fail = 0
    for fp in files:
        fp, n, status, issues, warns = check(fp)
        print(f"\n=== {fp.name} [{n}字] {status} ===")
        for i in issues: print(f"  [FAIL] {i}")
        for w in warns:  print(f"  [WARN] {w}")
        if not issues and not warns: print("  全项通过")
        total_fail += 1 if issues else 0
    print(f"\n汇总:{len(files)}章,FAIL {total_fail}章")
    return 1 if total_fail else 0

if __name__ == "__main__":
    sys.exit(main())
