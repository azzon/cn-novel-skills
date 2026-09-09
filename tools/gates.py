#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gates.py 硬门检查器(技能体系的机制化闸门,docs/30机制规范5)
用法:
  python3 tools/gates.py style-ready          # 门1:风格包就位(无包禁写作)
  python3 tools/gates.py card-exists <卡路径>  # 门2:场景卡存在且非空模板(无卡禁生成)
  python3 tools/gates.py audit-marked <场景文件> # 门3:场景含验收通过标记(未验收禁拼章)
  python3 tools/gates.py ledger-fresh         # 门4:记账新于正文(不记账禁开新场)
  python3 tools/gates.py ideate-complete      # 门5:立项产物齐(构思域闸)
  python3 tools/gates.py all <卡路径>          # 写作前全门
违反任意门:非零退出+违规说明。全过:退出0+GREEN。
"""
import sys, pathlib, re, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
STORY = ROOT / "story"
TEXT = ROOT / "text"
LEDGERS = ROOT / "ledgers"

def _fail(msg): print(f"[GATE-FAIL] {msg}"); sys.exit(1)
def _pass(msg): print(f"[GREEN] {msg}")

def gate_style_ready():
    packs = sorted(STORY.glob("50-风格包*.md"))
    if not packs:
        _fail("无风格包(story/50-风格包*.md)——先运行 write:style-compiler;无包禁写作。")
    fp = packs[-1]
    if "盲评" in fp.read_text(encoding="utf-8") and "待跑" in fp.read_text(encoding="utf-8"):
        _fail("风格包盲评未完成(标'待跑')——盲评不过不收(style-compiler)。")
    s = fp.read_text(encoding="utf-8")
    if "范例" not in s or "风格卡" not in s:
        _fail("风格包不完整(缺风格卡或范例段)——回 style-compiler 补齐。")
    _pass("风格包就位。")

def gate_card_exists(card):
    fp = pathlib.Path(card)
    if not fp.exists():
        _fail(f"场景卡不存在:{fp}——先运行 write:scene-card;无卡禁生成。")
    s = fp.read_text(encoding="utf-8")
    blanks = re.findall(r"__[^\n]{0,8}", s)
    if len(blanks) > 30:
        _fail("场景卡疑似未填(空槽过多)——答案式填满再生成。")
    for must in ["戏剧问题", "价值", "钩"]:
        if must not in s:
            _fail(f"场景卡缺字段:{must}——回 scene-card。")
    _pass("场景卡就位。")

def gate_audit_light(scene):
    fp = pathlib.Path(scene)
    if not fp.exists(): _fail(f"文件不存在:{fp}")
    if "过(轻)" not in fp.read_text(encoding="utf-8"):
        _fail(f"{fp.name} 无简装标记——至少过check.py+抽检4项。")
    _pass("简装标记在。")

def gate_audit_marked(scene):
    fp = pathlib.Path(scene)
    if not fp.exists(): _fail(f"文件不存在:{fp}")
    s = fp.read_text(encoding="utf-8")
    if not re.search(r"验收[:：]\s*过", s):
        _fail(f"{fp.name} 无验收通过标记——先运行 audit:scene-audit;未验收禁拼章。")
    _pass("验收标记在。")

def gate_ledger_fresh():
    if not TEXT.exists():
        _pass("尚无正文,记账门免检。"); return
    texts = [t for t in TEXT.rglob("*.md") if "审" not in str(t) and "卡" not in str(t)]
    if not texts: _pass("尚无正文,记账门免检。"); return
    latest_text = max(t.stat().st_mtime for t in texts)
    need = ["伏笔.md", "梗.md", "钩分布.md", "类型轮换.md", "人物状态.md", "线弦.md"]
    missing = [n for n in need if not (LEDGERS / n).exists()]
    for n in need:
        fp = LEDGERS / n
        if fp.exists() and len(fp.read_text(encoding="utf-8").strip()) < 5:
            _fail(f"六账{n}为空文件(被清空但mtime新)——跑ops:rebuild从正文重导。")
    if missing: _fail(f"六账缺:{','.join(missing)}——先运行 ops:ledger-update;不记账禁开新场。")
    oldest_ledger = min((LEDGERS / n).stat().st_mtime for n in need)
    if oldest_ledger < latest_text:
        _fail("台账落后于最新正文(记的是旧账)——先补 ledger-update/timeline-keeper。")
    _pass("五账齐且新鲜。")

IDEATE_NEED = ["00-前提.md", "01-主题.md",
               "10-世界/规则.md", "10-世界/力量.md", "10-世界/地图.md", "10-世界/经济日常.md",
               "10-世界/历史.md", "10-世界/文化.md", "10-世界/呈现预算.md",
               "20-人物/主角.md", "20-人物/网络.md", "20-人物/声纹表.md",
               "20-人物/感情线.md",
               "30-情节/主线.md", "30-情节/卷一纲.md", "30-情节/开篇弧.md", "30-情节/多线表.md", "30-情节/名场面谱.md", "30-情节/单元库.md",
               "30-情节/伏笔总谱.md", "30-情节/奖励经济.md", "30-情节/节奏总谱.md",
               "40-定位.md"]

def gate_ideate_complete():
    missing = [n for n in IDEATE_NEED if not (STORY / n).exists()]
    if missing: _fail("立项产物缺:" + ", ".join(missing) + "——回 ideate 域对应叶补建。")
    _pass("立项产物齐。")

GATES = {"style-ready": gate_style_ready, "card-exists": gate_card_exists,
         "audit-marked": gate_audit_marked, "ledger-fresh": gate_ledger_fresh,
         "ideate-complete": gate_ideate_complete, "audit-light": gate_audit_light}

def main():
    args = sys.argv[1:]
    if not args or args[0] not in GATES:
        print(__doc__); sys.exit(2)
    name = args[0]
    if name == "all":
        if len(args) < 2: print("需要卡路径"); return 2
        gate_style_ready(); gate_card_exists(args[1]); gate_ledger_fresh()
        print("[GREEN] 写作前置三门全过。"); return
    if name in ("card-exists", "audit-marked"):
        if len(args) < 2: print("需要文件参数"); sys.exit(2)
        GATES[name](args[1])
    else:
        GATES[name]()

if __name__ == "__main__":
    main()
