#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_storm.py 多波次subagent风暴编排器(红队20260919)

用户需求: 每个功能不少于5波次,每波次不少于10个subagents,多角度多维红蓝对抗。

本工具为任意功能节点生成完整的agent风暴prompt包:
  Wave 1 攻击波(红队): 10个不同角度的攻击者,找一切问题
  Wave 2 辩护波(蓝队): 10个不同角度的辩护者,找攻击中的误报
  Wave 3 仲裁波(评审): 10个不同维度的评审,综合红蓝对抗结果
  Wave 4 修复波(工匠): 10个不同专长的修复者,各管一个维度
  Wave 5 守卫波(终审): 10个不同立场的终审官,最终放行/打回

用法:
  python3 tools/agent_storm.py <功能类型> <目标路径> [--book 书根] [--wave N]
  功能类型: chapter|premise|design|volume|system|ledger|periodic
  --wave N: 只生成第N波(1-5),缺省生成全部5波

红队20260919用户令: 每一章、每一个设计文件、每一个构思步骤
都默认跑全5波×10 agent=50 subagent红蓝对抗。不设条件跳过。

输出: <书根>/audit/storm/<功能>-<目标>-wave<N>.md
  每个wave文件包含10个agent prompt,供Agent工具逐个派发
"""
import sys, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_TARGET_SIZE = 500_000  # 缺陷16

# ═══ 角色池(每个wave 10个不同角色) ═══

WAVE1_ATTACKERS = [
    {"id": "A1", "role": "追更毒舌读者", "lens": "爽感", "mission": "你是追更3年的毒舌读者。找出这章所有不爽的地方——哪里温吞?哪里想跳?哪里想弃?你的标准:不爽=罪。"},
    {"id": "A2", "role": "弃书审判官", "lens": "注意力", "mission": "你是弃书审判官。逐段找'读者会关闭页面'的段落。走神一次记一罪。你的标准:走神=死罪。"},
    {"id": "A3", "role": "逻辑审查员", "lens": "逻辑", "mission": "你是逻辑审查员。找前后矛盾/时间线穿帮/角色说了不该知道的话。你的标准:穿帮=致命。"},
    {"id": "A4", "role": "文笔鉴赏家", "lens": "AI检测", "mission": "你是文笔鉴赏家。逐段判断'像人还是像AI'。找AI指纹:匀速段落/安全用词/签名句式。你的标准:AI感=不合格。"},
    {"id": "A5", "role": "代入党", "lens": "代入感", "mission": "你是目标受众替身(30-50岁男性,下班手机看文)。找'完全无感'的段落。你的标准:无感=废话。"},
    {"id": "A6", "role": "节奏警察", "lens": "节奏", "mission": "你是节奏警察。找'太慢'和'太快'的段落。拖沓?赶?匀速无起伏?你的标准:节奏不对=读不下去。"},
    {"id": "A7", "role": "重复猎手", "lens": "新鲜度", "mission": "你是重复猎手。找情节模式/句式/用词/桥段的重复。连续N章都在写同一件事?你的标准:重复=读者跑了。"},
    {"id": "A8", "role": "伏笔审计师", "lens": "伏笔", "mission": "你是伏笔审计师。检查:埋了的有没有收?收了的有没有埋?悬空的有没有计划?你的标准:伏笔悬空=骗子。"},
    {"id": "A9", "role": "角色律师", "lens": "人设", "mission": "你是角色律师,代表读者检查每个角色。角色OOC了吗?工具人了吗?死了又活了吗?你的标准:角色崩=信任崩。"},
    {"id": "A10", "role": "商业分析师", "lens": "付费", "mission": "你是商业分析师。这章值不值钱?读者会不会付费?有没有社交货币(想截图发群的场面)?你的标准:不值钱=白写。"},
]

WAVE2_DEFENDERS = [
    {"id": "D1", "role": "文本辩护律师", "lens": "误报过滤", "mission": "你是文本辩护律师。攻击波A1-A10的指控中,哪些是误报?用原文证明被告无罪。"},
    {"id": "D2", "role": "类型惯例专家", "lens": "类型合理性", "mission": "你是类型文专家。有些'问题'其实是类型惯例(年代文就是慢热/系统文就是金手指)。过滤掉伪问题。"},
    {"id": "D3", "role": "伏笔辩护人", "lens": "伏笔合法性", "mission": "你是伏笔辩护人。A8说的'悬空伏笔',哪些其实是'长线伏笔'还没到回收时机?"},
    {"id": "D4", "role": "节奏辩护人", "lens": "蓄压合法性", "mission": "你是节奏辩护人。A6说的'慢',哪些其实是必要的蓄压?爽文也需要呼吸。"},
    {"id": "D5", "role": "角色辩护人", "lens": "角色复杂性", "mission": "你是角色辩护人。A9说的'OOC',哪些其实是角色的成长/多面性?"},
    {"id": "D6", "role": "AI检测辩护人", "lens": "检测假阳性", "mission": "你是AI检测专家。A4标记的'AI指纹',哪些其实是正常的文学手法?检测器也有假阳性。"},
    {"id": "D7", "role": "商业辩护人", "lens": "长线价值", "mission": "你是商业辩护人。A10说'不值钱',但这章是否在为后文的大爽做铺垫?"},
    {"id": "D8", "role": "受众辩护人", "lens": "受众分层", "mission": "你是受众专家。A5说'无感',但也许这段不是写给他的?不同读者段位不同。"},
    {"id": "D9", "role": "结构辩护人", "lens": "结构必要性", "mission": "你是结构专家。有些'重复'其实是母题变奏(如'先量后拆'反复出现是刻意的)。"},
    {"id": "D10", "role": "综合辩护律师", "lens": "整体权衡", "mission": "你是综合辩护律师。权衡所有辩护:哪些指控站得住,哪些该撤?给最终辩护意见。"},
]

WAVE3_ARBITERS = [
    {"id": "J1", "role": "总编", "lens": "综合质量", "mission": "你是出版社总编。综合攻击波和辩护波的意见,给出本章的最终判定:放行/修改后放行/打回。"},
    {"id": "J2", "role": "数据分析师", "lens": "量化", "mission": "你是数据分析师。把红蓝对抗的论点量化:攻击波提了几个问题?辩护波推翻了几个?净问题数是多少?"},
    {"id": "J3", "role": "读者代表", "lens": "追读", "mission": "你是读者代表(从评论区选出)。你不关心红蓝对抗的辩论,只关心:这章我想不想看下一章?"},
    {"id": "J4", "role": "平台审核员", "lens": "合规", "mission": "你是平台审核员。检查:有没有敏感内容?AI检测风险?会不会被限流?"},
    {"id": "J5", "role": "编辑(情节线)", "lens": "情节", "mission": "你是负责情节线的编辑。这章的情节推进够吗?信息密度够吗?有没有'白写'的章?"},
    {"id": "J6", "role": "编辑(人物线)", "lens": "人物", "mission": "你是负责人物线的编辑。这章人物有成长吗?有关系变化吗?有没有工具人?"},
    {"id": "J7", "role": "编辑(文笔线)", "lens": "文笔", "mission": "你是负责文笔线的编辑。语言有质感吗?有记忆点吗?有'金句'吗?"},
    {"id": "J8", "role": "编辑(商业线)", "lens": "商业", "mission": "你是负责商业线的编辑。这章有付费点吗?有安利点吗?有转发点吗?"},
    {"id": "J9", "role": "心理顾问", "lens": "情绪", "mission": "你是情绪设计顾问。这章的情绪弧线对吗?哪里该高哪里该低?读者读完什么感受?"},
    {"id": "J10", "role": "终审法官", "lens": "终审", "mission": "你是终审法官。听取所有评审意见,敲槌:放行(不改)/修改后放行(列出必改项)/打回(重写)。"},
]

WAVE4_CRAFTERS = [
    {"id": "C1", "role": "爽点强化师", "lens": "爽感", "mission": "你是爽点强化师。根据仲裁波的判定,强化本章的爽点:加围观/加反应链/加高光拍。"},
    {"id": "C2", "role": "节奏调音师", "lens": "节奏", "mission": "你是节奏调音师。根据仲裁判定,调整本章节奏:慢的删水/快的加呼吸/匀的加起伏。"},
    {"id": "C3", "role": "去AI化专家", "lens": "AI检测", "mission": "你是去AI化专家。根据仲裁判定,消除AI指纹:加段落方差/加感官词/加意外用词/删签名句式。"},
    {"id": "C4", "role": "代入感工程师", "lens": "代入感", "mission": "你是代入感工程师。根据仲裁判定,加强代入感:加记忆闪回/加内心独白/加感官锚点。"},
    {"id": "C5", "role": "对话医生", "lens": "对话", "mission": "你是对话医生。根据仲裁判定,修复对话:加废话率/加碎片句/加语气词/删复盘腔。"},
    {"id": "C6", "role": "伏笔缝纫师", "lens": "伏笔", "mission": "你是伏笔缝纫师。根据仲裁判定,修补伏笔:该埋的埋/该养的养/该收的收。"},
    {"id": "C7", "role": "角色深化师", "lens": "人物", "mission": "你是角色深化师。根据仲裁判定,深化人物:加内心挣扎/加压力反应/加成长痕迹。"},
    {"id": "C8", "role": "逻辑修补匠", "lens": "逻辑", "mission": "你是逻辑修补匠。根据仲裁判定,修补逻辑漏洞:加过渡/加铺垫/加解释(用行为不用旁白)。"},
    {"id": "C9", "role": "新鲜感守护者", "lens": "新鲜度", "mission": "你是新鲜感守护者。根据仲裁判定,消除重复:换情节模式/换句式/换桥段。"},
    {"id": "C10", "role": "社交货币设计师", "lens": "付费", "mission": "你是社交货币设计师。根据仲裁判定,设计'读者想截图发群'的场面:金句/反转/笑点/高光。"},
]

WAVE5_GUARDS = [
    {"id": "G1", "role": "质量守门员", "lens": "全项", "mission": "你是质量守门员。修复后的版本,重新检查攻击波提出的问题是否已解决。"},
    {"id": "G2", "role": "回归测试员", "lens": "副作用", "mission": "你是回归测试员。修复有没有引入新问题?改了A是不是把B改坏了?"},
    {"id": "G3", "role": "风格一致性守卫", "lens": "风格", "mission": "你是风格守卫。修复后的文风与全书一致吗?有没有'补丁感'?"},
    {"id": "G4", "role": "字数守卫", "lens": "体量", "mission": "你是字数守卫。修复后字数还在卡带内吗?有没有为修而注水?"},
    {"id": "G5", "role": "数字守卫", "lens": "数字", "mission": "你是数字守卫。修复后数字账还对吗?改了金额有没有对不上?"},
    {"id": "G6", "role": "时间线守卫", "lens": "时序", "mission": "你是时间线守卫。修复后的时序还对吗?有没有'昨天下午'变成'今天早上'?"},
    {"id": "G7", "role": "知情状态守卫", "lens": "知情", "mission": "你是知情守卫。修复后'谁知道什么'还对吗?有没有角色突然知道不该知道的?"},
    {"id": "G8", "role": "伏笔守卫", "lens": "伏笔", "mission": "你是伏笔守卫。修复有没有误删伏笔?有没有引入新伏笔但没登记?"},
    {"id": "G9", "role": "AI检测终审", "lens": "AI", "mission": "你是AI检测终审。修复后的版本,重新跑AI指纹八维。全绿才放行。"},
    {"id": "G10", "role": "放行官", "lens": "终审", "mission": "你是放行官。所有守卫全绿,你签字放行。任何一盏红灯,退回修复波。"},
]

WAVES = {
    1: ("攻击波(红队·找问题)", WAVE1_ATTACKERS),
    2: ("辩护波(蓝队·滤误报)", WAVE2_DEFENDERS),
    3: ("仲裁波(评审·综合判定)", WAVE3_ARBITERS),
    4: ("修复波(工匠·定向改进)", WAVE4_CRAFTERS),
    5: ("守卫波(终审·放行/打回)", WAVE5_GUARDS),
}

def gen_wave_prompt(wave_n, agents, target, book, func_type):
    lines = [f"# Agent Storm Wave {wave_n}: {WAVES[wave_n][0]}", ""]
    lines.append(f"功能: {func_type} | 目标: {target} | 书根: {book}")
    lines.append(f"Agent数: {len(agents)}个 | 派发方式: 逐个独立Agent(subagent_type=general-purpose)")
    lines.append("")
    lines.append("## 派发指令(执行者逐个复制prompt派发Agent工具)")
    lines.append("")
    for a in agents:
        lines.append(f"### Agent {a['id']}: {a['role']} [{a['lens']}]")
        lines.append("```")
        lines.append(f"{a['mission']}")
        lines.append("")
        lines.append(f"【操作】只读: {target}")
        lines.append("【锚定】劣锚一(AI腔):'月光如水银泻地...'打分(须<7);劣锚二(流水账):'他早上起床...'打分(须<7)")
        lines.append("【纪律】引原文作证;禁空评;独立判断不受其他agent影响")
        lines.append(f"【输出】{a['lens']}维度评分(1-10)+最致命问题1个(引原文)+JSON行")
        json_tpl = '{"id":"' + a["id"] + '","role":"' + a["role"] + '","score":x.x,"致命问题":"..."}'
        lines.append("末行: " + json_tpl)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)

def main():
    if len(sys.argv) < 3:
        print(__doc__); return 2
    func_type = sys.argv[1]  # chapter|premise|volume|system|periodic
    target = pathlib.Path(sys.argv[2]).resolve()
    if not target.exists():
        print(f"目标不存在: {target}"); return 2
    # 红队修复: 从目标往上找含text/的祖先=书根(兼容任意深度)
    book = target.parent
    while book != book.parent and not (book / "text").is_dir():
        book = book.parent
    if not (book / "text").is_dir():
        book = target.parent  # 兜底

    wave_filter = None
    if "--wave" in sys.argv:
        wave_filter = int(sys.argv[sys.argv.index("--wave") + 1])

    out_dir = book / "audit" / "storm"
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = re.sub(r'[^\w]', '-', target.stem)[:20]

    print(f"═══ Agent Storm: {func_type} / {target.name} ═══")
    print(f"目标: {target}")
    print(f"输出: {out_dir}/")
    print()

    for wn, (label, agents) in WAVES.items():
        if wave_filter and wn != wave_filter:
            continue
        out = out_dir / f"{func_type}-{stem}-wave{wn}.md"
        prompt = gen_wave_prompt(wn, agents, target, book, func_type)
        out.write_text(prompt, encoding="utf-8")
        print(f"  ✅ Wave {wn} {label}: {len(agents)} agents → {out.name}")

    if not wave_filter:
        total = sum(len(a) for _, a in WAVES.values())
        print(f"\n── 总计: 5波 × 10 agents = {total}个subagent ──")
        print(f"── 执行顺序: Wave1(攻击) → Wave2(辩护) → Wave3(仲裁) → Wave4(修复) → Wave5(守卫) ──")
        print(f"── 每波完成后汇总结果,再进下一波(波间有依赖) ──")
    return 0

if __name__ == "__main__":
    sys.exit(main())
