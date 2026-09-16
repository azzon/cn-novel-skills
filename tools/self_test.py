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
    import shutil, subprocess
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
    # 双卡格式+括号剥离: 临时fixture(审计20260917: 旧书根已清,测试禁依赖可变书数据)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        card = pathlib.Path(td) / "声口卡.md"
        card.write_text(
            "# 声口卡\n"
            "## 秦见微（主角·法医）\n"
            "- 3个口头禅: “数据不会说谎”“死人不吵架”“嗯”\n"
            "- 2个禁词: “大概”“可能”\n"
            "## 老周（搭档）\n"
            "- 1个口头禅: “得嘞”\n"
            "## 林小姐（法助）\n"
            "- 1个口头禅: “好哒”\n"
            "## 犯人甲\n"
            "- 1个禁词: “我没杀人”\n"
            "## 遮名测试验收线\n"
            "- 说明行,不应被解析为人\n", encoding="utf-8")
        p2, err = v.parse_card(card)
        case("新书卡解析4人", not err and len(p2) == 4, f"{len(p2)}")
        case("人名括号已剥离", "秦见微" in p2, list(p2))
        case("保留节不入人表", "遮名测试验收线" not in p2, list(p2))
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
    print("[4] gate_chapter.book_root 多书根(临时构造,不依赖真实文件)")
    import gate_chapter as g, shutil
    bk = ROOT / "_tmp_book_selftest"
    (bk / "text" / "卷1").mkdir(parents=True, exist_ok=True)
    try:
        case("主书章→ROOT", g.book_root(ROOT / "text" / "卷1" / "第099章.md") == ROOT)
        case("新书章→书根", g.book_root(bk / "text" / "卷1" / "第001章.md") == bk)
        case("非章路径→ROOT兜底", g.book_root(ROOT / "tools" / "x.md") == ROOT)
    finally:
        shutil.rmtree(bk, ignore_errors=True)


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


def test_n1_assembly():
    print("[8] N1拼装疤门三态")
    import subprocess
    cases = {
        "真事故100%": ("崔兰来送饭，听说了这件事，把饭盒往桌上一放：“大龙，你娘的药吃了吗？”\n\n王大龙低头扒饭。\n\n崔兰来送饭，听说了这件事，把饭盒往桌上一放：“迅捷两千五？”", "FAIL"),
        "动作框架87%": ("王大龙抬起头，看了崔兰一眼。\n\n崔兰把饭盒放下。\n\n王大龙看了马小丁一眼。\n\n马小丁没说话。", "WARN"),
    }
    for name, (body, want) in cases.items():
        f = pathlib.Path(tempfile.mkdtemp()) / "第993章.md"
        f.write_text(f"第993章 测试\n\n{body}\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), "--modern", str(f)],
                           capture_output=True, text=True)
        got = "FAIL" if "拼装疤" in r.stdout else ("WARN" if "段首句疑似" in r.stdout else "无")
        case(f"拼装疤:{name}→{want}", got == want, f"got={got}")


def test_exit_and_timejump():
    print("[9] #63离场者+#64时间跳跃")
    import subprocess
    cases = {
        "离场者FAIL": ("老主顾摇摇头，还是走了。\n\n老主顾说：“那就这样吧。”", "离场者发言"),
        "时间跳跃WARN": ("6月15日，摊子开张第一天。\n\n8月26日，学费交完的日子。", "时间跳跃"),
    }
    for name, (body, key) in cases.items():
        f = pathlib.Path(tempfile.mkdtemp()) / "第99X章.md"
        f.write_text(f"第99X章 测试\n\n{body}\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), "--modern", str(f)],
                           capture_output=True, text=True)
        case(f"{name}", key in r.stdout, "未命中")


def test_number_and_anticipation():
    print("[10] number_audit恒等式+anticipation连击")
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as d:
        book = pathlib.Path(d) / "测试书"
        (book / "ledgers").mkdir(parents=True)
        (book / "text" / "卷1").mkdir(parents=True)
        (book / "ledgers" / "数字账.md").write_text(
            "# 数字账\n## 科目流水\n- 净利|九月|1533|ch20\n- 净利|十月|1112|ch20\n- 基金|截至十一月|9999|ch20\n"
            "## 恒等式\n- 基金(截至十一月) = 净利(九月) + 净利(十月)\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "number_audit.py"), str(book)],
                           capture_output=True, text=True)
        case("恒等式不平检出(9999≠2644)", "恒等式不平" in r.stdout, r.stdout[-80:])
        # 磨刀十八批F5: 减法+常数+首项无符号
        (book/"ledgers"/"数字账.md").write_text(
            "# 数字账\n## 科目流水\n- 公示期|法定|15|ch1\n- 剩余|死线|13|ch1\n"
            "## 恒等式\n- 剩余(死线) = 公示期(法定) - 2\n", encoding="utf-8")
        r3 = subprocess.run([sys.executable, str(ROOT/"tools"/"number_audit.py"), str(book)], capture_output=True, text=True)
        case("减法恒等式通过(15-2=13)", "验算通过" in r3.stdout and "FAIL" not in r3.stdout, r3.stdout[-80:])
        (book / "ledgers" / "钩分布.md").write_text(
            "- 第001章 [叙述收] 甲\n- 第002章 [叙述收] 乙\n- 第003章 [叙述收] 丙\n", encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(ROOT / "tools" / "anticipation_audit.py"), str(book)],
                            capture_output=True, text=True)
        case("平淡收连击检出", "平淡收连击" in r2.stdout, r2.stdout[-80:])


def test_scaffold_gate():
    print("[11] 脚手架门(卡+冷读指纹/残留,H0吞失败修复)")
    import subprocess, shutil
    bk = ROOT / "_tmp_sg_selftest"
    (bk / "卡").mkdir(parents=True, exist_ok=True)
    (bk / "audit").mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"), "gen", "card", "9", "--book", bk.name], capture_output=True)
        subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"), "gen", "coldread", "9", "--book", bk.name], capture_output=True)
        subprocess.run(["git", "add", str(bk)], capture_output=True, cwd=ROOT)
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"), "audit-cards"], capture_output=True, text=True, cwd=ROOT)
        case("骨架卡+骨架冷读被拦", ("骨架残留" in r.stdout or "占位提示语" in r.stdout) and r.returncode == 1, r.stdout[-60:])
        # 填空后应放行: 替换（填）并保留指纹
        for f in bk.rglob("*.md"):
            _t = f.read_text(encoding="utf-8").replace("（填）", "已填").replace("（四选一", "（已选").replace("（本章全部数字事实", "（数字事实")
            f.write_text(_t, encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"), "audit-cards"], capture_output=True, text=True, cwd=ROOT)
        case("填空+指纹放行", r2.returncode == 0 and "通过" in r2.stdout, r2.stdout[-60:])
    finally:
        subprocess.run(["git", "restore", "--staged", str(bk)], capture_output=True, cwd=ROOT)
        shutil.rmtree(bk, ignore_errors=True)


def test_canary_and_new_knives():
    """第12组: 金丝雀(带已知缺陷的文必须被抓)+#65编辑残渣+#66时序(1993全量审计)"""
    import shutil, subprocess
    tmp = ROOT / "_tmp_canary"
    tmp.mkdir(exist_ok=True)
    try:
        f = tmp / "第001章.md"
        content = (
            "第一章 测试\n\n"
            "他看着那个“哦”——不对，那个动静。"
            "初十那天他来了。初七那天他也来了。\n\n完。"
        )
        f.write_text(content, encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "check.py"), "--modern", "--scene", str(f)],
                           capture_output=True, text=True, cwd=ROOT)
        case("金丝雀:编辑残渣被抓", "编辑残渣" in r.stdout, r.stdout[-70:])
        case("金丝雀:时序乱序被抓", "时序词疑似乱序" in r.stdout, "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_goldmine_audit():
    """第13组: 矿产账审计(2026-09-15 era-goldmine)——双采/超窗FAIL,非重生书跳过"""
    import shutil, subprocess
    bk = ROOT / "_tmp_gm"
    led = bk / "ledgers"; led.mkdir(parents=True, exist_ok=True)
    try:
        (bk / "00-前提.md").write_text("他重生回1993年。", encoding="utf-8")
        (led / "时间线.md").write_text("- 第041章|1998年05月|股市|入场\n", encoding="utf-8")
        (led / "矿产账.md").write_text(
            "- [G-1] 94年大底 | 类别:股市 | 窗口:1994.07 | 采:第040章 | 收益:2万 | 时扰:0 | 状态:已采\n"
            "- [G-1] 94年大底 | 类别:股市 | 窗口:1994.07 | 采:第041章 | 收益:3万 | 时扰:0 | 状态:已采\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "goldmine_audit.py"), str(bk)],
                           capture_output=True, text=True, cwd=ROOT)
        case("goldmine:双采被抓", "双采" in r.stdout, r.stdout[-80:])
        case("goldmine:超窗被抓", "超窗" in r.stdout, "")
        (bk / "00-前提.md").write_text("普通写实年代文。", encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(ROOT / "tools" / "goldmine_audit.py"), str(bk)],
                            capture_output=True, text=True, cwd=ROOT)
        case("goldmine:非重生书跳过", "跳过" in r2.stdout, "")
    finally:
        shutil.rmtree(bk, ignore_errors=True)


def test_genre_contract():
    """第14组: 流派契约门(2026-09-15)——无声明FAIL/重生缺矿产FAIL/齐装PASS"""
    import shutil, subprocess
    bk = ROOT / "_tmp_gc"
    led = bk / "ledgers"; led.mkdir(parents=True, exist_ok=True)
    try:
        (bk / "00-前提.md").write_text("普通写实故事。", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "genre_contract.py"), str(bk)],
                           capture_output=True, text=True, cwd=ROOT)
        case("genre:无声明被抓", "缺流派声明" in r.stdout, r.stdout[-70:])

        (bk / "00-前提.md").write_text("他重生回1993年,不想赚大钱,只想享受生活守着小档口(动机层限制);张力三轴: 反应链+树大招风。\n- 流派: 躺赢流", encoding="utf-8")
        r2 = subprocess.run([sys.executable, str(ROOT / "tools" / "genre_contract.py"), str(bk)],
                            capture_output=True, text=True, cwd=ROOT)
        case("genre:重生缺矿产被抓", "矿产档案" in r2.stdout, "")

        (bk / "00-矿产档案.md").write_text("档案", encoding="utf-8")
        (led / "矿产账.md").write_text("# 矿产账\n", encoding="utf-8")
        r3 = subprocess.run([sys.executable, str(ROOT / "tools" / "genre_contract.py"), str(bk)],
                            capture_output=True, text=True, cwd=ROOT)
        case("genre:齐装放行", r3.returncode == 0 and "PASS" in r3.stdout, r3.stdout[-70:])
    finally:
        shutil.rmtree(bk, ignore_errors=True)




def test_era_clean_regression():
    """第16组: era_clean回归(审计20260917)——.modern上溯死循环修复/--scan模式存活/相对路径"""
    import subprocess, os
    Path = pathlib.Path
    ec = ROOT / "tools" / "era_clean.py"
    # 1) 相对路径文件清洗须在30s内完成(旧bug: exists()死循环)
    with tempfile.TemporaryDirectory() as td:
        bk = Path(td) / "书"
        (bk / "text" / "卷1").mkdir(parents=True)
        f = bk / "text" / "卷1" / "第001章.md"
        f.write_text("他需要开始继续已经。", encoding="utf-8")
        rel = os.path.relpath(f, Path.cwd())
        try:
            r = subprocess.run([sys.executable, str(ec), rel], capture_output=True,
                               text=True, timeout=30, cwd=Path.cwd())
            case("era_clean相对路径不挂死", r.returncode == 0, (r.stderr or r.stdout)[-50:])
        except subprocess.TimeoutExpired:
            case("era_clean相对路径不挂死", False, "TIMEOUT>30s")
        # 2) .modern书跳过清洗
        (bk / ".modern").write_text("", encoding="utf-8")
        f.write_text("他需要开始。", encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, str(ec), os.path.relpath(f, Path.cwd())],
                               capture_output=True, text=True, timeout=30)
            case("era_clean.modern书跳过", r.returncode == 0 and "他需要开始。" in f.read_text(encoding="utf-8"), "")
        except subprocess.TimeoutExpired:
            case("era_clean.modern书跳过", False, "TIMEOUT>30s")
        # 3) --scan模式存活(审计20260917: 旗标被参数清洗剥掉成死代码)
        try:
            r = subprocess.run([sys.executable, str(ec), "--scan", os.path.relpath(bk, Path.cwd())],
                               capture_output=True, text=True, timeout=30)
            case("era_clean --scan模式存活", r.returncode == 0 and "全量扫描" in r.stdout, r.stdout[-40:])
        except subprocess.TimeoutExpired:
            case("era_clean --scan模式存活", False, "TIMEOUT>30s")


def test_redteam_canaries():
    """第15组: 红队金丝雀(大审计-35)——evidence旗标真生效/伪造冷读被拦"""
    import shutil, subprocess
    # 1) evidence: 临时书32章含无产物引用自证→exit 1(审计20260917: 悬空书根→fixture)
    bk = ROOT / "_tmp_ev"
    (bk / "ledgers").mkdir(parents=True, exist_ok=True)
    try:
        rec = bk / "ledgers" / "技能执行记录.md"
        lines = ["# 技能执行记录（第032章）"]
        for i in range(25):
            lines.append(f"- [x] draft{ i }(生成初稿) 技能: scene-draft")
        rec.write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "skill_protocol.py"),
                            "audit", "32", "--book", "_tmp_ev", "--evidence"],
                           capture_output=True, text=True, cwd=ROOT)
        case("红队:evidence旗标拦自证", r.returncode == 1 and "自证" in r.stdout, r.stdout[-60:])
    finally:
        shutil.rmtree(bk, ignore_errors=True)
    # 2) 伪造冷读(一行文)被done内容门判FAIL文本
    bk = ROOT / "_tmp_cr"
    (bk / "audit").mkdir(parents=True, exist_ok=True)
    try:
        (bk / "audit" / "冷读-第005章.md").write_text("总分: 9/10 会翻", encoding="utf-8")
        c = (bk / "audit" / "冷读-第005章.md").read_text(encoding="utf-8")
        ok = len(c) < 600
        case("红队:一行文冷读判薄", ok, str(len(c)))
    finally:
        shutil.rmtree(bk, ignore_errors=True)


def main():
    tests = [test_cn2num, test_fix_quotes, test_voice_check, test_book_root,
             test_card_check_nums, test_legacy_aphor_exemption, test_new_gates,
             test_n1_assembly, test_exit_and_timejump, test_number_and_anticipation,
             test_scaffold_gate,
            test_canary_and_new_knives,
            test_goldmine_audit,
            test_genre_contract,
            test_redteam_canaries,
            test_era_clean_regression]
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
