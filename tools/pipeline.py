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
from skill_protocol import scaffold_residue  # noqa: E402  骨架残留检测(20260917系统级统一)

# 多书隔离(docs/多书隔离协议.md): --book <书根> 切换; 主书=ROOT(历史占用)
BOOK = ROOT
CARD_DIR = ROOT / "text" / "卡"
AUDIT_DIR = ROOT / "story" / "audit"   # 书根模式由set_book重定向(法医秦见微/audit)
LEDGERS = ROOT / "ledgers"


def set_book(name):
    """切换书根: 卡目录按书布局自动探测(主书=text/卡,新书=<书>/卡)"""
    global BOOK, CARD_DIR, LEDGERS, PROGRESS
    BOOK = ROOT if not name else ROOT / name
    if not BOOK.is_dir():
        raise SystemExit(f"[exit 2] 书根不存在: {BOOK}")
    import glob as _g
    _tc = BOOK / "text" / "卡"
    CARD_DIR = _tc if _tc.is_dir() and _g.glob(str(_tc / "*.md")) else BOOK / "卡"   # 空目录视为不存在(审计-32 S4:残留空text/卡致寻卡指向空)
    LEDGERS = BOOK / "ledgers"
    PROGRESS = BOOK / ".progress.json"
    global AUDIT_DIR, BIBLE, STYLE, VOICE_TABLE, MATERIAL, SCORES
    AUDIT_DIR = BOOK / "audit" if BOOK != ROOT else ROOT / "story" / "audit"
    # 磨刀十五批(端到端推演#7): set_book此前只切四路径——圣经/风格包/声纹表/素材库/scores全是ROOT全局,
    # 非主书bundle会注入主书圣经,scores.json按章号互相覆盖(千章级多书污染)
    # 红队20260915: 书根缺资产时禁回退主书(跨书污染实锤: 1993书bundle曾注入主书电子城素材+风格包)——缺=空+done报警
    BIBLE = (BOOK / "圣经") if (BOOK / "圣经").is_dir() else ((ROOT / "story" / "60-圣经") if BOOK == ROOT else None)
    STYLE = (BOOK / "风格包.md") if (BOOK / "风格包.md").exists() else ((ROOT / "story" / "50-风格包.md") if BOOK == ROOT else None)
    # 红队技能库: 声口资产三分天下——统一单源: 书根声口卡.md优先,主书用story/60-圣经/声口卡.md(与voice_check同源)
    _root_card = ROOT / "story" / "60-圣经" / "声口卡.md"
    VOICE_TABLE = (BOOK / "声口卡.md") if (BOOK / "声口卡.md").exists() else (_root_card if BOOK == ROOT and _root_card.exists() else None)
    MATERIAL = (BOOK / "素材库.md") if (BOOK / "素材库.md").exists() else ((ROOT / "story" / "素材库.md") if BOOK == ROOT else None)
    SCORES = BOOK / "scores.json" if BOOK != ROOT else ROOT / "scores.json"
BIBLE = ROOT / "story" / "60-圣经"   # 目录(全书卡/卷摘要/章摘要);set_book按书根重定向
STYLE = ROOT / "story" / "50-风格包.md"
VOICE_TABLE = ROOT / "story" / "20-人物" / "声纹表.md"
MATERIAL = ROOT / "story" / "素材库.md"
PROGRESS = ROOT / ".progress.json"
SCORES = ROOT / "scores.json"   # set_book会按书根重定向
LEDGER_NAMES = ["伏笔", "梗", "钩分布", "类型轮换", "人物状态", "线弦", "时间线", "数字账"]   # 审计-32 N2: 数字入账为第八账

PREFIX = (
    "【生成纪律】单位=一个场景,目标字数按卡带(2400-5000)。对话40-55%,心理>=2/千字(少而准,与风格卡一致)。"
    "禁工程词;情绪禁告知;明喻<=3,破折号<=3,警句<=1/场景;首句禁时间状语开场(与前两章错型)。"
    "【生活气正向(上限定式)】每章1个本书专属物件(可复现道具);钱过手写面额与谁的钱;"
    "对话跑题一次;季节落在具体物上(风掀榜纸,非'天气热');称呼带关系史(用本书声口卡人名与关系称谓)。"
    "季节落在具体物上(风掀榜纸/汗浸票据),禁写'天气很热';称呼带关系史(以'叔/姨/哥'带关系相称,不写姓名全称——用本书声口卡里的人)。"
    "【生活气硬指标】金额>=2(1处参与情绪运算),感官>=3通道,闲笔>=1(>=60字),每章1轮家常对话。"
    "【情绪纪律】高情感拍减速到秒级三连微拍,单拍<=15字。"
    "【段落形态】段均<=30字;长段>=110字全章<=3;每场景3个<=15字短段。"
    "【章末】必钩,形态与上两章轮换;警句式收尾每卷<=1/3;禁旁白判词与排比宣言,收在动作/物件/对话。"
    "【防同构】对白禁复盘腔;讲解问答每章<=1次;章末禁议论;本章至少一处失控/失败/意外。"
    "【对白声口】漏不要聚:废话率>=30%,句碎片化,语气词>=8/千字,答非所问>=15%;配角警句同章<=1枚;该角色禁词绝不入其台词(查声口卡)。"
    "【数字表】卡上数字逐一入正文,口语可数值不可变。"
    "【峰后禁释】情感峰值段后,下一段=动作/物件/沉默/环境;禁叙述者解释。"
    "每场景必须有人想要不同的东西(阻碍);只写本卡,Forbid绝对不写;价值反转必须发生;对白遮名可辨。"
)

def git(*args):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT,
                       capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def chapter_map():
    out = {}
    files = G.chapter_files() if BOOK == ROOT else sorted(BOOK.glob("text/卷*/第*.md"))
    for p in files:
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


def zh_num_variants(x):
    """数字表对账用: 4500→[四千五,四千五百,4500]; 返回候选字符串列表"""
    try:
        v = int(x)
    except ValueError:
        return [x]
    digits = "零一二三四五六七八九"
    if v <= 0 or v > 9999:
        return [x]
    out = {x}
    qian, bai, shi, ge = v // 1000, v % 1000 // 100, v % 100 // 10, v % 10
    parts = []
    if qian: parts.append(digits[qian] + "千")
    if bai: parts.append(digits[bai] + "百")
    if shi: parts.append(("一" if shi == 1 and not (qian or bai) else digits[shi]) + "十")
    if ge: parts.append(digits[ge])
    full = "".join(parts)
    if full:
        out.add(full)
        # 口语截断: 九百五十→九百五/两千四百→两千四(末位为零时吞最后一个单位字)
        if ge == 0 and len(parts) >= 2:
            out.add(full[:-1])
        # 两/二口语: 二千八→两千八(1993审计: 正文口语用"两",变体缺失致数字表验证假阴)
        if "二千" in full:
            out.add(full.replace("二千", "两千"))
        if full.startswith("二百"):
            out.add("两百" + full[2:])
    s = "".join(parts) if parts else "零"
    out.add(s)
    # 口语省略: 4500→四千五; 250→二百五
    if qian and not bai and shi == 5 and ge == 0:
        out.add(digits[qian] + "千五")
    if qian and bai and shi == 5 and ge == 0:
        out.add(digits[qian] + "千" + digits[bai] + "百五")
    if shi == 2 and not (qian or bai):
        out.add(s.replace("二十", "廿十"))
    if v >= 20 and v < 100 and ge == 0 and shi:
        out.add(digits[shi] + "十")
    return sorted(out)

def ledger_stamped(n):
    """盖章=账内存在以"- "开头的条目行且含本章号(红队20260915: 任意位置token=垃圾文本可骗;
    占位行(待记/TODO/占位)不算)"""
    toks = (f"第{n}章", f"第{n:03d}章")
    stamped = []
    for f in sorted(LEDGERS.glob("*.md")):
        if f.name == "waivers.md":
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s.startswith("- "):
                continue
            if re.search(r"待记|TODO|占位|待补", s):
                continue
            if any(t in s for t in toks):
                stamped.append(f.stem)
                break
    return stamped

def read_text(p, limit=None):
    if not p or not pathlib.Path(p).exists():
        return ""
    t = pathlib.Path(p).read_text(encoding="utf-8")
    if limit is None:
        return t
    return t[limit:] if limit < 0 else t[:limit]  # 负数=取末尾N字

def stub_chapter_alert():
    """红队中断恢复: 末章是残章(cjk<1500)时报警——42字断句曾被当'上一章末尾'注入下一章(E8实测)"""
    try:
        cm2 = chapter_map()
        if not cm2:
            return
        last = max(cm2)
        p2 = cm2[last]
        cjk = len(re.sub(r"[^\u4e00-\u9fff]", "", p2.read_text(encoding="utf-8", errors="ignore")))
        if 0 < cjk < 1500:
            print(f"[WARN] 第{last:03d}章仅{cjk}字——疑中断残留,先补完该章再推进(status/next/bundle均提醒)")
    except Exception:
        pass


def _atomic_write(path, text):
    """红队中断恢复: JSON/状态写入tmp+os.replace——半截JSON会静默重置scores历史(E1实测)"""
    import os
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _load_json_warn(path, default):
    """红队中断恢复: 损坏显式告警,不再静默吞成默认值"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] {path.name}损坏({e})——用默认值续跑;修复后跑: pipeline.py scores --recompute")
        return default


def run_check_metrics(fp):
    _bd = pathlib.Path(fp).resolve()
    _flagpath = next((_bd.parents[i] / "text" / ".modern" for i in range(3) if (_bd.parents[i] / "text" / ".modern").exists()), None)
    flag = ["--modern"] if _flagpath else []   # 红队冷读可信: 原只认ROOT,多书仓里1993书会假FAIL
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
    sp = STYLE
    if sp and sp.exists():
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

def sync_hooks():
    """铁律一: 没有机器强制的流程等于不存在。.git/hooks里的拷贝必须与tools/源头一致,
    否则修改工具后跑的还是旧门(已发生过:'0字'假FAIL事故)。status时自动同步并报告。"""
    import hashlib, shutil as _sh
    src = ROOT / "tools" / "pre-commit-hook.sh"
    dst = ROOT / ".git" / "hooks" / "pre-commit"
    if not src.exists() or not (ROOT / ".git").exists():
        return None
    def h(p):
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""
    if h(src) != h(dst):
        _sh.copyfile(src, dst)
        import os, stat
        os.chmod(dst, os.stat(dst).st_mode | stat.S_IEXEC)
        return "已同步(源与.git/hooks不一致,已覆盖)"
    return None


def cmd_batch(args):
    """红队20260916 end-to-end批量化: 机器侧半自动驾驶——对区间逐章: 前置检查→bundle→四门→done,输出生产看板。
    AI侧(填卡/写正文/冷读)仍在人机回路,本命令报告每章的可推进/阻塞状态。"""
    nums = [a for a in args if not a.startswith("--")]
    if len(nums) < 2:
        print("用法: pipeline.py batch <起始章> <结束章> [--book 书根]")
        return 2
    n1, n2 = int(nums[0]), int(nums[1])
    cm = chapter_map()
    vols = G.scan_volumes(list(cm.values()))
    board = []
    for n in range(n1, n2 + 1):
        row = {"章": n, "状态": "OK", "阻塞": []}
        card = card_for(n)
        if card is None:
            row["阻塞"].append("无卡")
        else:
            ct = card.read_text(encoding="utf-8-sig")
            if any(m in ct for m in ("（填）", "（四选一", "（本章全部数字事实")):
                row["阻塞"].append("卡未填")
        body = cm.get(n)
        if body is None:
            row["阻塞"].append("无正文")
            row["状态"] = "BLOCKED"
            board.append(row)
            continue
        cjk = len(re.sub(r"[^\u4e00-\u9fff]", "", body.read_text(encoding="utf-8", errors="ignore")))
        row["字数"] = cjk
        if cjk < 1800:
            row["阻塞"].append(f"正文{cjk}字<1800(残章或未写)")
        rc, out, _ = run_check_metrics(body)
        if rc != 0:
            row["阻塞"].append("check未过")
        rc2, gout = run_gate("modified", [str(body)])
        if rc2 != 0:
            row["阻塞"].append("gate未过")
        dr = cold_read_for(n)
        row["冷读"] = "有" if dr else "无"
        stamped = ledger_stamped(n)
        miss = [x for x in LEDGER_NAMES if x not in stamped]
        if miss:
            row["阻塞"].append(f"缺账:{','.join(miss[:3])}")
        row["状态"] = "BLOCKED" if row["阻塞"] else "READY"
        board.append(row)

    print("\n═══ 生产看板 ═══")
    for r in board:
        flag = "🟢" if r["状态"] == "READY" else ("🟡" if r["状态"] == "OK" else "🔴")
        line = f"{flag} 第{r['章']:03d}章 {r['状态']}"
        if "字数" in r:
            line += f" {r['字数']}字"
        line += f" 冷读:{r.get('冷读', '?')}"
        if r["阻塞"]:
            line += " | 阻塞: " + "; ".join(r["阻塞"])
        print(line)
    ready = sum(1 for r in board if r["状态"] == "READY")
    blocked = sum(1 for r in board if r["状态"] == "BLOCKED")
    print(f"\n可验收(READY): {ready} | 阻塞(BLOCKED): {blocked} | 其余: 未到生产位")
    print("下一步: 对READY章跑 done N;对BLOCKED章按阻塞项处置")
    return 0




def cmd_produce(args):
    """单章全自动化流水线: era_clean→bundle→四门→auto_expand诊断→ledger_extract→done。
    AI侧(填卡/写正文/冷读)在人机回路。"""
    nums = [a for a in args if not a.startswith("--")]
    if not nums:
        print("用法: pipeline.py produce <章号> [--book 书根]")
        return 2
    n = int(nums[0])
    cm = chapter_map()
    body = cm.get(n)
    steps = []

    # 0. 卡检查
    card = card_for(n)
    if card is None:
        steps.append(("卡", "MISS", "无卡——先跑 skill_protocol gen card"))
    else:
        ct = card.read_text(encoding="utf-8-sig")
        has_fill = bool(scaffold_residue(ct))
        steps.append(("卡", "BLOCK" if has_fill else "OK", "骨架未填" if has_fill else "已填"))

    if body and body.exists():
        # 1a. era_clean(古代书自动清洗现代词)
        ec = subprocess.run([sys.executable, "tools/era_clean.py", str(body)],
                           capture_output=True, text=True, cwd=ROOT)
        steps.append(("era_clean", "OK", ec.stdout.strip()[:30] if ec.stdout else "清洁"))

        # 1b. era1993(年代书专用: .modern书自动扫穿帮词——20260917系统级接入)
        _modern_flag = body.parent
        while _modern_flag != _modern_flag.parent:
            if (_modern_flag / ".modern").exists():
                break
            _modern_flag = _modern_flag.parent
        if (_modern_flag / ".modern").exists():
            er = subprocess.run([sys.executable, "tools/era1993.py", str(body)],
                               capture_output=True, text=True, cwd=ROOT)
            steps.append(("era1993", "OK" if er.returncode == 0 else "FAIL",
                          er.stdout.strip()[:30] if er.stdout else "年代清洁"))

        # 2. fix_quotes
        fq = subprocess.run([sys.executable, "tools/fix_quotes.py", str(body)],
                           capture_output=True, text=True, cwd=ROOT)
        steps.append(("fix_quotes", "OK", fq.stdout.strip()[:30] if fq.stdout else "清洁"))

        # 3. bundle
        r = subprocess.run([sys.executable, "tools/pipeline.py", "bundle", str(n), "--book", str(BOOK.name)],
                          capture_output=True, text=True, cwd=ROOT)
        steps.append(("bundle", "OK" if r.returncode == 0 else "FAIL", ""))

        # 4. check
        rc, out, met = run_check_metrics(body)
        steps.append(("check", "OK" if rc == 0 else "FAIL", f"{met.get('fails', '?')}F" if met else ""))
        # 5. gate
        rc2, gout = run_gate("new" if not is_committed(body) else "modified", [str(body)])
        steps.append(("gate", "OK" if rc2 == 0 else "FAIL", ""))
        # 6. voice
        rv = subprocess.run([sys.executable, "tools/voice_check.py", str(body)],
                           capture_output=True, text=True, cwd=ROOT)
        steps.append(("voice", "OK" if "PASS" in rv.stdout else "FAIL", ""))
        # 7. card_check
        cc = subprocess.run([sys.executable, "tools/card_check.py", str(n), "--volume", "1", "--book", str(BOOK.name)],
                           capture_output=True, text=True, cwd=ROOT)
        steps.append(("card_check", "OK" if cc.returncode == 0 else "FAIL", cc.stdout.strip()[-20:] if cc.stdout else ""))

        # 8. auto_expand诊断(只报告)
        ae = subprocess.run([sys.executable, "tools/auto_expand.py", str(body), "--target", "2400"],
                           capture_output=True, text=True, cwd=ROOT)
        has_deficit = "欠" in ae.stdout and "✅" not in ae.stdout
        steps.append(("expand诊断", "NEED" if has_deficit else "OK", ae.stdout.strip().split("\n")[1][:40] if len(ae.stdout.strip().split("\n")) > 1 else ""))

        # 9. ledger_extract(自动抽取八账)
        le = subprocess.run([sys.executable, "tools/ledger_extract.py", str(n), "--book", str(BOOK.name)],
                           capture_output=True, text=True, cwd=ROOT)
        steps.append(("ledger抽取", "OK", le.stdout.strip().split("\n")[-1][:30] if le.stdout else ""))

    # 输出
    print(f"\n═══ 第{n:03d}章 全自动流水线 ═══")
    all_ok = True
    for name, status, detail in steps:
        icon = "✅" if status == "OK" else ("🟡" if status in ("MISS", "NEED") else "🔴")
        print(f"  {icon} {name:12s} {status:6s} {detail}")
        if status in ("FAIL", "BLOCK", "MISS"):
            all_ok = False

    if not body or not body.exists():
        print("\n→ 下一步: 写正文")
        return 1
    if all_ok:
        print("\n→ 全绿。下一步: 独立冷读→done→commit")
        return 0
    else:
        print("\n→ 有阻塞项,先修复")
        return 1


def cmd_volume_close(args):
    """卷末自动交接: 归档本卷→生成下卷脚手架→香火/数字账结算"""
    nums = [a for a in args if not a.startswith("--")]
    if not nums:
        print("用法: pipeline.py volume-close <卷末章号> [--book 书根]")
        return 2
    n = int(nums[0])
    cm = chapter_map()
    vols = G.scan_volumes(list(cm.values()))
    vol_num = G.parse_vol(cm[n]) if n in cm else None
    if not vol_num:
        print("[FAIL] 无法确定卷号")
        return 1

    print(f"═══ 卷{vol_num}末交接(ch{n:03d}) ═══")
    checks = []

    # 1) 卷摘要存在
    vol_sum = BOOK / "圣经" / f"卷{vol_num}章摘要.md"
    checks.append(("卷章摘要", vol_sum.exists() and vol_sum.stat().st_size > 100))

    # 2) 人物圣经卷末快照
    bible = BOOK / "人物圣经.md"
    bt = bible.read_text(encoding="utf-8") if bible.exists() else ""
    checks.append(("卷末快照", f"卷{vol_num}末" in bt or f"卷{vol_num}末" in bt))

    # 3) 伏笔账卷末盘点
    fban = BOOK / "ledgers" / "伏笔.md"
    ft = fban.read_text(encoding="utf-8") if fban.exists() else ""
    unfired = [l for l in ft.splitlines() if "充能" in l and "第" in l]
    checks.append((f"在跑伏笔({len(unfired)}条)", len(unfired) > 0))

    # 4) 香火账/数字账结算
    for acc_name in ("香火账", "数字账"):
        acc = BOOK / "ledgers" / f"{acc_name}.md"
        has_balance = acc.exists() and "余额" in acc.read_text(encoding="utf-8")
        checks.append((f"{acc_name}结算", has_balance))

    all_pass = all(ok for _, ok in checks)
    for name, ok in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon} {name}")

    if all_pass:
        print(f"\n✅ 卷{vol_num}交接检查全过。下一步: arc-review + 锚金丝雀 + 下卷立项")
    else:
        print(f"\n❌ 有未完成项,补齐后再交接")
    return 0 if all_pass else 1



def cmd_stats(args):
    """质量指标统计: 各书冷读均分/章数追踪"""
    import re as _re
    for bk_dir in sorted(ROOT.iterdir()):
        if not bk_dir.is_dir() or bk_dir.name.startswith("."):
            continue
        audit_dir = bk_dir / "audit"
        if not audit_dir.is_dir():
            continue
        scores = []
        for cr in sorted(audit_dir.glob("冷读-第*.md")):
            ct = cr.read_text(encoding="utf-8", errors="ignore")
            m = _re.search(r"总分[:：]\s*\*{0,2}([0-9](?:\.[0-9])?)", ct)
            if m:
                scores.append(float(m.group(1)))
        if scores:
            avg = round(sum(scores)/len(scores), 1)
            print(f"  {bk_dir.name}: {len(scores)}章冷读 均分{avg} 区间[{min(scores)}-{max(scores)}]")
    return 0


def cmd_status():
    stub_chapter_alert()
    hs = sync_hooks()
    if hs:
        print(f"hook同步: {hs}")
    cm = chapter_map()
    vols = G.scan_volumes(list(cm.values()))
    maxn = max(cm) if cm else 0
    nxt = maxn + 1
    pg = progress_data()
    print(f"进度: max={maxn} next={nxt} 卷={vols}")
    # 结构同构门(advisory,大审计-08/11): 跨章开场/收尾/场景数分布
    try:
        sc = subprocess.run([sys.executable, str(ROOT / "tools" / "structure_check.py")],
                            capture_output=True, text=True, timeout=60)
        lines = [l for l in sc.stdout.splitlines() if l.startswith(("  ", "跨章", "结构门", "──"))]
        brief = [l for l in lines if "[WARN]" in l or "[FAIL]" in l or "标准差" in l or l.startswith("跨章")]
        print("结构门: " + ("; ".join(brief) if brief else "PASS"))
    except Exception as e:
        print(f"结构门: 跳过({e})")
    if pg.get("story_time"):
        print(f"故事时间: {pg['story_time']}")

    # 写前新鲜度门(大审计-20: 时刻卡新鲜度只在done查,写前不查)
    mm = re.search(r"下一章[:：]\s*第?(\d{3})章", read_text(LEDGERS / "当前时刻卡.md"))
    if mm and int(mm.group(1)) != nxt:
        print(f"新鲜度: [WARN] 当前时刻卡'下一章'指向第{mm.group(1)}章,实扫应为第{nxt:03d}章——先更新ledgers/当前时刻卡.md")
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
    mat_left = len([l for l in read_text(MATERIAL).splitlines()
                    if l.strip().startswith(("- ", "  - ")) and "已用:" not in l]) if MATERIAL.exists() else 0
    est = mat_left // 3 if mat_left else 0
    if mat_left < 30:
        print(f"[红灯] 素材库仅剩{mat_left}条(约{est}章耗尽)——立即扩容(world-economy/行业经营库)")
    else:
        print(f"素材库余量: {mat_left}条(约{est}章)")
    print(f"下一动作: pipeline.py next {nxt}")
    return 0

# ---------------- next ----------------
def cmd_next(args):
    stub_chapter_alert()
    # 脏章检测(20260917用户铁令): done后正文被改但未重跑done=脏章,禁止推进
    _hf = BOOK / "ledgers" / ".done_hashes"
    if _hf.exists():
        import hashlib as _hl
        _dm = chapter_map()
        for _line in _hf.read_text().splitlines():
            if ":" not in _line: continue
            _k, _, _v = _line.partition(":")
            _k = _k.strip()
            if not _k.isdigit(): continue
            _f = _dm.get(int(_k))
            if _f and _f.exists():
                _cur = _hl.sha1(_f.read_bytes()).hexdigest()
                if _cur != _v.strip():
                    print(f"[脏章] 第{int(_k):03d}章正文在done后被修改——请重跑: pipeline.py done {_k}")
                    return 1
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
    # 磨刀十六批: 卷切换机器触发——expected_volume跳变(上一章属卷A,本章属卷B)即硬提示卷末流程,无人时不再靠人记
    if maxn:
        _prev_vol = G.expected_volume(maxn, vols)
        if _prev_vol and exp and _prev_vol != exp:
            print(f"[卷末触发] 第{maxn:03d}章为{_prev_vol}末章,第{n:03d}章开新卷{exp}——")
            print(f"  先走periodic phase_volume_end(卷末复盘/一致性/人物审计/下卷纲红队),再开新章;")
            print(f"  无下卷纲时bundle会缺章场景清单——先volume-outline,禁裸写")
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
    stub_chapter_alert()
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
    # ── 开写门(20260917用户战略纠偏:"构思没做到位就急于开写") ──
    # 第001章bundle=全书开写时刻,强制核构思域五件套;缺=拒开写(ideate域final_gate机器化)
    if n == 1:
        _dm = []
        def _has(rel):
            return (BOOK / rel).exists() if BOOK != ROOT else (ROOT / rel).exists()
        if not _has("story/20-人物/人物圣经.md"):
            _dm.append("人物圣经(char-bible:五层弧线)")
        if not _has("story/01-主题.md"):
            _dm.append("主题档案(theme-dossier)")
        if not _has("story/素材库.md"):
            _dm.append("素材库(world-economy)")
        if not _has("story/30-情节/卷册表.md"):
            _dm.append("卷册表(全书弧线+问题句)")
        _o = (BOOK / "story/卷一纲.md") if BOOK != ROOT else (ROOT / "story/30-情节/卷一纲.md")
        _ot = _o.read_text(encoding="utf-8") if _o.exists() else ""
        if _ot and "名场面" not in _ot:
            _dm.append("set-piece名场面钉桩(纲内须有名场面节)")
        if _dm:
            print("[开写门·FAIL] 构思域缺" + str(len(_dm)) + "项——禁止开写正文:")
            for d in _dm:
                print("  ✗ " + d)
            print("  (20260917用户质询:'构思没做到位就急于开写';此门机器强制,补齐后重跑)")
            return 2
    sp = STYLE
    if sp is None:
        missing.append("书根风格包.md(多书隔离禁回退主书;走style-compiler)")
    elif not sp.exists():
        missing.append("story/50-风格包.md")
    voice = VOICE_TABLE
    if voice is None and BOOK != ROOT:
        print('[红灯] 书根缺声口卡.md——voice_check与bundle将空转;立声口卡(char-voice)')
    if not voice.exists():
        missing.append("story/20-人物/声纹表.md")
    if missing:
        print("[前置缺失] " + "; ".join(missing))
        return 2

    items = []  # (名, 实占, 上限, 正文)
    def add(name, cap, text):
        text = (text or "").strip()
        items.append((name, len(text), cap, crop(text, cap, name)))
    # 范例段飞轮(磨刀十八批提上限: 冷读高光自喂——注入2段匹配场景型的本书最佳文字)
    # 红队20260915: 原条件 `A and B if C else D` 按Python优先级解析成 `(A and B) if C else D`
    # → 非生活卡时"匹配型+动作型"全部注入且无2段上限(031/032事故: 动作型3条垃圾全量进槽);
    # 改为显式分池+总数封顶2段+按章号轮换取段(防每章恒喂同2段→风格近亲繁殖)
    _lib = BOOK / "风格包范例段库.md"
    if _lib.exists() and card:
        _card_t = read_text(card)
        _want = "生活" if _card_t.count("细节") + _card_t.count("钱面") >= 2 else ("对话" if _card_t.count("“") > 6 else ("收尾" if "钩" in _card_t else "情感"))
        _pool, _cur, _last = {}, None, None
        for _l in read_text(_lib).splitlines():
            m = re.match(r"## (\w+)型", _l)
            if m:
                _cur = m.group(1)
                _pool.setdefault(_cur, [])
                _last = None
                continue
            if _l.startswith("- 第") and _cur:
                _pool[_cur].append(_l)
                _last = _pool[_cur][-1]
            elif _l.strip() and _last is not None and _cur:
                _pool[_cur][-1] += "\n" + _l   # 多行范例(冷读引用块)续行并入同一条目
        _segs = []
        for _t in ((_want, "动作") if _want != "生活" else ("生活",)):
            _es = _pool.get(_t, [])
            while _es and len(_segs) < 2:
                _segs.append(_es.pop((n + len(_segs)) % len(_es)))   # 按章轮换
        if _segs:
            add("0范例段(本书最佳·模仿其质感非内容)", 500, "\n".join(_segs))


    add("1固定指令前缀", 650, PREFIX)
    add("2场景卡(全文)", 1600, read_text(card))  # 大审计-20: 收口卡700被裁
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
    # 红队注入质量: 声口卡(##人名节式)整节注入——表格不存在时槽3曾恒空,声口禁词从未进包
    _vs = read_text(voice)
    if "|" not in _vs:
        _sec_name, _sec_buf = None, []
        _secs = []
        for l in _vs.splitlines():
            m2 = re.match(r"^##\s+([^#\n]+)\s*$", l)
            if m2:
                if _sec_name:
                    _secs.append((_sec_name, "\n".join(_sec_buf)))
                _nm = re.sub(r"[（(].*?[）)]", "", m2.group(1)).strip()
                _sec_name, _sec_buf = _nm, [l]
            elif _sec_name:
                _sec_buf.append(l)
        if _sec_name:
            _secs.append((_sec_name, "\n".join(_sec_buf)))
        present += [body for nm, body in _secs if nm in card_text or nm in cast]
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
    add("6当前时刻卡", 1400, read_text(LEDGERS / "当前时刻卡.md"))  # 大审计-20: 934/500静默裁剪收口指令,P0
    # 7 圣经: 全书卡(修烂账:进度改由实扫)+卷摘要(不存在则用章摘要近窗,大审计-20)
    bible = read_text(BIBLE / "全书卡.md") if BIBLE else "(缺圣经目录——书根建圣经/,断点恢复与跨卷记忆靠它)"
    _volsum = (BIBLE / f"卷{int(re.search(r'\d+', exp).group())}章摘要.md") if (BIBLE and exp and re.search(r'\d+', exp)) else ((BIBLE / "卷摘要.md") if BIBLE else None)   # 磨刀十六批: 产物名统一;红队20260915: BIBLE可为None(书根隔离禁回退)
    if _volsum and _volsum.exists():
        _vs = read_text(_volsum)
        bible += "\n" + (_vs if len(_vs) <= 1500 else "…(头部压缩)…" + _vs[-1450:])   # 红队20260915: 卷摘要超限保尾弃头(最新章摘要在尾部)
    else:
        _zq = (BIBLE / f"卷{int(re.search(r'\d+', exp).group())}章摘要.md") if (BIBLE and exp and re.search(r'\d+', exp)) else ((BIBLE / "章摘要.md") if BIBLE else None)
        if _zq and _zq.exists():
            bible += "\n" + read_text(_zq, -900)
    add("7圣经(全书卡+章摘要近窗)", 1500, bible)
    # 8 伏笔账在跑项
    fb = [l for l in read_text(LEDGERS / "伏笔.md").splitlines()
          if re.search(r"状态.*(养|悬空|待回收|充能|引信|排期|大压|悬)", l)]
    add("8伏笔在跑项", 2600, "\n".join(fb))  # 随章数增长,季度性归档已兑项可回撤  # 大审计-20: 1435/600静默裁剪,P0
    # 9 钩分布/类型轮换近窗
    hooks = read_text(LEDGERS / "钩分布.md", -250)
    rotate = read_text(LEDGERS / "类型轮换.md", -250)
    add("9钩/类型近窗", 550, hooks + "\n" + rotate)
    # 12 知情状态近窗(大审计-20断点恢复缺口: 知情状态无法恢复)
    kb = read_text(LEDGERS / "口碑账.md", -450)
    add("12口碑账近窗(谁知道什么)", 500, kb)

    # 10 生活素材(audits/21-Fix1): cast从声纹表派生(禁硬编码),按卡面提及打分,
    #    按地点分区加权,J区语言恒带2条;素材须变形入文(数字保留,表述重造)
    mat_path = MATERIAL
    mat_raw = read_text(mat_path) if mat_path else ""
    if BOOK != ROOT and mat_path is None:
        print("[红灯] 书根缺素材库.md——多书隔离禁回退主书素材(红队20260915跨书污染);走world-economy建本书素材库")
    # 当前section标记
    sec = ""
    mat_items = []  # (section, line)
    for l in mat_raw.splitlines():
        if l.startswith("## "):
            sec = l[3:].strip()[:8]
        elif l.strip().startswith(("- ", "  - ")) and "已用:" not in l and not l.strip().startswith("- 202"):
            mat_items.append((sec, l.strip()))
    # cast从声纹表表格首列派生;声口卡(##人名头)格式兼容(红队20260915: 1993书表格不存在→cast恒空)
    cast = []
    for l in read_text(voice).splitlines():
        if l.strip().startswith("|") and not re.search(r"^\|[-\s|:]+\|?$", l.strip()):
            cell = l.strip().strip("|").split("|")[0].strip("*# 【】[]")
            if cell and cell not in ("人", "—") and len(cell) <= 4:
                cast.append(cell)
    if not cast:
        cast = [re.sub(r"[（(].*?[）)]", "", m.group(1)).strip()
                for m in re.finditer(r"^##\s+([^#\n]{2,20})\s*$", read_text(voice), re.M)]
        cast = [c for c in cast if 2 <= len(c) <= 4]   # 红队注入质量: "## 陈长贵(主角)"括号注记曾致槽3恒空
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
    print(f"  合计: {total}字 (硬上限10200" + (",超限!" if total > 9000 else ",OK") + ")")
    if total > 10200:
        print("[FAIL] 注入包超硬上限10200字——先跑ledger_compact/伏笔归档再生成(磨刀十五批: 原超限仍return 0=注入静默截断)")
        return 1
    print()
    print()
    print("===== BUNDLE-START (按序注入,顺序即优先级) =====")
    for name, used, cap, body in items:
        print(f"\n◀ {name} ▶\n{body}")
    print("\n===== BUNDLE-END =====")
    try:
        bundle_log(n, total, card=card_for(n))
    except Exception:
        pass
    return 0

# ---------------- bundle落盘(磨刀十三批H6: 注入过程痕迹,done验第NNN章在档) ----------------
def bundle_log(n, size, card=None):
    import datetime, hashlib
    gr = LEDGERS / "生成记录.md"
    head = "# 生成记录(bundle注入落盘——正文生成前必跑pipeline.py bundle N,此账=过程证据链)\n"
    if not gr.exists():
        gr.write_text(head, encoding="utf-8")
    # 红队20260915指纹链: 正文必须生成于这版注入物之下;done重算比对,事后改卡/改时刻卡而不重bundle=可检出
    def _sha(p):
        return hashlib.sha1(p.read_bytes()).hexdigest()[:12] if p and p.exists() else "缺"
    mom = LEDGERS / "当前时刻卡.md"
    fp = f" 指纹[卡:{_sha(card)} 时刻卡:{_sha(mom)}]"
    line = f"- 第{n:03d}章 | {datetime.date.today()} | bundle注入包{size}字(PREFIX/锚/时刻卡/伏笔在档){fp}\n"
    txt = gr.read_text(encoding="utf-8")
    if f"第{n:03d}章 |" not in txt:
        gr.write_text(txt.rstrip() + "\n" + line, encoding="utf-8")
    elif fp not in txt:
        # 已有记录但指纹变了→追加重bundle记录(不覆盖历史,过程链完整)
        gr.write_text(txt.rstrip() + "\n" + f"- 第{n:03d}章 | {datetime.date.today()} | 重bundle(注入物变更){fp}\n", encoding="utf-8")


# ---------------- check ----------------
def cmd_check(args):
    card_only = "--card-only" in args
    args = [a for a in args if a != "--card-only"]
    if card_only:
        # 审计-32 S2: 先卡后稿的工作流需要纯卡阶段检查(正文不存在时也可验)
        worst = 0
        for a in args:
            n = int(re.sub(r"\D", "", a) or 0)
            card = card_for(n)
            if card is None:
                print(f"[FAIL] 场景卡不存在(text/卡或书根卡 *第{n:03d}章*)——先走scene-card")
                worst = 1
                continue
            ct = read_text(card)
            need = ["场景型", "戏剧问题", "冲突源", "代价", "Forbid", "钩"]
            miss = [k for k in need if k not in ct]
            if miss:
                print(f"[FAIL] 卡缺字段{miss}: {card.name}")
                worst = 1
            else:
                print(f"✅ 卡检查通过({card.name})")
        return worst
    if not args:
        print("用法: pipeline.py check <file...> [--card-only]"); return 2
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
    # 20260917用户铁令: 冷读不设软门——每章必冷读,缺失一律FAIL(原非硬门=软WARN可跳=漏洞)
    hard_cold = True
    if cr is None:
        msg = "无冷读记录(story/audit/冷读-第{:03d}章.md)——运行reader-proxy后落盘".format(n)
        (problems if hard_cold else warns).append(msg + ("[硬门]" if hard_cold else "[软门]"))
        # 红队20260917修: 原hash校验误置于cr=None分支必崩(AttributeError),移至else(cr存在)分支
    else:
        # 出处账(红队二轮: 硬门章冷读须在ledgers/冷读出处.md登记hash;自写报告=自我阅卷)
        if hard_cold:
            _pro = LEDGERS / "冷读出处.md"
            import hashlib as _h2
            _rhash = _h2.sha1(cr.read_bytes()).hexdigest()[:12]
            _prook = _pro.exists() and any(
                (f"第{n:03d}章" in l or f"第{n}章" in l) and _rhash in l
                for l in _pro.read_text(encoding="utf-8").splitlines())
            if not _prook:
                (warns if (revise or post) else problems).append(
                    f"冷读报告无出处登记(ledgers/冷读出处.md 缺 hash{_rhash} 行)——硬门章冷读须由独立代理产出并落账")
        # 红队20260915: 冷读内容门——一行文伪造/低分/不会翻必须拦(新章FAIL,后验WARN)
        _crt = cr.read_text(encoding="utf-8", errors="ignore")
        _sc = re.search(r"总分[:：]\s*\*{0,2}([0-9](?:\.[0-9])?)", _crt)   # 红队: 总分:**6/10**粗体格式
        _fail = None
        if len(_crt) < 600:
            _fail = "冷读报告过薄(<600B,疑似一行文)"
        elif not _sc:
            _fail = "冷读无总分数字"
        elif float(_sc.group(1)) < 7:
            _fail = f"冷读{_sc.group(1)}分(<7)"
        elif re.search(r"追读判定[:：]\s*不会翻", _crt):
            _fail = "冷读判定不会翻"
        if _fail:
            (warns if (revise or post) else problems).append(
                f"{_fail}——打回重写(reader-proxy),豁免走waivers[{'硬门' if hard_cold else '软门'}]")
        else:
            # 红队冷读可信度: 摘录verbatim绑定——报告引文/块引必须多数真在正文(防伪造报告/复制旧报告改号)
            _ch = re.sub(r"[\s\u201c\u201d\"]+", "", p.read_text(encoding="utf-8", errors="ignore"))
            _qs = re.findall(r"\u300c([^\u300c\u300d]{12,})\u300d", _crt) + [m for m in re.findall(r'"([^"\n]{16,})', _crt)]
            _qs += [l.strip()[1:].strip() for l in _crt.splitlines() if l.strip().startswith(">") and len(l.strip()) > 14]
            _hits = sum(1 for q in _qs if re.sub(r"[\s\u201c\u201d\"]+", "", q) in _ch)
            if len(_qs) >= 6 and _hits == 0:
                (warns if (revise or post) else problems).append(
                    f"冷读摘录0/{len(_qs)}命中正文——疑似伪造报告或复制旧报告改号(红队冷读可信度)")

    # 6 卡字数预算 vs 实测
    cjk = (met or {}).get("cjk", 0)
    if budget and cjk:
        mid = sum(budget) / 2
        delta = (cjk - mid) / mid * 100
        if delta < -32:
            warns.append(f"字数低于卡预算{delta:.0f}%(实测{cjk} vs 卡{budget})——峰章体量红线,beat-expand回炉项")

    # 6.5 当前时刻卡随章断言(软门,audits/22-11)
    moment = read_text(LEDGERS / "当前时刻卡.md")
    if f"第{n:03d}章" not in moment and f"第{n}章" not in moment:
        warns.append(f"当前时刻卡未含第{n:03d}章——跨会话恢复注入物过期,更新ledgers/当前时刻卡.md")

    # 6.6 口供对账(大审计-11:台账引用的章末拍必须真实存在于正文末尾)
    m2 = re.search(r'上一章末拍[:：]\s*[“"](.+?)[”"]\s*[（(](\d{3})[）)]', moment)
    if m2:
        quote, qn = m2.group(1), int(m2.group(2))
        qf = cm.get(qn)
        if qf is None:
            warns.append(f"当前时刻卡'上一章末拍'引用第{qn:03d}章——该章不存在(坏引用,大审计-20不可自愈点)")
        else:
            qtail = [l.strip() for l in qf.read_text(encoding="utf-8").splitlines() if l.strip()]
            if qtail and not any(quote[:10] in l for l in qtail[-3:]):
                warns.append(f"当前时刻卡'上一章末拍'引文「{quote}」不在第{qn:03d}章末三行——口供失真,更新当前时刻卡")

    # 6.7 数字表对账(大审计-11反向:卡上数字表条目必须在正文兑现)
    if card is not None:
        card_text = card.read_text(encoding="utf-8-sig")
        mt = re.search(r'数字表\*?\*?[:：]\s*([^\n]+)', card_text)
        if mt:
            body_full = p.read_text(encoding="utf-8")
            miss = []
            for x in re.findall(r'\d{2,4}(?:\.\d+)?', mt.group(1)):
                if not any(v in body_full for v in zh_num_variants(x)):
                    miss.append(x)
            if miss:
                warns.append(f"数字表条目未在正文兑现: {miss}——表外数字=穿帮,表内数字=空账,对齐两者")

    # 6.8 期待链刻度(技能-检测对齐表#1): 爽点管道在充能<2条=WARN
    try:
        _pipe = read_text(LEDGERS / "爽点管道.md")
        _charging = len(re.findall(r"\|\s*P\d\s*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|[^|]*\|\s*(充能|大压中|排期)", _pipe))
        if _pipe and _charging < 2:
            warns.append(f"期待链在充能仅{_charging}条(<2红线)——排下一波蓄压,见ledgers/爽点管道.md")
    except Exception:
        pass

    # 6.9 漂移审计触发器(技能-检测对齐表#2): 每10章硬提醒
    _drift_dir = AUDIT_DIR if BOOK != ROOT else ROOT / "story" / "audit"
    if n % 10 == 0 and not (_drift_dir / f"漂移审计-第{n // 10}期.md").exists():
        warns.append(f"第{n // 10}期漂移审计未落盘({_drift_dir})——满10章强制项[硬提醒]")

    # 6.95 技能执行率+四产物存在性(磨刀十三批H3-H6: 删记录即绕过/章摘要/人物圣经演进层/bundle生成记录全堵)
    sp = BOOK / "ledgers" / "技能执行记录.md"
    _spt = read_text(sp) if sp.exists() else ""
    if sp.exists():
        _tot = len([l for l in _spt.splitlines() if l.strip().startswith("- [")])
        _done = len([l for l in _spt.splitlines() if l.strip().startswith("- [x]")])
        if _spt:
            import subprocess as _sp
            rc_ev = _sp.run([sys.executable, "tools/skill_protocol.py", "audit", str(n), "--book", str(BOOK), "--evidence"],
                            capture_output=True, text=True, cwd=ROOT)
            if rc_ev.returncode != 0:
                (warns if (revise or post) else problems).append(
                    "技能执行记录证据链不过(打勾无产物引用/引用断裂)——红队20260915: 自证打勾=可偷懒,新章必须带'→ 产物: 路径'")
        if _tot and _done < _tot:
            (warns if revise else problems).append(
                f"技能执行记录未全勾({_done}/{_tot})——跳过的步骤产物按SKILL_PROTOCOL无效;漏项见{sp.name}")
        # H3.5 按章断言(1993ch031事故: 只查全局勾选率,漏登记整章块=空放过)
        if f"第{n:03d}章" not in _spt and f"第{n}章" not in _spt:
            (warns if revise else problems).append(
                f"技能执行记录无第{n:03d}章条目块——按章登记缺失,补录或跑: skill_protocol.py list {n}")
    else:
        (warns if revise else problems).append(
            f"无技能执行记录({sp.name})——先跑: python3 tools/skill_protocol.py list {n} {(f'--book {BOOK.name}' if BOOK != ROOT else '')}".strip())
    # H4 章摘要(story-bible技能产物) —— 章摘要库按卷分册,通配匹配(硬编码卷1漏卷2+)
    _sb_tokens = (f"第{n:03d}章", f"第{n}章")
    _sb_paths = [BOOK / "故事圣经.md", BOOK / "story" / "60-圣经" / "故事圣经.md",
                 BOOK / "ledgers" / "章摘要.md", BOOK / "圣经" / "章摘要.md"]
    _sb_dir = BOOK / "圣经"
    if _sb_dir.is_dir():
        _sb_paths += sorted(_sb_dir.glob("*章摘要.md"))
    _sb_ok = any(p2.exists() and any(tk in p2.read_text(encoding="utf-8") for tk in _sb_tokens) for p2 in _sb_paths)
    if not _sb_ok:
        (warns if revise else problems).append(f"章摘要未含第{n:03d}章(story-bible技能memory步)——落盘: {BOOK.name if BOOK != ROOT else 'story/60-圣经/'}/故事圣经.md")
    # H5 人物圣经演进层盖章(活文档协议)
    if BOOK != ROOT:
        _bible = BOOK / "人物圣经.md"
        if _bible.exists():
            _bt = _bible.read_text(encoding="utf-8")
            if "演进层" in _bt and not any(tk in _bt for tk in _sb_tokens):
                (warns if revise else problems).append(f"人物圣经演进层未含第{n:03d}章——活文档协议: 每章归档同步当前状态/关系位移/披露进度")
        else:
            warns.append("书根缺人物圣经.md(设计完整性红灯项,system_readiness会拦)")
    # H6 生成记录(bundle过程痕迹——正文绕过PREFIX注入的直接证据链)
    _gr = BOOK / "ledgers" / "生成记录.md"
    if not (_gr.exists() and any(tk in _gr.read_text(encoding="utf-8") for tk in _sb_tokens)):
        (warns if revise else problems).append(f"生成记录未含第{n:03d}章(bundle注入无落盘)——先跑: pipeline.py bundle {n} 再生成正文")
    else:
        # 红队20260915指纹比对: 卡/时刻卡当前sha1 vs bundle时记录——事后偷改注入物可检出
        import hashlib as _hl
        _grt = _gr.read_text(encoding="utf-8")
        _row = [l for l in _grt.splitlines() if f"第{n:03d}章 |" in l and "指纹" in l]
        if _row:
            def _sha_now(pp):
                return _hl.sha1(pp.read_bytes()).hexdigest()[:12] if pp and pp.exists() else "缺"
            _card = card_for(n)
            _want = f"卡:{_sha_now(_card)} 时刻卡:{_sha_now(LEDGERS / '当前时刻卡.md')}"
            if _want not in _row[-1]:
                (warns if (revise or post) else problems).append(
                    f"注入物指纹不匹配(当前[{_want}] vs 记录{_row[-1][-46:]})——卡/时刻卡在bundle后被改过,重跑bundle或回滚改动")

    # 6.96 卷末章义务(1993审计: 卷一完结时arc-review/卷末快照全跳过,"平淡"拖到卷二才暴露)
    _decl = G.volume_decl(BOOK if BOOK != ROOT else ROOT)
    _expno = int(re.search(r"\d+", exp).group()) if exp and re.search(r"\d+", exp) else None
    if _decl and _expno in {int(re.search(r"\d+", k).group()) for k in _decl}:
        _is_volend = bool(_expno in {int(re.search(r"\d+", k).group()) for k in _decl} and _decl.get(f"卷{_expno}", (0, -1))[1] == n)
    else:
        _is_volend = False
        if not _decl and n == max(cm):
            warns.append("缺卷册表(story/30-情节/卷册表.md)——卷末义务门无法判卷边界,建表后生效")
    if _is_volend:
        _va = None
        for _cand in sorted((BOOK / "audit").glob(f"*连读审查*")) if (BOOK / "audit").is_dir() else []:
            _va = _cand
            break
        if _va is None:
            (warns if (revise or post) else problems).append(
                f"第{n:03d}章为卷{exp}末章,缺卷级连读审查(audit/*连读审查*.md)——arc-review是卷末强制项")
        _bt2 = (BOOK / "人物圣经.md").read_text(encoding="utf-8") if (BOOK / "人物圣经.md").exists() else ""
        if "卷末快照" in _bt2 and f"卷{_expno}末" not in _bt2 if "_expno" in dir() else False:
            (warns if (revise or post) else problems).append(
                f"人物圣经缺卷{exp}末快照——活文档协议卷末义务")

    # 7 八账盖章(1993ch031事故升级: 新章验收缺账=FAIL,补账/后验=WARN)
    stamped = ledger_stamped(n)
    missing = [x for x in LEDGER_NAMES if x not in stamped]
    if missing:
        _msg = f"八账未盖章: {missing}——ledger-update补记(禁无章号记账)"
        (warns if (revise or post) else problems).append(_msg)
    # 7.5 盖章格式schema(红队流水线: "- 第N章 空话"式token盖章可骗;ledger_schema按账最小schema验)
    try:
        from ledger_schema import chapter_stamps_ok
        _g, _b = chapter_stamps_ok(BOOK, n)
        if _b:
            _det = "; ".join(f"{nm}:{err[:40]}" for nm, errs in _b for err in errs)
            (warns if (revise or post) else problems).append(f"盖章行格式不合规: {_det}——见tools/ledger_schema.py各账schema")
    except ImportError:
        pass

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
    # 范例段飞轮收割(done后自动——冷读高光回落风格包范例段库,喂给后续章)
    import subprocess as _sp
    _sp.run([sys.executable, "tools/exemplar_flywheel.py", "harvest", str(BOOK)], capture_output=True, cwd=ROOT)
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
            data = _load_json_warn(SCORES, {"chapters": {}, "_comment": "重建(scores损坏)"})
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
    _atomic_write(SCORES, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

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
    _atomic_write(SCORES, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"\nscores.json已重算({len(cm)}章,head={head})。红灯章: {worst or '无'}")
    try:
        bundle_log(n, total, card=card_for(n))
    except Exception:
        pass
    return 0

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if "--book" in args:
        i = args.index("--book")
        args.pop(i)
        set_book(args.pop(i))
    cmd, rest = args[0], args[1:]
    if cmd == "status":
        return cmd_status()
    if cmd == "stats":
        return cmd_stats(args)
    if cmd == "batch":
        return cmd_batch(rest)
    if cmd == "produce":
        return cmd_produce(rest)
    if cmd == "volume-close":
        return cmd_volume_close(rest)
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
    ""