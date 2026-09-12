#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""structure_check.py 跨章结构同构检测(大审计-08设计)

逐章提取三类结构特征并统计全书分布:
  开场型: 时间状语/判断句("X是Y")/对话直入/动作直入
  收尾型: 短句重音/对话切/日记收账/叙述收
  场景数: 独立句号段("。"独行)计数+1
任一特征占比>60% WARN, >80% FAIL(防"21章同一引擎")。
用法: python3 tools/structure_check.py [text/卷1 ...]  (缺省扫text/卷*)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TIME_PAT = re.compile(r"^(第?[一二三四五六七八九十百0-9]+[章日天早晚月年]|开春|进了腊月|正月|入了|那年|当年|次日|第二天|当天|礼拜|周五|周二|深夜|凌晨|傍晚|天黑|十月|十一月|十二月|三月)")
JUDGE_PAT = re.compile(r"^[^\u201c，。！？]{1,12}(是|就是)[^，。！？]{1,20}。")

def cjk(t):
    return len(re.findall(r"[\u4e00-\u9fff]", t))

def classify_open(paras):
    p = paras[0].strip()
    if p.startswith("\u201c"):
        return "对话直入"
    if TIME_PAT.match(p):
        return "时间状语"
    if JUDGE_PAT.match(p):
        return "判断句"
    return "动作直入"

def classify_end(paras):
    tail = [x.strip() for x in paras[-3:]]
    last = tail[-1]
    joined = "".join(tail)
    if "日记本" in joined or re.search(r"(写|记)(了|上)(一|两)行", joined):
        return "日记收账"
    if cjk(last) <= 15 and "\u201c" not in last:
        return "短句重音"
    if last.endswith("\u201d"):
        return "对话切"
    return "叙述收"

def scan(files):
    data = []
    for f in files:
        t = f.read_text(encoding="utf-8-sig")
        paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
        # 跳过标题行(大审计-18 P0-2: 标题"第N章"恒判时间状语=度量假象)
        paras = [p for p in paras if not re.match(r"^第[一二三四五六七八九十百0-9]+章", p)]
        if len(paras) < 3:
            continue
        scenes = sum(1 for p in paras if p == "。") + 1
        data.append({
            "file": f.name, "open": classify_open([paras[0]]),
            "end": classify_end(paras), "scenes": scenes,
        })
    return data

def dist(items, key):
    d = {}
    for it in items:
        d[it[key]] = d.get(it[key], 0) + 1
    n = len(items)
    return {k: (v, round(v / n * 100)) for k, v in d.items()}

def main():
    dirs = sys.argv[1:] or [str(ROOT / "text" / "卷1")]
    files = []
    for d in dirs:
        files += sorted(pathlib.Path(d).glob("第*章.md"))
    if not files:
        print("未找到章节文件"); return 2
    data = scan(files)
    n = len(data)
    print(f"跨章结构同构检测: {n}章")
    fails, warns = 0, 0
    for key, spec in (("open", "开场型"), ("end", "收尾型")):
        print(f"── {spec}分布 ──")
        for k, (cnt, pct) in sorted(dist(data, key).items(), key=lambda x: -x[1][0]):
            mark = ""
            eff = max(pct, pct * n / 10)  # 小样本(n<10)降级
            if pct > 80 and n >= 10:
                mark = "  [FAIL] 同构固化"; fails += 1
            elif eff > 60:
                mark = "  [WARN] 占比超标(小样本)"; warns += 1
            print(f"  {k}: {cnt}章 ({pct}%){mark}")
    scenes = [d["scenes"] for d in data]
    import statistics
    print(f"── 场景数: 均值{statistics.mean(scenes):.1f} 标准差{statistics.stdev(scenes) if n>1 else 0:.1f} "
          f"(标准差<1=节奏机械) ──")
    for d in data:
        print(f"  {d['file']}: 开={d['open']} 收={d['end']} 场={d['scenes']}")
    if fails:
        print("结构门: FAIL"); return 1
    if warns:
        print("结构门: WARN"); return 0
    print("结构门: PASS"); return 0

if __name__ == "__main__":
    sys.exit(main())
