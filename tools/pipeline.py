#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline.py v2 —— 可执行流水线状态机(架构v2核心,见docs/ARCHITECTURE.md与audits/14)
状态一律从文件系统+git派生,不新增状态文件;唯一缓存:.progress.json与scores.json(均禁手写)。
与pre-commit hook共享同一套门实现(check.py+gate_chapter.py)——单一实现,两个入口。

命令(退出码: 0=通过 1=验收未过 2=用法/前置缺失):
  status                       进度+每章状态+节奏欠账+下一动作
  next [N]                     第N章工作契约(缺省=下一章)
  bundle N                     上下文装配器:按三档预算装配生成注入包(stdout)
  check <file...>              一次跑check.py+gate_chapter.py
  done N [--revise] [--strict] 章验收:过则重算progress+scores并提示盖章;拒则列缺项
  scores [--recompute]         质量仪表scores.json(全量重算)
仅用标准库。
"""
import sys, re, json, subprocess, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gate_chapter as G  # noqa: E402  复用chapter_files/parse_num/scan_volumes/expected_volume

CARD_DIR = ROOT / "text" / "卡"
AUDIT_DIR = ROOT / "story" / "audit"
LEDGERS = ROOT / "ledgers"
BIBLE = ROOT / "story" / "60-圣经"
PROGRESS = ROOT / ".progress.json"
SCORES = ROOT / "scores.json"
LEDGER_NAMES = ["伏笔", "梗", "钩分布", "类型轮换", "人物状态", "线弦", "时间线"]

PREFIX = (
    "【生成纪律】生成单位=一个场景。字数以场景卡字数带为准(卡标峰章上限5200),无卡带则2400-2800。"
    "对话40-60%(角色必须开口说话),心理裸写≥2处/千字,禁工程词,禁情绪命名(恐惧/心疼→写动作与位移),"
    "明喻≤3,破折号≤3,禁「如你所知」式设定转述,首句≤15字扔事件,警句≤1/场景,禁排比+抽象名词社论腔,叙述者永不替读者总结主题。"
    "【焦点优先】若注入包含「本章焦点」,该2-3项是本章最高优先级,与其余规则冲突时焦点获胜。"
    "【生活气】金额物价≥2处且至少1处参与情绪运算(算账/心疼/划算);感官≥3通道(视觉不计);"
    "闲笔≥1处(≥60字,与主线无关,由人物腔说出,须含对白);等待给可感刻度(秒/圈/一支烟),禁「很久很久」;每章1轮家常对话。"
    "素材库条目须变形后入文:数字与事实可留用,表述必须重造,原句照抄=泄漏门FAIL。"
    "【爽点】按场景卡爽点行执行;小兑现只用震惊前两层(当事者失态细节+内行反应),大兑现才用四层;"
    "慢拍三微拍每2-3章≤1次(查钩分布账尾结构轮换);章末必钩且形态与上两章不同。"
    "只写本卡,不写卡外剧情;Forbid绝对不写;价值换极必须发生;对白遮名可辨;"
    "摘要句压缩仅限过渡,禁章末场景,单处≤30字。"
)

def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT,
                       capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def chapter_map():
    out = {}
    for p in G.chapter_files():
        n = G.parse_num(p)
        if n is not None:
            out[n] = p
    return out

def card_for(n):
    hits = sorted(CARD_DIR.glob(f"*第{n:03d}章*.md"))
    return hits[0] if hits else None

def card_volume(card):
    m = re.search(r"卷(\d+)", card.name)
    return f"卷{int(m.group(1))}" if m else None

def is_committed(path):
    _, out, _ = git("status", "--porcelain", "--", str(path.relative_to(ROOT)))
    return out == ""

def cold_read_for(n):
    for pat in (f"冷读-第{n:03d}章*.md", f"冷读-第{n}章*.md"):
        hits = sorted(AUDIT_DIR.glob(pat))
        if hits:
            return hits[0]
    return None

def ledger_stamped(n):
    toks = (f"第{n}章", f"第{n:03d}章")
    stamped = []
    for f in sorted(LEDGERS.glob("*.md")):
        if f.name == "waivers.md":
            continue
        if any(t in f.read_text(encoding="utf-8") for t in toks):
            stamped.append(f.stem)
    return stamped

def read_text(p, limit=None):
    if not p or not pathlib.Path(p).exists():
        return ""
    t = pathlib.Path(p).read_text(encoding="utf-8")
    if limit is None:
        return t
    return t[limit:] if limit < 0 else t[:limit]  # 负数=取末尾N字

def run_check_metrics(fp):
    flag = ["--modern"] if (ROOT / "text" / ".modern").exists() else []
    r = subprocess.run(["python3", "tools/check.py", *flag, "--metrics", str(fp)],
                       cwd=ROOT, capture_output=True, text=True)
    m = None
    for line in r.stdout.splitlines():
        if line.startswith("METRICS "):
            try:
                m = json.loads(line[8:])
            except Exception:
                m = None
    return r.returncode, r.stdout, m

def run_gate(mode, fps):
    r = subprocess.run(["python3", "tools/gate_chapter.py", mode, *map(str, fps)],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout

def recalc_progress():
    subprocess.run(["python3", "tools/gate_chapter.py", "--recompute"], cwd=ROOT,
                   capture_output=True, text=True)

def progress_data():
    if PROGRESS.exists():
        try:
            return json.loads(PROGRESS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def card_fields(card):
    """从卡提取: 钩级别/字数预算range/场景型。预算缺失时回退beats总和×1.4(audits/19病灶②)。"""
    t = card.read_text(encoding="utf-8")
    hm = re.search(r"钩\*?\*?[:：]\s*([轻重中]{1,2}(?:重|轻)?)", t)
    bm = re.search(r"(\d{4})\s*[-—~至]\s*(\d{4})", t)
    if not bm:
        beats = [int(x) for x in re.findall(r"\((\d{3,4})\)", t)]
        if beats:
            lo = int(sum(beats) * 1.3)
            bm_val = [lo, int(sum(beats) * 1.6)]
        else:
            bm_val = None
    else:
        bm_val = [int(bm.group(1)), int(bm.group(2))]
    sm = re.search(r"场景型\*?\*?[:：]\s*(\S{1,12})", t)
    return (hm.group(1) if hm else None, bm_val, sm.group(1) if sm else None)

# ---------------- status ----------------
def leak_check(fp):
    """注入物泄漏门(audits/21-Fix2): 正文与范例段/场景卡成句重叠>=10字=FAIL。"""
    body = re.sub(r"\s+", "", read_text(fp))
    sources = []
    sp = ROOT / "story" / "50-风格包.md"
    if sp.exists():
        m = re.search(r"^## 范例段.*?(?=^## |\Z)", read_text(sp), re.M | re.S)
        if m:
            sources.append(("风格包范例段", m.group(0)))
    n = G.parse_num(pathlib.Path(fp))
    if n:
        card = card_for(n)
        if card:
            sources.append(("场景卡", read_text(card)))
    hits = []
    for name, src in sources:
        for para in re.split(r"\n+", src):
            pc = re.sub(r"[\s#*>`\-]", "", para)
            if len(pc) < 12:
                continue
            for i in range(0, len(pc) - 10, 6):
                frag = pc[i:i+12]
                if frag and frag in body:
                    hits.append(f"{name}:{frag}")
                    break
            if len(hits) >= 3:
                break
    return hits

def cmd_status():
    cm = chapter_map()
    vols = G.scan_volumes(list(cm.values()))
    maxn = max(cm) if cm else 0
    nxt = maxn + 1
    pg = progress_data()
    print(f"进度: max={maxn} next={nxt} 卷={vols}")
    if pg.get("story_time"):
        print(f"故事时间: {pg['story_time']}")

    gaps = [n for n in range(1, maxn + 1) if n not in cm]
    no_card = [n for n in cm if card_for(n) is None]
    dirty = [n for n, p in cm.items() if not is_committed(p)]
    print(f"异常: 缺章(gap)={gaps or '无'} | 无卡={no_card or '无'} | 未提交={dirty or '无'}")

    print("最近5章:")
    for n in sorted(cm)[-5:]:
        p = cm[n]
        cr = "冷读✓" if cold_read_for(n) else "冷读—"
        print(f"  第{n:03d}章 [{'committed' if is_committed(p) else 'drafting'}] {cr}")

    due = [n for n in sorted(cm)[-5:] if cold_read_for(n) is None]
    if due:
        print(f"冷读欠账(5章窗口): {due} → reader-proxy")
    if nxt % 5 == 0:
        print(f"提示: 第{nxt}章为5的倍数——全装轨,冷读为硬门(done --strict)")
    drift_max = 0
    if AUDIT_DIR.exists():
        for f in AUDIT_DIR.glob("漂移审计-*"):
            m = re.search(r"第(\d+)", f.name)
            if m:
                drift_max = max(drift_max, int(m.group(1)))
    if maxn // 10 > drift_max // 10:
        print(f"[REMIND] 漂移审计到期: 已到第{maxn}章,账面仅覆盖至第{drift_max}章周期")
    if cm:
        stamped = ledger_stamped(maxn)
        missing = [x for x in LEDGER_NAMES if x not in stamped]
        if missing:
            print(f"第{maxn:03d}章盖章缺: {missing} → ledger-update")
    mat_left = len([l for l in read_text(ROOT / "story" / "素材库.md").splitlines()
                    if l.strip().startswith(("- ", "  - ")) and "已用:" not in l]) if (ROOT / "story" / "素材库.md").exists() else 0
    est = mat_left // 3 if mat_left else 0
    if mat_left < 30:
        print(f"[红灯] 素材库仅剩{mat_left}条(约{est}章耗尽)——立即扩容(world-economy/行业经营库)")
    else:
        print(f"素材库余量: {mat_left}条(约{est}章)")
    print(f"下一动作: pipeline.py next {nxt}")
    return 0

# ---------------- next ----------------
def cmd_next(args):
    cm = chapter_map()
    maxn = max(cm) if cm else 0
    n = int(args[0]) if args else maxn + 1
    vols = G.scan_volumes(list(cm.values()))
    exp = G.expected_volume(n, vols)
    if n in cm:
        print(f"第{n:03d}章已存在({cm[n].relative_to(ROOT)})——改写请直接修改文件后 `pipeline.py done {n} --revise`")
        return 0
    if n < maxn + 1:
        print(f"[gap] 第{n}章小于next={maxn+1}——补章禁止直接写,走arc-restructure重排(防时序倒置)")
        return 2
    card = card_for(n)
    print(f"=== 第{n:03d}章 工作契约 ===")
    print(f"目标路径: text/{exp or '?'}/第{n:03d}章.md")
    print(f"1. scene-card 填卡 → text/卡/ 命名: {exp}-第{n:03d}章-场1.md")
    print("   卡必填: 场景型/戏剧问题/价值换极/beats≤3(含字数预算)/Pre/Post/Forbid/钩级别/获得/笑点/声纹/知情状态")
    print("2. pipeline.py bundle {0} → 按注入包起草(scene-draft)".format(n))
    print("3. pipeline.py check text/{0}/第{1:03d}章.md".format(exp or "?", n))
    print("4. 冷读: " + ("第{}章为5的倍数/卷首——reader-proxy必做(硬门)".format(n) if (n % 5 == 0 or n == 1) else "建议reader-proxy(软门,5章窗口)"))
    print("5. git commit → pipeline.py done {0}".format(n))
    if card:
        print(f"[已有卡] {card.relative_to(ROOT)}——可直接进bundle")
    else:
        print("[缺卡] 先填卡;bundle/done会被前置缺失拦截")
        return 2
    return 0

# ---------------- bundle ----------------
def crop(text, cap, tag):
    t = (text or "").strip()
    if len(t) > cap:
        t = t[:cap] + f"\n…[已裁剪:{tag}上限{cap}字]"
    return t

def cmd_bundle(args):
    if not args:
        print("用法: pipeline.py bundle N"); return 2
    try:
        n = int(args[0])
    except (ValueError, IndexError):
        print("用法: pipeline.py done <章号>"); return 2
    cm = chapter_map()
    vols = G.scan_volumes(list(cm.values()))
    exp = G.expected_volume(n, vols) or "卷1"
    card = card_for(n)
    missing = []
    if card is None:
        missing.append(f"场景卡 text/卡/*第{n:03d}章*(先走scene-card)")
    sp = ROOT / "story" / "50-风格包.md"
    if not sp.exists():
        missing.append("story/50-风格包.md")
    voice = ROOT / "story" / "20-人物" / "声纹表.md"
    if not voice.exists():
        missing.append("story/20-人物/声纹表.md")
    if missing:
        print("[前置缺失] " + "; ".join(missing))
        return 2

    items = []  # (名, 实占, 上限, 正文)
    def add(name, cap, text):
        text = (text or "").strip()
        items.append((name, len(text), cap, crop(text, cap, name)))

    add("1固定指令前缀", 500, PREFIX)
    add("2场景卡(全文)", 700, read_text(card))
    card_text = read_text(card)
    # 3 声纹行(仅出场者): 声纹表为markdown表格,解析行首单元格人名,命中卡面/人物状态账才带
    voice_lines = [l for l in read_text(voice).splitlines() if l.strip()]
    cast = read_text(LEDGERS / "人物状态.md")
    def row_name(l):
        if not l.strip().startswith("|"):
            return None
        cell = l.strip().strip("|").split("|")[0].strip()
        cell = cell.strip("*# 【】[]")
        if not cell or cell in ("人", "—", "-", ":--") or set(cell) <= {"-", ":", " "}:
            return None
        return cell
    present = [l for l in voice_lines
               if row_name(l) and (row_name(l) in card_text or row_name(l) in cast)]
    add("3声纹行(出场者)", 400, "\n".join(present))
    # 4 风格包: 风格卡+范例段(按节标记定位——修复断供P0: 旧实现取头部1000字,
    #    风格卡在offset≈3679/范例段在≈3943,79章从未注入正样本,audits/19病灶④)
    sp_text = read_text(sp)
    def section(text, header):
        m = re.search(rf"^## {re.escape(header)}.*?(?=^## |\Z)", text, re.M | re.S)
        return m.group(0) if m else ""
    style_card = section(sp_text, "风格卡")
    sample = section(sp_text, "范例段")
    add("4风格卡+范例段(正样本)", 1800, (style_card + "\n" + sample).strip() or read_text(sp, 800))
    # 5 上一章末尾(原文,禁摘要)
    prev = cm.get(n - 1)
    add("5上一章末尾(原文)", 900, read_text(prev, -900) if prev else "(本章为开篇,无上一章)")
    # 6 当前时刻卡(全文,唯一整读账本)
    add("6当前时刻卡", 500, read_text(LEDGERS / "当前时刻卡.md"))
    # 7 圣经: 全书卡+当前卷摘要
    bible = read_text(BIBLE / "全书卡.md")
    if exp:
        bible += "\n" + read_text(BIBLE / f"卷摘要-{exp}.md")
    add("7圣经(全书卡+本卷摘要)", 700, bible)
    # 8 伏笔账在跑项
    fb = [l for l in read_text(LEDGERS / "伏笔.md").splitlines()
          if re.search(r"状态.*(养|悬空|待回收)", l)]
    add("8伏笔在跑项", 600, "\n".join(fb))
    # 9 钩分布/类型轮换近窗
    hooks = read_text(LEDGERS / "钩分布.md", -250)
    rotate = read_text(LEDGERS / "类型轮换.md", -250)
    add("9钩/类型近窗", 550, hooks + "\n" + rotate)

    # 10 生活素材(audits/21-Fix1): cast从声纹表派生(禁硬编码),按卡面提及打分,
    #    按地点分区加权,J区语言恒带2条;素材须变形入文(数字保留,表述重造)
    mat_path = ROOT / "story" / "素材库.md"
    mat_raw = read_text(mat_path)
    # 当前section标记
    sec = ""
    mat_items = []  # (section, line)
    for l in mat_raw.splitlines():
        if l.startswith("## "):
            sec = l[3:].strip()[:8]
        elif l.strip().startswith(("- ", "  - ")) and "已用:" not in l and not l.strip().startswith("- 202"):
            mat_items.append((sec, l.strip()))
    # cast从声纹表表格首列派生
    cast = []
    for l in read_text(voice).splitlines():
        if l.strip().startswith("|") and not re.search(r"^\|[-\s|:]+\|?$", l.strip()):
            cell = l.strip().strip("|").split("|")[0].strip("*# 【】[]")
            if cell and cell not in ("人", "—") and len(cell) <= 4:
                cast.append(cell)
    # 地点→素材分区加权表
    place_sec = {"夜市": ["吃食", "B."], "早市": ["吃食", "街巷", "B.", "C."], "家": ["吃食", "器物", "B.", "E."],
                 "家属院": ["街巷", "C."], "电子城": ["电子城", "手艺", "行话", "C.", "D.", "F."],
                 "打印社": ["场所", "I."], "网吧": ["等待", "G.", "B."], "考点": ["吃食", "B."], "柜台": ["电子城", "C.", "D."]}
    card_places = re.findall("夜市|早市|家属院|电子城|打印社|网吧|考点|柜台|家", card_text)
    want_secs = set()
    for pl in set(card_places):
        for key in place_sec.get(pl, []):
            want_secs.add(key)
    def mat_score(item):
        sec_, l = item
        s = 0
        if any(re.search(rf"^{w}|{w}", sec_) for w in want_secs):
            s -= 3
        for who in cast:
            if who in l:
                s -= 4
        if sec_ and ("语言" in sec_ or "J." in sec_):
            s -= 2  # 年代语言恒优先
        return s
    scored = sorted(mat_items, key=mat_score)
    # 保底:每区最多5条,防止单区霸屏;总12条
    picked, sec_count = [], {}
    for sec_, l in scored:
        c = sec_count.get(sec_, 0)
        if c >= 5:
            continue
        picked.append(f"[{sec_}] {l}" if not l.startswith("[") else l)
        sec_count[sec_] = c + 1
        if len(picked) >= 12:
            break
    add("10生活素材(变形后入文,禁原句照抄)", 1200, "\n".join(picked) + "\n[用法] 数字与事实可留用,表述必须重造;成句照抄=泄漏门FAIL")

    # 11 爽点管道(docs/爽点引擎): 在充能各条+型+距兑现章数——期待链的生成现场
    pipe_path = LEDGERS / "爽点管道.md"
    if pipe_path.exists():
        pipe_lines = [l for l in read_text(pipe_path).splitlines()
                      if l.strip().startswith("| P") and "充能" in l]
        add("11爽点管道(在充能)", 400, "\n".join(pipe_lines) or "(管道空——期待链红灯,先补P)")

    total = sum(x[1] for x in items)
    print("=== 注入预算报告(第{}章) ===".format(n))
    fm = re.search(r"焦点\*?\*?[:：]\s*([^\n]+)", card_text)
    gm = re.search(r"章级\*?\*?[:：]\s*(\S+)", card_text)
    if fm:
        print("\n【本章焦点】{}{}".format(fm.group(1).strip()[:80], "（峰章:5200上限+alt-takes必走+done--strict）" if (gm and "峰" in gm.group(1)) else ""))
    for name, used, cap, _ in items:
        flag = " !" if used > cap else ""
        print(f"  {name}: {used}/{cap}字{flag}")
    print(f"  合计: {total}字 (硬上限6500" + (",超限!" if total > 6500 else ",OK") + ")")
    print()
    print("===== BUNDLE-START (按序注入,顺序即优先级) =====")
    for name, used, cap, body in items:
        print(f"\n◀ {name} ▶\n{body}")
    print("\n===== BUNDLE-END =====")
    return 0

# ---------------- check ----------------
def cmd_check(args):
    if not args:
        print("用法: pipeline.py check <file...>"); return 2
    worst = 0
    for fp in args:
        rc, out, _ = run_check_metrics(fp)
        print(out)
        worst = max(worst, rc)
    grc, gout = run_gate("modified", args)
    print(gout)
    worst = max(worst, grc)
    for fp in args:
        leaks = leak_check(pathlib.Path(fp))
        if leaks:
            print(f"[FAIL] 注入物泄漏({fp}): {'; '.join(leaks[:3])} — 素材须变形,表述重造")
            worst = 1
    return worst

# ---------------- done ----------------
def cmd_done(args):
    revise = "--revise" in args
    strict = "--strict" in args
    nums = [a for a in args if not a.startswith("--")]
    if not nums:
        print("用法: pipeline.py done N [--revise] [--strict]"); return 2
    n = int(nums[0])
    cm = chapter_map()
    if n not in cm:
        print(f"[exit 2] 第{n:03d}章文件不存在")
        return 2
    p = cm[n]
    vols = G.scan_volumes(list(cm.values()))
    exp = G.expected_volume(n, vols)
    problems, warns = [], []

    committed = is_committed(p)
    if committed and not revise:
        # v3.1: 已提交章允许后验刷新(audits/22-12: done常在commit后补跑,committed字段结构性为false的修复)
        print(f"[post] 第{n:03d}章已committed——跑后验刷新(scores.committed将置真);改写验收用 --revise")
        revise = True  # 后验模式=按改写口径验收,但committed写真值
        post = True
    else:
        post = False

    # 1 卡
    card = card_for(n)
    if card is None:
        (warns if revise else problems).append("缺场景卡(text/卡/*第{:03d}章*)——先走scene-card".format(n))
        hv, budget, scene_type = None, None, None
    else:
        hv, budget, scene_type = card_fields(card)
        cv = card_volume(card)
        if cv != exp:
            (warns if revise else problems).append(f"卡卷错配: 卡标{cv} 章应属{exp}——mv卡文件并对齐卡头")

    # 2 跳章: 与【已提交】章比较(工作区含批量草稿不算);落后=存在已提交的更大章号且自己未提交
    committed_nums = [k for k, v in cm.items() if is_committed(v)]
    cur_max_c = max(committed_nums) if committed_nums else 0
    if n < cur_max_c and not revise:
        problems.append(f"章号落后: 已提交至第{cur_max_c}章,验收的是{n}——旧章改写用--revise,插章走arc-restructure")

    # 3 check.py
    rc, out, met = run_check_metrics(p)
    print(out.rstrip())
    if rc != 0:
        problems.append("check.py存在FAIL(见上)")
    elif met is None:
        warns.append("check.py未返回METRICS(版本过旧?)")

    # 4 韧性门(gate_chapter,与hook同一实现)
    gmode = "modified" if (committed or revise) else "new"
    grc, gout = run_gate(gmode, [p])
    print(gout.rstrip())
    if grc != 0:
        problems.append(f"gate_chapter({gmode})未过(见上)")

    # 5 冷读节奏(双轨: --strict/5的倍数/卷首=硬,其余=软)
    cr = cold_read_for(n)
    vol_first = exp in vols and n == vols[exp][0]
    hard_cold = strict or (n % 5 == 0) or vol_first
    if cr is None:
        msg = "无冷读记录(story/audit/冷读-第{:03d}章.md)——运行reader-proxy后落盘".format(n)
        (problems if hard_cold else warns).append(msg + ("[硬门]" if hard_cold else "[软门]"))

    # 6 卡字数预算 vs 实测
    cjk = (met or {}).get("cjk", 0)
    if budget and cjk:
        mid = sum(budget) / 2
        delta = (cjk - mid) / mid * 100
        if delta < -40:
            warns.append(f"字数低于卡预算{delta:.0f}%(实测{cjk} vs 卡{budget})——beat-expand回炉项")

    # 6.5 当前时刻卡随章断言(软门,audits/22-11)
    moment = read_text(LEDGERS / "当前时刻卡.md")
    if f"第{n:03d}章" not in moment and f"第{n}章" not in moment:
        warns.append(f"当前时刻卡未含第{n:03d}章——跨会话恢复注入物过期,更新ledgers/当前时刻卡.md")

    # 7 七账盖章
    stamped = ledger_stamped(n)
    missing = [x for x in LEDGER_NAMES if x not in stamped]
    if missing:
        warns.append(f"七账未盖章: {missing}——ledger-update补记(禁无章号记账)")

    print()
    if problems:
        print(f"❌ done验收未过(第{n:03d}章):")
        for x in problems:
            print(f"  [FAIL] {x}")
        for x in warns:
            print(f"  [WARN] {x}")
        return 1
    recalc_progress()
    scores_update(n, p, met, committed)
    print(f"✅ 第{n:03d}章验收通过: progress+scores已重算")
    for x in warns:
        print(f"  [WARN] {x}")
    print(f"下一动作: pipeline.py next (应为第{n+1:03d}章)")
    return 0

# ---------------- scores ----------------
def scores_update(n, p, met, committed):
    data = {"_comment": "派生缓存:python3 tools/pipeline.py scores重算;手稿是唯一权威;禁止手写",
            "generated_at": "", "head_commit": "", "chapters": {}}
    if SCORES.exists():
        try:
            data = json.loads(SCORES.read_text(encoding="utf-8"))
        except Exception:
            pass
    _, head, _ = git("rev-parse", "--short", "HEAD")
    data["head_commit"] = head
    import datetime
    data["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    ch = data["chapters"].setdefault(str(n), {})
    ch.update({"path": str(p.relative_to(ROOT)), "committed": is_committed(p),
               "cjk": (met or {}).get("cjk"), "dia_char_pct": (met or {}).get("dia_char_pct"),
               "psych_per_k": (met or {}).get("psych_per_k"),
               "hook_signals": (met or {}).get("hook_signals"), "dup18": (met or {}).get("dup18"),
               "check_status": (met or {}).get("status"), "check_fails": (met or {}).get("fails")})
    card = card_for(n)
    if card:
        hv, budget, scene_type = card_fields(card)
        ch.update({"hook_level_from_card": hv, "card_budget": budget})
        if budget and ch.get("cjk"):
            mid = sum(budget) / 2
            ch["budget_delta_pct"] = round((ch["cjk"] - mid) / mid * 100, 1)
    cr = cold_read_for(n)
    ch["cold_read"] = cr.name if cr else None
    flags = []
    if (ch.get("budget_delta_pct") or 0) < -40:
        flags.append("budget_delta_below_-40pct")
    if (ch.get("psych_per_k") or 0) < 0.5:
        flags.append("psych_starved")
    if (ch.get("dia_char_pct") or 0) and ch["dia_char_pct"] < 25:
        flags.append("dialogue_starved")
    ch["drift_flags"] = flags
    SCORES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def cmd_scores(args):
    import check as CHK  # noqa: E402
    if (ROOT / "text" / ".modern").exists():
        CHK.MODERN_SETTING[0] = True
    cm = chapter_map()
    data = {"_comment": "派生缓存:python3 tools/pipeline.py scores重算;手稿是唯一权威;禁止手写",
            "generated_at": "", "head_commit": "", "chapters": {}}
    _, head, _ = git("rev-parse", "--short", "HEAD")
    import datetime
    data["head_commit"] = head
    data["generated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    print(f"{'章':>5} {'卷':<4} {'字数':>5} {'对话%':>6} {'心理/千':>7} {'钩信号':>5} {'状态':<5} {'预算偏差':>8} 冷读")
    worst = []
    for n in sorted(cm):
        p = cm[n]
        _, _, _, _, _, met = CHK.check(p)
        card = card_for(n)
        hv, budget, _ = card_fields(card) if card else (None, None, None)
        delta = None
        if budget and met["cjk"]:
            mid = sum(budget) / 2
            delta = round((met["cjk"] - mid) / mid * 100, 1)
        cr = "✓" if cold_read_for(n) else "—"
        vol = G.parse_vol(p) or "?"
        print(f"{n:>5} {vol:<4} {met['cjk']:>5} {met['dia_char_pct']:>6} {met['psych_per_k']:>7} "
              f"{met['hook_signals']:>5} {met['status']:<5} {('%+.0f%%' % delta) if delta is not None else '—':>8} {cr}")
        if met["status"] == "FAIL" or (delta is not None and delta < -40):
            worst.append(n)
        ch = data["chapters"].setdefault(str(n), {})
        ch.update({"path": str(p.relative_to(ROOT)), "volume": vol, "cjk": met["cjk"],
                   "dia_char_pct": met["dia_char_pct"], "psych_per_k": met["psych_per_k"],
                   "hook_signals": met["hook_signals"], "dup18": met["dup18"],
                   "check_status": met["status"], "check_fails": met["fails"],
                   "hook_level_from_card": hv, "card_budget": budget,
                   "budget_delta_pct": delta, "cold_read": (cold_read_for(n).name if cold_read_for(n) else None)})
        if met["status"] == "FAIL" or (delta is not None and delta < -40):
            ch["drift_flags"] = ["below_target"]
    SCORES.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nscores.json已重算({len(cm)}章,head={head})。红灯章: {worst or '无'}")
    return 0

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    if cmd == "status":
        return cmd_status()
    if cmd == "next":
        return cmd_next(rest)
    if cmd == "bundle":
        return cmd_bundle(rest)
    if cmd == "check":
        return cmd_check(rest)
    if cmd == "done":
        return cmd_done(rest)
    if cmd == "scores":
        return cmd_scores(rest)
    print(f"未知命令: {cmd}\n" + __doc__)
    return 2

if __name__ == "__main__":
    sys.exit(main())
