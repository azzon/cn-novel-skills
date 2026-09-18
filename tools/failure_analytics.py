#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""failure_analytics.py 失败模式分析器(问题4: 从反复FAIL中学习,迭代优化系统)

用法: python3 tools/failure_analytics.py [书根]
输出: 全书所有章的FAIL/WARN统计→按频率排序→反馈到PREFIX/卡骨架的优化建议
周期: 每20章跑一次,或卷末跑
"""
import re, sys, subprocess, pathlib, json
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    # 找所有章
    files = sorted(book.glob("text/卷*/第*.md"))
    if not files:
        print("无章节可分析"); return 0

    fail_counter = Counter()
    warn_counter = Counter()

    for f in files:
        r = subprocess.run([sys.executable, str(ROOT/"tools/check.py"), str(f)],
                          capture_output=True, text=True, cwd=ROOT)
        for line in r.stdout.splitlines():
            clean = re.sub(r'\x1b\[\d+m', '', line)
            if "[FAIL]" in clean:
                # 提取错误类型关键词(去掉具体数值)
                err = re.sub(r'\d+', 'N', clean.split("[FAIL]")[1].strip()[:40])
                fail_counter[err] += 1
            elif "[WARN]" in clean:
                err = re.sub(r'\d+', 'N', clean.split("[WARN]")[1].strip()[:40])
                warn_counter[err] += 1

    print(f"═══ 失败模式分析({len(files)}章) ═══\n")

    if fail_counter:
        print("── FAIL频率TOP10(高频=系统指令有缺口,需优化PREFIX/卡骨架) ──")
        for err, cnt in fail_counter.most_common(10):
            print(f"  {cnt:>3}次  {err}")
    if warn_counter:
        print("\n── WARN频率TOP10(高频=生成习惯偏移,需校准) ──")
        for err, cnt in warn_counter.most_common(10):
            print(f"  {cnt:>3}次  {err}")

    # 自动生成优化建议(红队20260919: 从"检测问题"到"优化系统")
    print("\n── 系统优化建议(基于失败模式) ──")
    suggestions = []
    for err, cnt in fail_counter.most_common(5):
        if cnt < 3: continue  # 只处理高频(≥3次)
        if "段落长度方差" in err:
            suggestions.append("段长方差高频FAIL→PREFIX'段落形态'指令需加强;考虑在卡骨架beats中预标'此beat用长段'")
        elif "记忆碎片" in err:
            suggestions.append("记忆碎片高频缺失→素材库'记忆袋'需扩容;卡骨架记忆闪回栏需必填化")
        elif "社交货币" in err:
            suggestions.append("社交货币高频缺失→PREFIX'付费意愿引擎'需更具体;卡骨架爽点扩散槽需加'高光拍预设计'")
        elif "感官词" in err:
            suggestions.append("感官词高频不足→素材库需增感官细节条目;PREFIX感官锚点律需加示例")
        elif "爽感扩散" in err:
            suggestions.append("爽感扩散高频不足→卡骨架扩散槽需从可选变必填")
        elif "重复" in err:
            suggestions.append("重复高频→检查是否补丁工作流导致;强化'整章一次成型'纪律")
        elif "破折号" in err:
            suggestions.append("破折号高频超限→PREFIX中'破折号≤3'位置需前置(当前被埋没)")
        else:
            suggestions.append(f"'{err}'高频({cnt}次)→分析根因,优化对应PREFIX条目或卡骨架字段")

    if suggestions:
        for s in suggestions:
            print(f"  → {s}")
    else:
        print("  无高频失败模式(所有FAIL<3次=正常波动)")

    # 保存分析结果
    out = book / "story" / "audit" / "failure-analytics.md"   # 修正: 与其余audit产物统一story/audit
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(f"# 失败模式分析({len(files)}章)\n\n## FAIL频率\n")
        for err, cnt in fail_counter.most_common(20):
            f.write(f"- {cnt}次: {err}\n")
        f.write("\n## WARN频率\n")
        for err, cnt in warn_counter.most_common(20):
            f.write(f"- {cnt}次: {err}\n")
        if suggestions:
            f.write("\n## 优化建议\n")
            for s in suggestions:
                f.write(f"- {s}\n")
    print(f"\n分析已保存: {out}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
