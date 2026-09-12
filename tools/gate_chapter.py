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

def _shingles(s, k=12):
    c = re.sub(r"[\s，。！？；：、\u201c\u201d]", "", s)
    return {c[i:i+k] for i in range(max(0, len(c)-k+1))}

def cross_chapter_dup(staged_bodies, corpus_paras):
    """G8跨章贴入门: staged章的段落与存量章段落shingle相似>0.85=贴入残留(006→009事故形状)。
    返回[(staged段预览, 存量文件, 相似度)]"""
    hits = []
    corpus = [(f, _shingles(x)) for f in corpus_paras for x in corpus_paras[f] if cjk_len(x) >= 40]
    for para in staged_paras:
        if cjk_len(para) < 40:
            continue
        sp = _shingles(para)
        if len(sp) < 3:
            continue
        for f, cp in corpus:
            inter = len(sp & cp)
            if inter and inter / min(len(sp), len(cp)) > 0.85:
                hits.append((para[:24], f, round(inter/min(len(sp),len(cp)), 2)))
                break
    return hits

def chapter_files():
    return sorted(ROOT.glob("text/卷*/第*章.md"))

def parse_num(p):
    m = re.search(r"第(\d+)章", p.name)
    return int(m.group(1)) if m else None

def parse_vol(p):
    m = re.search(r"卷(\d+)", str(p))
    # 归一化: 卷04≡卷4(防影子卷,audits/13攻击2)
    return f"卷{int(m.group(1))}" if m else None

def vol_dir_canonical(p):
    """目录名必须是规范的'卷N'(非零填充)——'卷04'这类命名视为违规"""
    m = re.search(r"[\/\\]卷(\d+)[\/\\]", str(p) + "/")
    return m is None or m.group(1) == str(int(m.group(1)))

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
    """章号→期望卷: 落入区间用该卷; 大于所有max→末卷(max+1顺写); 落入间隙/小于所有min→None(异常); 空库→None(新书任意)"""
    if not volumes:
        return None
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
        lines = [l for l in TIMELINE.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
        for l in reversed(lines):
            m = re.match(r"- 第(\d+)章\|([^|]+)\|", l.strip())
            if m:
                story_time = f"第{int(m.group(1)):03d}章·{m.group(2).strip()}"
                break
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

    # G4去自洽(audits/13): 卷区间只从非staged存量实扫;但modified模式用全量(改写已入库章不缩区间)
    if mode == "new":
        volumes = scan_volumes([p for p in files if str(p.resolve()) not in staged_paths])
    else:
        volumes = scan_volumes(files)
    fail_total = 0
    # 跳章阈值: 新章号最大允许 = 存量max + 本批新章数(批提交080+081合法;单独085=跳章)
    existing_nums = set(existing)
    max_existing = max(existing_nums) if existing_nums else 0
    n_new_staged = len([p for p in staged
                        if parse_num(p) is not None and parse_num(p) not in existing_nums])
    jump_cap = max_existing + n_new_staged
    # G8语料: 存量章(排除staged)按段预切
    corpus_paras = {}
    for p2 in files:
        if str(p2.resolve()) in staged_paths:
            continue
        try:
            raw2 = p2.read_text(encoding="utf-8-sig")
            # G8用原始空行分段(大审计-18 D3-G8: body过滤空行后单\n拼接,再按空行切=死代码)
            corpus_paras[str(p2)] = [x.strip() for x in re.split(r"\n\s*\n", raw2) if x.strip() and not re.match(r"^第[一二三四五六七八九十百0-9]+章", x.strip())]
        except OSError:
            pass
    staged_paras = []
    for p in staged:
        problems, warns = [], []
        n = parse_num(p)
        if not p.exists():
            # 静默读空会把调用方的argv拼接错误伪装成"新章0字"——直接点名(铁律一:错误必须可归因)
            print(f"=== gate_chapter [{p.name}] FAIL ===")
            print(f"  [FAIL] 门输入错误: {p} 不存在(检查调用方是否把模式词当路径传入)")
            fail_total += 1
            continue
        raw = p.read_text(encoding="utf-8-sig")
        body = "\n".join(l for l in raw.splitlines() if l.strip() and not l.startswith("#"))
        title = raw.splitlines()[0].strip() if raw.splitlines() else ""
        staged_paras += [x.strip() for x in re.split(r"\n\s*\n", raw) if x.strip() and not re.match(r"^第[一二三四五六七八九十百0-9]+章", x.strip())]

        # G9 开场型门(新章;大审计-08:存量25章100%时间状语开场=同构固化)
        if mode == "new":
            # 跳过标题行: 本项目标题无#前缀, body首元素即"第N章 XXX"(大审计-18 P0-1)
            _lines = [l for l in body.splitlines() if l.strip()]
            first_para = ""
            for _l in _lines:
                if not re.match(r"^第[一二三四五六七八九十百0-9]+章", _l.strip()):
                    first_para = _l.strip()
                    break
            if re.match(r"^(第?[一二三四五六七八九十百0-9]+[章日天早晚月年]|开春|进了腊月|正月|入了|那年|当年|次日|第二天|当天|礼拜|周[一二三四五六日末]|深夜|凌晨|傍晚|天黑|十月|十一月|十二月|三月)", first_para):
                problems.append("G9开场型: 首段时间状语开场——禁令生效(PREFIX/场景卡开场型字段),用对话/动作/异常直入")

        # G1 字数硬底线(只卡新增章;存量章回炉是计划内工作)
        cn = cjk_len(body)
        if cn < 1500:
            if mode == "new":
                problems.append(f"G1字数硬底线: 新章仅{cn}字(<1800硬线)——骨架未回填禁入库,走血肉遍(beat-expand)扩写")
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
                t2 = p2.read_text(encoding="utf-8-sig").splitlines()[0].strip() if p2.exists() else ""
                if t2 and t2 == title:
                    problems.append(f"G3标题重复: 「{title}」与{p2.relative_to(ROOT)}相同")

        # G2b 跳章门(new): 章号超前于max+本批新章数=挖洞
        if mode == "new" and n is not None and n not in existing_nums and n > jump_cap:
            problems.append(f"G2b跳章: 第{n}章超前(next应≤{jump_cap})——禁挖洞,按序写或走arc-restructure")

        # G4 卷归属门(区间=存量实扫;吞并/影子卷/间隙全拦,audits/13)
        # 空库(新书)放行: 无存量区间可依,任意卷号合法,由卷纲层管
        if n is not None and not volumes:
            warns.append(f"G4空库放行: 第{n}章为新书早期章(卷={parse_vol(p)}),存量区间为空")
        elif n is not None:
            exp = expected_volume(n, volumes)
            act = parse_vol(p)
            if act is None:
                problems.append(f"G4卷归属: 路径无卷号({p})")
            elif not vol_dir_canonical(p):
                problems.append(f"G4卷归属: 卷目录名非规范(卷04应写作卷4)——影子卷拒绝")
            elif exp is None:
                # 唯一放行: 合法新卷 n==存量max+1 且 卷号=末卷+1;或带"插叙:"标记的回填
                ok = False
                if volumes:
                    last = max(volumes, key=lambda v: volumes[v][1])
                    ok = (n == volumes[last][1] + 1
                          and int(act.replace("卷", "")) == int(last.replace("卷", "")) + 1)
                head5 = "\n".join(raw.splitlines()[:5])
                if not ok and ("插叙:" in head5 or "插叙：" in head5):
                    warns.append(f"G4插叙回填: 第{n}章落入存量间隙但已标'插叙:'——请确认arc-restructure已排期重编号")
                elif not ok:
                    problems.append(f"G4卷归属: 第{n}章落入卷间隙或非法新卷(存量区间{volumes})——需arc-restructure")
            elif act != exp:
                problems.append(f"G4卷归属: 第{n}章应属{exp},实际在{act}——错放卷(事故B)")

        # G5 跨章查重门
        if body:
            sh_new = shingles(body)
            worst, worst_p = 0.0, None
            for num2, p2 in existing.items():
                try:
                    old = "\n".join(l for l in p2.read_text(encoding="utf-8-sig").splitlines() if l.strip() and not l.startswith("#"))
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

        # G6 时序门(硬化,audits/13攻击7): 解析时间线账,新章号≤账面末章且无插叙标记=FAIL
        if TIMELINE.exists() and n is not None:
            tl_max = 0
            for l in TIMELINE.read_text(encoding="utf-8-sig").splitlines():
                m = re.match(r"-\s*第(\d+)章\|", l.strip())
                if m:
                    mm = int(m.group(1))
                    # 只统计早于本章的记录——账本若先盖了本章/后续章的章,不应让新章误判(audits/22后实测缺陷)
                    if mm < n:
                        tl_max = max(tl_max, mm)
            head = "\n".join(raw.splitlines()[:5])
            if tl_max and mode == "new" and n < tl_max:
                if "插叙:" not in head and "插叙：" not in head:
                    problems.append(f"G6时序门: 新章{n}不晚于时间线末记录(第{tl_max}章)且文件头无'插叙:'标记——时序回退禁止,走arc-restructure")
                else:
                    warns.append(f"G6插叙豁免: 第{n}章为回溯章(账面末章{tl_max}),请确认arc-restructure已排期重编号")
            elif mode == "modified":
                warns.append("G6时序提醒: 修改存量章后核对ledgers/时间线.md")

        print(f"\n=== gate_chapter [{p.name}] {'FAIL' if problems else 'PASS'} ===")
        for x in problems:
            print(f"  [FAIL] {x}")
        for w in warns:
            print(f"  [WARN] {w}")
        fail_total += len(problems)

    # G8 跨章贴入门(整批一次)
    if mode == "new" and staged_paras and corpus_paras:
        hits = cross_chapter_dup(staged_paras, corpus_paras)
        if hits:
            print("=== gate_chapter [G8跨章贴入] FAIL ===")
            for prev, f, r in hits[:4]:
                print(f"  [FAIL] 段落「{prev}…」与存量{f.rsplit('/',1)[-1]}相似{r}——贴入残留,必须重写该段(006→009事故形状)")
            fail_total += len(hits)

    if fail_total:
        print(f"\n汇总: {fail_total}项FAIL")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
