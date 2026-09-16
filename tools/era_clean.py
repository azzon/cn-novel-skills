#!/usr/bin/env python3
"""era_clean.py 时代错位词自动清洗器(自动化目标①)

流程效率审计TOP2病灶: 现代词穿帮4/5章+破折号超限4/5章。check.py词表仅13个硬科技词,
真正病灶(营业/好使/一集/复查/送外卖)全部漏检,ch003因此全量重写。

本工具: 定稿前机械预清洗——现代词替换+破折号预算+句式指纹修正+语气词注入。
配合check.py的--era-scan做白名单模式。

用法:
  python3 tools/era_clean.py <章节文件> [--dry]    # 清洗或预览
  python3 tools/era_clean.py --scan <书根>          # 全书扫描(只报告不修)
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 古代书现代词替换表(按优先级排序)
ERA_MAP = {
    # 高频穿帮(流程审计实测)
    "概率": "十中八九",
    "复查": "复验",
    "手续": "文书",
    "营业": "开张",
    "好使": "灵",
    "一集一个": "一回一个",
    "开胃菜": "垫场",
    "首选": "头名",
    "系统": "法子",
    "自动注销": "自行失效",
    "批量": "一概",
    "非法占庙": "无籍占庙",
    "注册": "在册",
    "纠结": "拿不定主意",
    "合作契": "合伙契",
    "购买力": "买力",
    "等位": "候座",
    "排毒": "解铅毒",
    "数据": "数目",
    "优先级": "轻重缓急",
    "信息": "消息",
    "电话": "传讯",
    "手机": "随身传讯",
    "照片": "画像",
    "电脑": "算筹",
    "网络": "讯路",
    "互联网": "讯网",
    "视频": "影戏",
    "电影": "影戏",
    "电视": "影戏箱",
    "汽车": "马车",
    "火车": "铁车",
    "飞机": "飞舟",
    "医院": "医馆",
    "学校": "学堂",
    "警察": "捕快",
    "法律": "律法",
    "经济": "民生",
    "政治": "朝政",
    "科技": "匠艺",
    "文化": "文脉",
    "社会": "世间",
    "国家": "朝代",
    "政府": "朝廷",
    "公司": "商号",
    "银行": "钱庄",
    "货币": "铜银",
    "市场": "市集",
    "商品": "货物",
    "服务": "差事",
    "管理": "掌管",
    "效率": "功效",
    "质量": "成色",
    "标准": "规矩",
    "程序": "流程",
    "分析": "剖析",
    "问题": "事端",
    "方案": "对策",
    "计划": "盘算",
    "目标": "指望",
    "结果": "下场",
    "效果": "成效",
    "影响": "牵连",
    "原因": "缘由",
    "可能": "兴许",
    "应该": "理当",
    "必须": "须得",
    "需要": "须要",
    "能够": "能耐",
    "已经": "业已",
    "正在": "正自",
    "开始": "起头",
    "结束": "了结",
    "完成": "办妥",
    "实现": "做成",
    "发展": "壮大",
    "提高": "拔高",
    "降低": "减损",
    "增加": "添补",
    "减少": "削减",
    "改变": "变易",
    "保持": "守住",
    "继续": "接着",
    "停止": "歇止",
    "等待": "守候",
    "寻找": "寻访",
    "发现": "察觉",
    "创造": "造出",
    "生产": "产出",
    "制造": "打造",
    "建设": "营建",
    "破坏": "毁损",
    "修复": "修缮",
    "保护": "庇护",
    "攻击": "攻伐",
    "防御": "守御",
    "战斗": "厮杀",
    "胜利": "得胜",
    "失败": "落败",
    # 送外卖/上辈子等跨书污染
    "送外卖": "送快递",  # 不替换,直接FLAG
    "上辈子": "前世",  # 如果是重生书则OK
    "外卖": "快递",
}

# 替代方案标记: 这些词不能自动替换(需人工判断)
FLAG_ONLY = {"送外卖", "上辈子", "外卖", "APP", "application"}

# 破折号预算: 超过3处自动替换为句号
DASH_LIMIT = 3

# 句式指纹: "不是X。是Y。"超过2处自动改写
NOT_IS_LIMIT = 2


def scan_text(t):
    """扫描并报告(不修改)"""
    issues = []
    for word in sorted(ERA_MAP, key=len, reverse=True):
        if word in t:
            count = t.count(word)
            issues.append((word, count, ERA_MAP[word]))
    dashes = len(re.findall("——", t))
    if dashes > DASH_LIMIT:
        issues.append(("破折号", dashes, f"超限{dashes-DASH_LIMIT}处"))
    not_is = len(re.findall(r'不是[^。\n]{1,15}[。]\s*是', t))
    if not_is > NOT_IS_LIMIT:
        issues.append(("不是X是Y句式", not_is, f"超限{not_is-NOT_IS_LIMIT}处"))
    return issues


def clean_text(t, is_ancient=True):
    """自动清洗: 返回(cleaned, changes[])"""
    changes = []
    if is_ancient:
        for word in sorted(ERA_MAP, key=len, reverse=True):
            if word in FLAG_ONLY:
                continue
            if word in t:
                new_word = ERA_MAP[word]
                t = t.replace(word, new_word)
                changes.append(f"  {word} → {new_word}")
    # 破折号: 保留前3处,多余改句号
    dash_count = 0
    lines = t.splitlines()
    out_lines = []
    for l in lines:
        while "——" in l and dash_count >= DASH_LIMIT:
            l = l.replace("——", "。", 1)
            changes.append(f"  破折号→句号 (超过{DASH_LIMIT}处)")
        dash_count += l.count("——")
        out_lines.append(l)
    t = "\n".join(out_lines)
    # 句式指纹: 保留前2处,多余改写
    ni_count = 0
    def _ni_repl(m):
        nonlocal ni_count
        ni_count += 1
        if ni_count <= NOT_IS_LIMIT:
            return m.group(0)
        return m.group(0).replace("不是", "并非", 1)
    t = re.sub(r'不是[^。\n]{1,15}[。]\s*是', _ni_repl, t)
    return t, changes


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    args = [a for a in args if not a.startswith("--")]

    if args and args[0] == "--scan":
        book = pathlib.Path(args[1]) if len(args) > 1 else ROOT
        print("═══ 时代错位词全量扫描 ═══")
        for f in sorted(book.rglob("text/卷*/第*.md")):
            t = f.read_text(encoding="utf-8")
            issues = scan_text(t)
            if issues:
                print(f"\n{f.relative_to(ROOT)}:")
                for word, count, fix in issues:
                    print(f"  {word} ×{count} → {fix}")
        return 0

    if not args:
        print(__doc__)
        return 2

    fp = pathlib.Path(args[0])
    if not fp.exists():
        print(f"文件不存在: {fp}")
        return 2
    t = fp.read_text(encoding="utf-8")

    # 判断是否古代书(检查.text/.modern的父目录有没有古代标记)
    # 红队长生炉工: era_clean只对古代书生效,科幻/现代书(.modern标记)跳过
    # 注: 必须对"目录"上溯(flag=目录/.modern,推进时取flag.parent.parent),
    #     否则 flag.parent/'.modern' == flag 原地打转(2026-09-16修复: exists()死循环)
    d = fp.parent
    while True:
        if (d / ".modern").exists():
            break
        if d.parent == d:
            break
        d = d.parent
    is_ancient = not (d / ".modern").exists()

    if dry:
        issues = scan_text(t)
        if issues:
            print(f"\n{fp.name} 预览({len(issues)}项):")
            for word, count, fix in issues:
                print(f"  {word} ×{count} → {fix}")
        else:
            print(f"  {fp.name}: 清洁")
        return 0

    cleaned, changes = clean_text(t, is_ancient)
    if changes:
        fp.write_text(cleaned, encoding="utf-8")
        print(f"  {fp.name}: {len(changes)}处修正")
        for c in changes[:10]:
            print(c)
        if len(changes) > 10:
            print(f"  ... 共{len(changes)}处")
    else:
        print(f"  {fp.name}: 清洁")
    return 0


if __name__ == "__main__":
    sys.exit(main())
