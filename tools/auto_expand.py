#!/usr/bin/env python3
"""auto_expand.py 自动扩写器(自动化目标④)

流程效率审计: 首稿欠卡带20-40%是AI执笔稳定病灶。本工具从正文自动识别欠密beat,
给出扩写建议(不直接生成正文——正文生成仍由LLM完成,本工具做术前诊断)。

用法:
  python3 tools/auto_expand.py <章节文件> [--target 2400]   # 诊断+建议
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def analyze(fp, target=2400):
    t = fp.read_text(encoding="utf-8")
    cjk = len(re.sub(r"[^\u4e00-\u9fff]", "", t))
    paras = [p.strip() for p in t.splitlines() if p.strip()]
    short_paras = [p for p in paras if len(p) < 30]
    long_paras = [p for p in paras if len(p) > 110]

    issues = []
    deficit = target - cjk
    if deficit > 0:
        issues.append(f"字数欠{deficit}字(target={target})")

    # 段落分析
    if len(short_paras) / max(len(paras), 1) > 0.5:
        issues.append(f"短段过多({len(short_paras)}/{len(paras)})——碎片化风险")

    # 对话密度
    dia_lines = [p for p in paras if "“" in p or '"' in p]
    dia_ratio = len(dia_lines) / max(len(paras), 1)
    if dia_ratio < 0.3:
        issues.append(f"对话段占比{dia_ratio:.0%}(<30%)——需加对话回合")

    # 心理密度
    psych = len(re.findall(r"他[想觉得]|她[想觉得]|心里|暗想", t))
    psych_per_k = psych / cjk * 1000 if cjk else 0
    if psych_per_k < 1.5:
        issues.append(f"心理{psych_per_k:.1f}/千字(<1.5)——需加内心beat")

    # 金额
    money = len(re.findall(r"\d+[两贯文石块元毛]", t))
    if money < 2:
        issues.append(f"金额{money}处(<2)——需加钱过手")

    # 语气词
    tl = len(re.findall(r"[啊呗嘛呢吧呀哦嘛]", "".join(dia_lines)))
    tl_per_k = tl / max(len("".join(dia_lines)), 1) * 1000
    if tl_per_k < 3:
        issues.append(f"语气词{tl_per_k:.1f}/千字(<3)——需加语气词")

    # 扩写建议
    suggestions = []
    if deficit > 100:
        beats_needed = deficit // 200
        suggestions.append(f"扩{beats_needed}个beat×200字")
    if dia_ratio < 0.3:
        suggestions.append("加一组对话回合(带引导语和动作)")
    if psych_per_k < 1.5:
        suggestions.append("加心理beat(他想/他知道/他明白)")
    if money < 2:
        suggestions.append("加金额细节(X两/X文)")
    if tl_per_k < 3:
        suggestions.append("对白加语气词(啊/呗/嘛)")

    return {
        "cjk": cjk, "target": target, "deficit": deficit,
        "paras": len(paras), "dia_ratio": round(dia_ratio * 100, 1),
        "psych_per_k": round(psych_per_k, 1),
        "money": money, "tl_per_k": round(tl_per_k, 1),
        "issues": issues, "suggestions": suggestions,
    }


def main():
    args = sys.argv[1:]
    target = 2400
    if "--target" in args:
        target = int(args[args.index("--target") + 1])
        args = [a for a in args if not a.startswith("--") and a != str(target)]
    if not args:
        print(__doc__)
        return 2
    fp = pathlib.Path(args[0])
    if not fp.exists():
        print(f"文件不存在: {fp}")
        return 2
    r = analyze(fp, target)
    print(f"═══ {fp.name} 扩写诊断 ═══")
    print(f"  字数: {r['cjk']} / target {r['target']} (欠{r['deficit']})")
    print(f"  对话: {r['dia_ratio']}% | 心理: {r['psych_per_k']}/千字 | 金额: {r['money']}处 | 语气词: {r['tl_per_k']}/千字")
    if r["issues"]:
        print(f"\n  待修({len(r['issues'])}项):")
        for i in r["issues"]:
            print(f"    · {i}")
    if r["suggestions"]:
        print(f"\n  扩写建议:")
        for s in r["suggestions"]:
            print(f"    → {s}")
    if not r["issues"]:
        print("  ✅ 全部达标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
