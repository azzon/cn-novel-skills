#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate_chapter.py 章级机器门(v3) —— 上下文韧性事故(见 audits/10)的机械防护
用法:
  python3 tools/gate_chapter.py text/卷4/第080章.md ...   # 对staged章节跑全部门
  python3 tools/gate_chapter.py --recompute               # 从文件系统实扫重算 .progress.json
门清单:
  G1 字数硬底线      CJK<1500 FAIL(回beat-expand) / <2000 WARN
  G2 章号重复门      新章章号与库内既有章重复 → FAIL(防"重复写章"事故A)
  G3 标题重复门      章标题与既有章完全相同 → FAIL
  G4 卷归属门        章号必须落入该卷区间或为末卷max+1 → FAIL(防"错放卷"事故B)
  G5 跨章查重门      18字shingle与既有章重叠率>15% → FAIL / >8% WARN(防内容复写)
  G6 时序提醒门      时间线存在时提醒确认新章故事时间不早于末次记录(账建全后硬化)
  G7 .progress.json  --recompute: 文件系统是唯一权威,本文件只是派生缓存
仅用标准库。
"""
import sys, re, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROGRESS = ROOT / ".progress.json"
TIMELINE = ROOT / "ledgers" / "时间线.md"

def cjk_len(t):
    return len(re.findall(r"[\u4e00-\u9fff]", t))

def chapter_files():
    return sorted(ROOT.glob("text/卷*/第*章.md"))

def parse_num(p):
    m = re.search(r"第(\d+)章", p.name)
    return int(m.group(1)) if m else None

def parse_vol(p):
    m = re.search(r"卷(\d+)", str(p))
    return f"卷{m.group(1)}" if m else None

def scan_volumes(files):
    vols = {}
    for p in files:
        v = parse_vol(p)
        n = parse_num(p)
        if v and n is not None:
            lo, hi = vols.get(v, (10**9, -1))
            vols[v] = (min(lo, n), max(hi, n))
    order = sorted(vols, key=lambda v: int(re.search(r"\d+", v).group()))
    return {v: list(vols[v]) for v in order}

def expected_volume(n, volumes):
    """章号→期望卷: 落入区间用该卷; 大于所有max→末卷(max+1顺写); 落入间隙/小于所有min→None(异常)"""
    for v, (lo, hi) in volumes.items():
        if lo <= n <= hi:
            return v
    maxes = {v: hi for v, (lo, hi) in volumes.items()}
    last = max(maxes, key=lambda v: maxes[v])
    if n > maxes[last]:
        return last
    return None

def shingles(text, k=18):
    clean = re.sub(r"\s+", "", text)
    return {clean[i:i+k] for i in range(len(clean) - k + 1)}

def recompute():
    files = chapter_files()
    nums = [parse_num(p) for p in files]
    vols = scan_volumes(files)
    story_time = None
    if TIMELINE.exists():
        lines = [l for l in TIMELINE.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            story_time = lines[-1].strip()[:80]
    maxn = max(nums) if nums else 0
    last_vol = max(vols, key=lambda v: vols[v][1]) if vols else "卷1"
    data = {
        "max_chapter": maxn,
        "count": len([x for x in nums if x is not None]),
        "next_chapter": maxn + 1,
        "volumes": vols,
        "story_time": story_time,
        "next_action": f"pipeline-chapter 第{maxn+1:03d}章({expected_volume(maxn+1, vols) or last_vol})",
        "_comment": "本文件由tools/gate_chapter.py --recompute自动生成,禁止手写;文件系统是唯一权威",
    }
    PROGRESS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[progress] max={maxn} next={maxn+1} volumes={vols}")
    return 0

def main():
    args = sys.argv[1:]
    if "--recompute" in args:
        return recompute()

    # 模式: new=新增章(字数硬门) / modified=修改存量章(字数降为WARN,回炉走beat-expand计划)
    mode = "modified"
    if args and args[0] in ("new", "modified"):
        mode = args.pop(0)

    staged = [pathlib.Path(a) for a in args if not a.startswith("--")]
    if not staged:
        print("用法: gate_chapter.py <章节文件...> | --recompute")
        return 2

    files = chapter_files()
    existing = {}   # num -> path (工作区现状, 不含本次staged路径)
    staged_paths = {str(p.resolve()) for p in staged}
    for p in files:
        if str(p.resolve()) in staged_paths:
            continue
        n = parse_num(p)
        if n is not None:
            existing[n] = p

    volumes = scan_volumes(files + staged)
    fail_total = 0
    for p in staged:
        problems, warns = [], []
        n = parse_num(p)
        raw = p.read_text(encoding="utf-8") if p.exists() else ""
        body = "\n".join(l for l in raw.splitlines() if l.strip() and not l.startswith("#"))
        title = raw.splitlines()[0].strip() if raw.splitlines() else ""

        # G1 字数硬底线(只卡新增章;存量章回炉是计划内工作)
        cn = cjk_len(body)
        if cn < 1500:
            if mode == "new":
                problems.append(f"G1字数硬底线: 新章仅{cn}字(<1500)——禁止入库,beat-expand扩写到≥1500字再提交")
            else:
                warns.append(f"G1存量短章{cn}字(<1500)——已列入回炉清单(beat-expand),修文可入库,扩写前不得作为首发库存")
        elif cn < 2000:
            warns.append(f"G1字数{cn}(<2000,目标2500-3200)")

        # G2 章号重复门
        if n is not None and n in existing:
            problems.append(f"G2章号重复: 第{n}章已存在于{existing[n].relative_to(ROOT)}——重复写章(事故A),如为改写请用原路径,如为插章需arc-restructure重编号")

        # G3 标题重复门
        if title:
            for num2, p2 in existing.items():
                t2 = p2.read_text(encoding="utf-8").splitlines()[0].strip() if p2.exists() else ""
                if t2 and t2 == title:
                    problems.append(f"G3标题重复: 「{title}」与{p2.relative_to(ROOT)}相同")

        # G4 卷归属门
        if n is not None:
            exp = expected_volume(n, volumes)
            act = parse_vol(p)
            if exp is None:
                problems.append(f"G4卷归属: 第{n}章落入卷间隙或早于所有卷起点(区间{volumes})——需arc-restructure")
            elif act != exp:
                problems.append(f"G4卷归属: 第{n}章应属{exp},实际在{act}——错放卷(事故B)")

        # G5 跨章查重门
        if body:
            sh_new = shingles(body)
            worst, worst_p = 0.0, None
            for num2, p2 in existing.items():
                try:
                    old = "\n".join(l for l in p2.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#"))
                except Exception:
                    continue
                if not old:
                    continue
                sh_old = shingles(old)
                if not sh_new:
                    continue
                ov = len(sh_new & sh_old) / len(sh_new)
                if ov > worst:
                    worst, worst_p = ov, p2
            if worst > 0.15:
                problems.append(f"G5跨章查重: 与{worst_p.name if worst_p else '?'}相似度{worst:.0%}(>15%)——内容复写,必须重写或arc-restructure")
            elif worst > 0.08:
                warns.append(f"G5跨章查重: 与{worst_p.name if worst_p else '?'}相似度{worst:.0%}(>8%,检查是否自我复读)")

        # G6 时序提醒
        if TIMELINE.exists():
            warns.append("G6时序自检: 确认本章故事时间不早于ledgers/时间线.md末次记录,回退须标'插叙:'并走arc-restructure")

        print(f"\n=== gate_chapter [{p.name}] {'FAIL' if problems else 'PASS'} ===")
        for x in problems:
            print(f"  [FAIL] {x}")
        for w in warns:
            print(f"  [WARN] {w}")
        fail_total += len(problems)

    if fail_total:
        print(f"\n汇总: {fail_total}项FAIL")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
