#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quality_score.py 全书45章质量评分器
每个章打一个0-100分。分数越高=读者越可能继续读。
评分维度基于32份审计报告的高频发现加权。

用法: python3 tools/quality_score.py [--json]
"""
import json, math, pathlib, re, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

def cjk(s): return len(re.findall(r"[\u4e00-\u9fff]", s))

def score_chapter(fp):
    t = fp.read_text(encoding="utf-8")
    n = cjk(t)
    paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
    score = 0.0
    details = {}

    # 1. 字数 (20分): 2500-5000满, 线性递减
    if n >= 2500: score += 20
    elif n >= 1500: score += 20 * (n - 1500) / 1000
    details["字数"] = round(min(20, max(0, 20 * (n - 1500) / 1000)), 1)

    # 2. 对话密度 (15分): 40-60%满
    dl = [p for p in paras if "\u201c" in p]
    dia_pct = sum(cjk(p) for p in dl) / n * 100 if n > 0 else 0
    if 40 <= dia_pct <= 60: score += 15
    elif 30 <= dia_pct < 40: score += 15 * (dia_pct - 30) / 10
    elif 60 < dia_pct <= 70: score += 15 * (70 - dia_pct) / 10
    details["对话%"] = round(dia_pct, 1)
    details["对话得分"] = round(min(15, max(0, (15 if 40 <= dia_pct <= 60 else (15*(dia_pct-30)/10 if 30<=dia_pct<40 else (15*(70-dia_pct)/10 if 60<dia_pct<=70 else 0))))), 1)

    # 3. 语气词密度 (10分): ≥8/千字对白满
    dtxt = "".join(re.findall(r"\u201c([^\u201d]*)\u201d", t))
    dl2 = cjk(dtxt)
    tlw = ["啊","呗","嘛","呃","那啥","反正","横竖","嗯","哦","啦","呀"]
    tl = sum(dtxt.count(w) for w in tlw)
    tl_k = tl / dl2 * 1000 if dl2 > 0 else 0
    tl_score = min(10, tl_k / 8 * 10)
    score += tl_score
    details["语气词/千"] = round(tl_k, 1)
    details["语气词得分"] = round(tl_score, 1)

    # 4. 冲突/阻碍 (15分): 有冲突词=满
    conflict_w = ["不行","反对","问题","麻烦","不对","不能","拒绝","不要","失败","坏了","出事","急","但是","可是","然而","砸","亏","查","抓"]
    c_count = sum(1 for w in conflict_w if w in t)
    c_score = min(15, c_count * 1.5)
    score += c_score
    details["冲突词"] = c_count
    details["冲突得分"] = round(c_score, 1)

    # 5. 感官细节 (10分): 视觉外感官
    senses = ["热","冷","凉","烫","湿","干","臭","香","辣","咸","酸","甜","苦","疼","痛","痒","麻","粗糙","光滑","软","硬","刺","滑","粘"]
    s_count = sum(t.count(w) for w in senses)
    s_score = min(10, s_count * 1.5)
    score += s_score
    details["感官词"] = s_count
    details["感官得分"] = round(s_score, 1)

    # 6. 段落形态 (10分): 段均≤30 + 长段≤3 + 有短段
    lens = [cjk(p) for p in paras]
    avg_pl = statistics.mean(lens) if lens else 0
    longs = sum(1 for l in lens if l >= 110)
    shorts = sum(1 for l in lens if l <= 15)
    pl_score = 0
    if avg_pl <= 30: pl_score += 4
    elif avg_pl <= 35: pl_score += 2
    if longs <= 3: pl_score += 3
    elif longs <= 6: pl_score += 1
    if shorts >= 3: pl_score += 3
    score += pl_score
    details["段均"] = round(avg_pl, 1)
    details["长段"] = longs
    details["段落得分"] = round(pl_score, 1)

    # 7. 对白声口 (10分): 每个角色的对白有独特标记
    # 简化: 检查是否有多样化的语气词(不是只用一种)
    tl_types = len(set(w for w in tlw if w in dtxt))
    v_score = min(10, tl_types * 2)
    score += v_score
    details["语气词种类"] = tl_types
    details["声口得分"] = round(v_score, 1)

    # 8. 无机器指纹 (5分): 无判词/无重复/无直引号
    finger = 0
    if t.count('"') > 0: finger += 2
    if t.count("\u2014\u2014") > 3: finger += 1
    if re.search(r"不是[^。」]{1,10}，是[^。」]{1,15}。$", t): finger += 1
    if re.search(r"有一种?账[^。」]{0,10}。$", t): finger += 1
    f_score = max(0, 5 - finger)
    score += f_score
    details["指纹"] = finger
    details["无指纹得分"] = f_score

    return round(min(100, score), 1), details


def cmd_all():
    results = []
    for f in sorted(ROOT.glob("text/卷*/第*.md")):
        s, d = score_chapter(f)
        results.append((f.name, s, d))
    
    results.sort(key=lambda x: x[1])
    print(f"{'章名':<20} {'得分':>6} {'字数':>6} {'对话%':>6} {'段均':>6} {'冲突':>4} {'语气':>4}")
    print("-" * 70)
    for name, s, d in results:
        print(f"  {name:<18} {s:>6.1f} ({d.get('字数',0):>4.0f}字 对话{d.get('对话%',0):>4.0f}% 段均{d.get('段均',0):>4.1f} 冲突{d.get('冲突词',0):>2} 语气{d.get('语气词/千',0):>4.1f})")
    
    avg = statistics.mean(s for _, s, _ in results)
    print(f"\n全书均分: {avg:.1f}/100")
    best = max(results, key=lambda x: x[1])
    worst = min(results, key=lambda x: x[1])
    print(f"最佳: {best[0]} ({best[1]}分)")
    print(f"最差: {worst[0]} ({worst[1]}分)")
    return results


def cmd_json():
    results = []
    for f in sorted(ROOT.glob("text/卷*/第*.md")):
        s, d = score_chapter(f)
        results.append({"file": f.name, "score": s, **d})
    print(json.dumps(results, ensure_ascii=False, indent=1))
    return results


def main():
    results = cmd_all()
    # 保存
    out = [{"file": r[0], "score": r[1]} for r in results]
    (ROOT / "quality_scores.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
