#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
self_test.py 工具自测套件——把历次事故靶测用例固化为可重复执行的单测(零依赖,纯标准库)

动机: voice_check/card_check 迭代时全靠临时脚本靶测,改一处崩一处(eval <- 调试耗时占比过高)。
覆盖:
  card_check.cn2num     中文口语数字 11 例(两千五/三百二/一万八…)
  fix_quotes            三态: 反向对修复/正常保留/奇数行跳过
  voice_check           双卡格式解析/人名括号剥离/轮转归属/否定前缀排除
  gate_chapter.book_root 多书根判定(主书/书根/保留目录)
  card_check 数字对账   正文含/缺 两态
  legacy_audit          心理句豁免(格言误报)

用法: python3 tools/self_test.py   全部通过 exit 0,否则打印失败项 exit 1
"""
import re, sys, pathlib, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILS = []


def case(name, cond, detail=""):
    if cond:
        print(f"  ✓ {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  ✗ {name}: {detail}")


def test_cn2num():
    print("[1] card_check.cn2num 中文口语数字")
    import card_check as c
    for s, want in [("两千五", 2500), ("三百二", 320), ("十二", 12), ("两", 2), ("四千五", 4500),
                    ("三十", 30), ("一万八", 18000), ("七万八", 78000), ("三万六", 36000),
                    ("五十", 50), ("九百", 900)]:
        got = c.cn2num(s)
        case(f"cn2num({s})={want}", got == want, f"got={got}")


def test_fix_quotes():
    print("[2] fix_quotes 三态")
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "t.md"
        f.write_text("”反向开头的对话。“他说。\n\n“正常。”\n\n”奇数结尾\n", encoding="utf-8")
        subprocess.run([sys.executable, str(ROOT / "tools" / "fix_quotes.py"), str(f)], capture_output=True)
        t = f.read_text(encoding="utf-8")
        case("反向对已修复", t.startswith("“反向开头的对话。”"), t.splitlines()[0][:20])
        case("正常行保留", "“正常。”" in t)
        case("奇数行不误改", "”奇数结尾" in t, t.splitlines()[-4:] and [l for l in t.splitlines() if "奇数" in l][0])


def test_voice_check():
    print("[3] voice_check 归属与排除")
    import voice_check as v
    # 双卡格式+括号剥离
    p2, err = v.parse_card(ROOT / "法医秦见微" / "声口卡.md")
    case("新书卡解析4人", not err and len(p2) == 4, f"{len(p2)}")
    case("人名括号已剥离", "秦见微" in p2, list(p2))
    p1, _ = v.parse_card(ROOT / "story" / "60-圣经" / "声口卡.md")
    case("主书卡解析8人", len(p1) == 8, f"{len(p1)}")
    # 否定前缀: "不一定"不算说"一定"
    import types
    q = [("贵的也不一定是好的", "", True)]
    text_all = q[0][0]
    case("否定前缀排除", v._negated("这不一定", "一定") and not v._negated("我一定去", "一定"))
    # 更直接: 构造_negated可测
    case("_negated(不一定)豁免", v._negated("这不一定", "一定"))
    case("_negated(一定)不豁免", not v._negated("我一定去", "一定"))


def test_book_root():
    print("[4] gate_chapter.book_root 多书根")
    import gate_chapter as g
    case("主书章→ROOT", g.book_root(ROOT / "text" / "卷1" / "第001章.md") == ROOT)
    case("新书章→书根", g.book_root(ROOT / "法医秦见微" / "text" / "卷1" / "第001章.md") == ROOT / "法医秦见微")
    case("非章路径→ROOT兜底", g.book_root(ROOT / "tools" / "x.md") == ROOT)


def test_card_check_nums():
    print("[5] card_check 数值比对")
    import card_check as c
    body = "他说百分之三。她给了二百五。"
    bv = c.extract_vals(body)
    case("正文'百分之三'数值化", 3.0 in bv, sorted(bv))
    case("正文'二百五'数值化", 250.0 in bv, sorted(bv))
    missing = c.extract_vals("卡载九百九十九") - bv
    case("缺数检出", 999.0 in missing, sorted(missing))


def test_legacy_aphor_exemption():
    print("[6] legacy_audit 心理句豁免")
    import legacy_audit as la
    m = la.APHOR_PAT.search("他知道这不是消防的问题，是管理费的问题")
    line = "他知道这不是消防的问题，是管理费的问题"
    is_psych = bool(la.PSYCH_PAT.search(line))
    case("心理句被豁免逻辑识别", is_psych)
    case("该句确含判词模式(豁免前的确会误报)", m is not None)


def test_new_gates():
    print("[7] 大审计-32六新门")
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "第999章.md"
        f.write_text(
            "第999章 测试\n\n。\n\n他说“引号开着没关\n\n全院炸了。全院炸了锅。\n\n"
            "赵大爷被他逗笑了，拍了一下大腿。崔兰又被他逗笑了。\n\n手一抖。手又抖。手再抖。\n\n"
            "“利六百。利一百六。利二百八。合计利九百四。”他说。\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), "--modern", str(f)],
                           capture_output=True, text=True)
        out = r.stdout
        for key in ["孤立标点段", "引号不闭合", "群体情绪标注", "笑声标注", "身体反应复用", "报表对白"]:
            case(f"门命中:{key}", key in out, "未命中")


def main():
    tests = [test_cn2num, test_fix_quotes, test_voice_check, test_book_root,
             test_card_check_nums, test_legacy_aphor_exemption, test_new_gates]
    for t in tests:
        try:
            t()
        except Exception as e:
            FAILS.append(f"{t.__name__} 异常: {e}")
            print(f"  ✗ {t.__name__} 异常: {e}")
    print(f"\n{'全部通过' if not FAILS else '失败 ' + str(len(FAILS)) + ' 项'}: "
          f"{sum(1 for t in tests)} 组")
    for f in FAILS:
        print("  -", f)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
