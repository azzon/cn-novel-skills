#!/usr/bin/env python3
"""genre_contract.py 流派契约核验器(genre-playbook机器门,2026-09-15)

原理: 00-前提.md 必须声明流派(- 流派: <名>),且按流派装配配套产物。
本工具在立项(book_design phase_0硬门)与system_readiness时核验:
  1) 声明存在(缺=FAIL——流派引擎知识必须构思期输入,autopilot要求)
  2) 按流派的配套产物存在性与关键声明(重生系→矿产档案/矿产账;躺赢流→动机限制+张力三轴声明;博弈流→能力层限制声明;经营流→数字账;系统流→系统规则声明...)
  3) 混搭声明合法性(主流派必须命中档案库)

用法: python3 tools/genre_contract.py [书根]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

KNOWN = ("躺赢流", "博弈流", "无敌流", "苟道流", "经营流", "系统流", "杀伐流",
         "扮猪吃虎", "轻喜剧", "正剧年代", "悬疑单元", "争霸流", "无限流")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    premise = None
    for c in ("00-前提.md", "story/00-前提.md"):
        f = book / c
        if f.exists():
            premise = f.read_text(encoding="utf-8")
            break
    issues, warns = [], []

    if premise is None:
        print("  [WARN] 无00-前提.md(未立项或主书区)——流派契约跳过")
        return 0

    m = re.search(r"流派[:：]\s*([^\s//(（]+)", premise)
    parked = bool(re.search(r"待重启|清稿|搁置|封存", premise))   # 停摆书降级为WARN(红队: 门要诚实但不挡无关工作)
    bucket = warns if parked else issues
    if not m:
        bucket.append("00-前提.md缺流派声明(- 流派: <名>)——genre-playbook硬前置: 流派引擎必须构思期选定并声明,不许写完后补")
        genre = None
    else:
        genre = m.group(1).strip()
        matched = [k for k in KNOWN if k in genre]
        main_g = matched[0] if matched else None
        if main_g is None:
            bucket.append(f"流派「{genre}」不在genre-playbook档案库(已知: {'/'.join(KNOWN)})——先补档案再立项,或改用已收录流派")

    is_rebirth = bool(re.search(r"重生|穿越|先知|未来记忆|上一世|前世", premise))

    # 重生/穿越系(不论流派): 矿产三件套
    if is_rebirth:
        if not (book / "00-矿产档案.md").exists():
            bucket.append("重生/穿越书缺00-矿产档案.md(era-goldmine硬前置)")
        if not (book / "ledgers" / "矿产账.md").exists():
            bucket.append("重生/穿越书缺ledgers/矿产账.md(第九账)")
        if not re.search(r"限制|不想赚|动机|记忆颗粒|盲区|代价", premise):
            bucket.append("重生书缺限制层声明(博弈流=能力层限制/躺赢流=动机层'不想赚')——无限先知=无聊死")

    # 流派专属
    if genre and "躺赢流" in genre:
        if not re.search(r"不想赚|享受生活|三轴|反应链|树大招风|无心", premise):
            warns.append("躺赢流: 前提未见动机层限制/张力三轴声明——按genre-playbook模式B补入(张力三轴≥2)")
    if genre and "博弈流" in genre and is_rebirth:
        if not re.search(r"限制", premise):
            warns.append("博弈流: 能力层限制器声明建议显式写入")
    if genre and "经营流" in genre:
        if not (book / "ledgers" / "数字账.md").exists():
            bucket.append("经营流缺ledgers/数字账.md——资产表复利是经营流主引擎,数字不动=死(1993卷一实证)")
    if genre and "系统流" in genre:
        if not re.search(r"系统规则|系统面板|任务|积分|商城", premise):
            warns.append("系统流: 前提未见系统规则/任务/积分类声明——系统规则有限性须入设计层")
        if re.search(r"寿元|寿命|消耗生命", premise) and not (book / "ledgers" / "寿元账.md").exists():
            issues.append("系统流以寿元为代价但缺ledgers/寿元账.md——代价货币必须入账(数字账联动)")
    if genre and "杀伐流" in genre:
        if not re.search(r"底线|不滥|原则", premise):
            warns.append("杀伐流: 底线人设(狠而不滥)未声明——滥杀失共情是头号死因")
    if genre and "苟道流" in genre:
        if not re.search(r"露锋芒|作死对照|避险|苦一爽一|稳", premise):
            warns.append("苟道流: 节奏三件套未声明(露锋芒排期/作死对照组/苦爽蓄压比)——苟成懦夫或从不爆发是双头死因(genre-playbook)")
    if genre and "系统流" in genre and (b := book) is not None:
        pass

    for x in issues:
        print(f"  [FAIL] {x}")
    for w in warns:
        print(f"  [WARN] {w}")
    print(f"流派契约: {'FAIL' if issues else 'PASS'}(流派={genre or '未声明'}{'/重生系' if is_rebirth else ''})")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
