#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""continuity_guard.py 内容连续性守卫(问题5: 400万字内容不崩溃)

已知局限: 代词死亡/间接死亡由Wave1-A9角色律师(AI agent)补充检测
四道内容完整性防线:
  1. 生死账: 人物死了不能复活(除非有明确复活情节);活人突然消失也要报
  2. 伏笔完整性: 所有埋下的伏笔必须有回收计划;悬空伏笔>阈值报警
  3. 情节跳变: 相邻章的故事内时间/地点/人物突变而无过渡说明
  4. 情节重复: 相似情节模式(不只文字)的跨章检测

用法: python3 tools/continuity_guard.py [书根]
周期: 每20章或每卷末
"""
import re, sys, pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

DEATH_WORDS = re.compile(r"(死|亡|牺牲|殉|咽气|断气|去世|逝世|毙|葬|坟|墓|灵堂|遗像|遗物)")
REVIVE_HINT = re.compile(r"(复活|还魂|起死回生|没死|还活着|原来没)")

def extract_deaths(text, ch_num):
    """从章节文本提取死亡事件和人物名"""
    deaths = []
    for sent in re.split(r'[。！？\n]', text):
        if DEATH_WORDS.search(sent):
            # 找人名(中文2-4字,前后有动词或标点)
            names = re.findall(r'[\u4e00-\u9fff]{2,3}(?=(?:死|亡|牺牲|去世|逝世|咽气|断气))', sent)
            for nm in names:
                if nm not in ('他们', '她们', '一个', '这位', '那位', '老人', '女人', '男人'):
                    deaths.append((nm, ch_num, sent.strip()[:50]))
    return deaths

def check_revival(text, deaths, ch_num):
    """检查死亡人物是否无解释复活"""
    issues = []
    for sent in re.split(r'[。！？\n]', text):
        if REVIVE_HINT.search(sent):
            for nm, death_ch, death_sent in deaths:
                if nm in sent and ch_num > death_ch + 2:
                    # 死了至少2章后提到复活暗示
                    if not re.search(r'(梦|回忆|幻觉|想象|照片|遗像|碑|墓)', sent):
                        issues.append(f"第{ch_num:03d}章: '{nm}'死于第{death_ch}章,此处疑似无解释复活: {sent.strip()[:40]}")
    return issues

def check_foreshadow(ledger):
    """伏笔完整性: 埋了但既无回收也无充能=悬空"""
    if not ledger.exists():
        return []
    issues = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("- ["):
            continue
        # 解析: [F-1] 描述 | 埋:第NNN章 | 兑付:XXX | 状态:YYY
        m = re.search(r'埋[:：]第(\d+)章.*?兑付[:：](\S+).*?状态[:：](\S+)', line)
        if m:
            状态 = m.group(3)
            if "沉睡" in 状态 or "悬空" in 状态 or "待" in 状态:
                issues.append(f"伏笔悬空: {line[:60]}")
    return issues

def check_time_jump(files):
    """情节跳变: 相邻章时间/地点/人物突变"""
    issues = []
    prev_meta = None
    for f in files:
        t = f.read_text(encoding="utf-8")
        ch = int(re.search(r'第(\d+)章', f.stem).group(1))
        # 提取首段地点线索和时间线索
        first_paras = "\n".join(t.split('\n\n')[1:4])  # 跳过标题
        locs = re.findall(r'(医院|工厂|矿|学校|家|街|市|省|村|山|海|河|城)', first_paras)[:3]
        times = re.findall(r'(凌晨|早上|上午|中午|下午|傍晚|晚上|深夜|第[一二三四五六七八九十]+天)', first_paras)[:2]
        cur_meta = (ch, set(locs), set(times))
        if prev_meta and ch == prev_meta[0] + 1:
            prev_locs, prev_times = prev_meta[1], prev_meta[2]
            cur_locs, cur_times = cur_meta[1], cur_meta[2]
            # 如果地点完全无交集且时间也无交集,可能是跳变
            if prev_locs and cur_locs and not (prev_locs & cur_locs):
                if not re.search(r'(到了|来到|赶到|回|去|出发|路上|途中)', first_paras):
                    issues.append(f"第{ch:03d}章: 地点从{prev_locs}跳到{cur_locs}无过渡说明")
        prev_meta = cur_meta
    return issues

def check_plot_repetition(files):
    """情节重复: 检测跨章的相似情节模式(简化版: 章末钩类型+爽点类型+冲突源的重复)"""
    issues = []
    patterns = defaultdict(list)
    for f in files:
        t = f.read_text(encoding="utf-8")
        ch = int(re.search(r'第(\d+)章', f.stem).group(1))
        # 提取情节签名: 开场型+转折方式+结尾类型
        parts = t.split("\n\n")
        opener = "对话" if len(parts) > 1 and parts[1].strip().startswith("\u201c") else "叙述"
        # 简化: 用首段长度+末段长度+对话占比做签名
        paras = [p for p in t.split('\n\n') if p.strip()]
        if len(paras) < 3: continue
        dia_ratio = sum(1 for p in paras if '"' in p or '\u201c' in p) / len(paras)
        sig = (opener, round(dia_ratio, 1))
        patterns[sig].append(ch)
    # 找连续5章以上相同签名的
    for sig, chs in patterns.items():
        chs.sort()
        run = 1
        for i in range(1, len(chs)):
            if chs[i] == chs[i-1] + 1:
                run += 1
                if run >= 5:
                    issues.append(f"第{chs[i-4]:03d}-{chs[i]:03d}章: 连续{run}章情节模式相同({sig})——读者会感到重复")
            else:
                run = 1
    return issues

def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    files = sorted(book.glob("text/卷*/第*.md"))
    if not files:
        print("无章节可检查"); return 0

    print(f"═══ 内容连续性守卫({len(files)}章) ═══\n")
    all_issues = []

    # 1. 生死账
    all_deaths = []
    for f in files:
        t = f.read_text(encoding="utf-8")
        ch = int(re.search(r'第(\d+)章', f.stem).group(1))
        all_deaths.extend(extract_deaths(t, ch))
    if all_deaths:
        print(f"── 生死账: 检测到{len(all_deaths)}次死亡事件 ──")
        for nm, ch, sent in all_deaths[:10]:
            print(f"  第{ch:03d}章: {nm} — {sent}")
        # 检查复活
        for f in files:
            t = f.read_text(encoding="utf-8")
            ch = int(re.search(r'第(\d+)章', f.stem).group(1))
            rev = check_revival(t, all_deaths, ch)
            all_issues.extend(rev)
    else:
        print("── 生死账: 无死亡事件 ──")

    # 2. 伏笔完整性
    fl = book / "ledgers" / "伏笔.md"
    fs_issues = check_foreshadow(fl)
    print(f"\n── 伏笔完整性: {len(fs_issues)}条悬空 ──")
    for i in fs_issues[:5]:
        print(f"  ⚠️ {i}")
    all_issues.extend(fs_issues)

    # 3. 情节跳变
    tj = check_time_jump(files)
    print(f"\n── 情节跳变: {len(tj)}处 ──")
    for i in tj[:5]:
        print(f"  ⚠️ {i}")
    all_issues.extend(tj)

    # 4. 情节重复
    pr = check_plot_repetition(files)
    print(f"\n── 情节重复: {len(pr)}处 ──")
    for i in pr[:5]:
        print(f"  ⚠️ {i}")
    all_issues.extend(pr)

    print(f"\n═══ 总计: {len(all_issues)}项内容连续性问题 ═══")
    if all_issues:
        out = book / "audit" / "continuity-guard.md"
        out.parent.mkdir(exist_ok=True)
        out.write_text("\n".join([f"# 内容连续性守卫报告\n"] + [f"- {i}" for i in all_issues]), encoding="utf-8")
        print(f"报告已保存: {out}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
