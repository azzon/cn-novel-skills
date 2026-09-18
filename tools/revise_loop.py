#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revise_loop.py 自动迭代修复回路(问题1: 检测到不合格→诊断→定向处方→复检)

用法: python3 tools/revise_loop.py <章文件> [最大轮数]
流程: check.py检测 → 解析FAIL/WARN → 按错误类型给出定向处方 → 等待修复 → 复检
     循环直到全过或达最大轮数(默认5)
"""
import re, sys, subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 错误类型→定向处方映射(红队20260919: 从"打回重写"到"告诉AI具体怎么改")
PRESCRIPTIONS = {
    "章级字数": "beat-expand: 按卡上beats预算扩写欠密的beat,禁注水;每个beat至少加1个感官细节+1句对话",
    "破折号": "把破折号改成句号或逗号;保留最多3处最有戏剧张力的",
    "明喻": "删到3处以内;优先删'像是''仿佛'开头的;用白描替代(直接写物象)",
    "装饰性修辞": "删到3处以内;AI标志=每个描写点都挂比喻,真人白描为主",
    "情绪告知": "改写为行为: '他很震惊'→'他手里的茶杯晃了一下,水洒在裤子上'",
    "段落长度方差": "加入3个超短独立段(≤5字: '有了。''不对。''就是它。')+3个长段(80-200字,蓄压/织线/闲笔)",
    "原样重复": "找到重复段落,删除旧版保留新版;如果是补丁残留,整段清创重写",
    "拼装疤": "两版场景并存=补丁事故;保留新版,删除旧版",
    "对话字数占比": "加对话: 让角色开口说废话/跑题/答非所问;每3-5句台词插1段动作/心理",
    "心理活动": "加内心独白: '他想''心里一沉''忽然想起';每千字2处",
    "记忆碎片": "加感官记忆闪回: 当前感官→'那年...'+画面30-60字(从素材库记忆袋取)",
    "社交货币": "加高光拍: 全场愣住/拍桌叫好/炸了围观;兑现拍末80-150字反应链",
    "感官词密度": "加具体感官词: 浆糊味/冰凉/硌手/发霉/消毒水(味/触/嗅优先)",
    "爽感扩散": "爽点兑现处加围观: 谁看见了?谁传开了?个人愣→全场炸→有人传话",
    "转折密度": "每章至少2次价值翻转;在beats中设计反转拍(却/谁知/没想到)",
    "章末钩子": "末三行加悬念/中断/情绪峰值;用'来了''开门''转身'等钩信号词",
    "引号": "跑 python3 tools/fix_quotes.py <文件>",
    "英文残留": "删除所有拉丁字母词;人名除外(K-7等前情既定)",
    "工程词": "删除元层词汇(伏笔/爽点/beat/场景卡等);用故事内语言替代",
    "旁白判词": "删段尾抽象总结句;画面已把话说完",
    "连续.*纯对话": "每3-5句台词插1段动作/心理/环境描写(织毛衣法)",
}

def get_issues(fp):
    r = subprocess.run([sys.executable, str(ROOT/"tools/check.py"), str(fp)],
                       capture_output=True, text=True, cwd=ROOT)
    fails, warns = [], []
    for line in r.stdout.splitlines():
        if "[FAIL]" in line: fails.append(line.strip())
        elif "[WARN]" in line: warns.append(line.strip())
    return fails, warns

def prescribe(fail_msg):
    """根据FAIL消息给出定向处方"""
    for pattern, rx in PRESCRIPTIONS.items():
        if re.search(pattern, fail_msg):
            return rx
    return "通读FAIL信息,按错误类型定向修改;改完重跑check.py"

def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    fp = pathlib.Path(sys.argv[1])
    if not fp.exists():
        print(f"文件不存在: {fp}"); return 2
    max_rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    for round_n in range(1, max_rounds + 1):
        fails, warns = get_issues(fp)
        print(f"\n═══ 迭代修复 第{round_n}/{max_rounds}轮 ═══")
        if not fails:
            print(f"  ✅ FAIL清零 ({len(warns)}条WARN待处理)")
            if warns:
                print(f"\n  WARN处方:")
                for w in warns:
                    print(f"    ⚠️ {w[7:60]}")
                    print(f"       → {prescribe(w)}")
            return 0
        print(f"  ❌ {len(fails)}项FAIL:")
        for f in fails:
            # 提取错误核心
            core = re.sub(r'\x1b\[\d+m', '', f)  # 去颜色码
            print(f"    • {core[8:70]}")
            rx = prescribe(core)
            print(f"      → 处方: {rx}")
        print(f"\n  修复后重跑: python3 tools/revise_loop.py {fp}")
        return 1
    return 1

if __name__ == "__main__":
    sys.exit(main())
