#!/usr/bin/env python3
"""legacy_cards.py 骨架卡批量回填器(1993全量审计产物: 23张骨架卡以成稿身份入库)

原理: 骨架卡欠账的根因是"卡生成后没填就提交了正文"。与其逐张手补23张,
不如把账本里已验证的事实(钩分布/时间线/数字账/章摘要)自动回填成"补录卡":
  - 钩:      来自 ledgers/钩分布.md (真实数据)
  - 数字表:  来自 ledgers/数字账.md 该章流水,且逐值验证在正文存在(zh变体)
  - 承接/时间线: 来自 ledgers/时间线.md
  - 字数带:  按正文实测对齐(补录卡如实记录成稿口径,不假装是事前规划)
  - 开场型:  正文首段启发式(对话直入/动作直入/判断句),标注"补录推断"
  - 其余判断字段(戏剧问题/价值换极/beats等): "补录待校(修订期人工升级)"
    ——不造假填空,留诚实锚点;修订期该章动工时按scene-card技能升级为正式卡
卡保留 generated-by 指纹(audit-cards要求),清空全部占位标记(（填）/（四选一/…）)。

用法:
  python3 tools/legacy_cards.py <书根> [--dry]     # 回填书内全部骨架卡
"""
import re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card_check import find_card, extract_vals   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

PLACEHOLDER_MARKS = ("（填）", "（四选一", "（本章全部数字事实")


def zh_variants(v):
    """数字的正文存在形态: 阿拉伯数字+中文口语(粗粒度,够验数字表用)"""
    forms = {str(int(v)) if v == int(v) else str(v)}
    try:
        from pipeline import zh_num_variants
        forms |= set(zh_num_variants(str(int(v)) if v == int(v) else str(v)))
    except Exception:
        pass
    return forms


def in_body(v, body):
    return any(f in body for f in zh_variants(v))


def first_scene_type(text):
    """正文首段启发式开场型"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    body = [l for l in lines if not l.startswith("#")][0] if len(lines) > 1 else ""
    if body.startswith("“") or body.startswith('"'):
        return "对话直入(补录推断)"
    if re.match(r"^(第?[一二三]?[天早晚]|那年|此[时刻]|回到)", body):
        return "判断句(补录推断)"
    return "动作直入(补录推断)"


def ledger_row(ledger, n):
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if re.search(rf"第0?{n}章", line) and line.strip().startswith("- "):
            return line.strip()
    return None


def fill_card(card, book):
    n = int(re.search(r"第(\d+)章", card.name).group(1))
    vol_m = re.search(r"卷(\d+)", card.name)
    vol = int(vol_m.group(1)) if vol_m else 1
    body_p = book / "text" / f"卷{vol}" / f"第{n:03d}章.md"
    if not body_p.exists():
        return None, f"正文不存在 {body_p.name}"
    body = body_p.read_text(encoding="utf-8")
    cjk = len(re.sub(r"[^\u4e00-\u9fff]", "", body))

    led = book / "ledgers"
    hook = ledger_row(led / "钩分布.md", n) or ""
    tl = ledger_row(led / "时间线.md", n) or ""
    hm = re.search(r"\[(.+?)\]\s*(.+)$", hook)
    hook_val = f"{hm.group(1)}·{hm.group(2)[:30]}" if hm else "补录待校"
    tlm = re.split(r"\|", tl, 3)
    timeline = f"{tlm[1]}|{tlm[2]}" if len(tlm) >= 4 else "补录待校"

    # 数字账: 该章流水,逐值验证在正文
    num_items = []
    if (led / "数字账.md").exists():
        for line in (led / "数字账.md").read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s.startswith("- ") or f"第{n:03d}章" not in s:
                continue
            parts = [x.strip() for x in s[2:].split("|")]
            if len(parts) < 4:
                continue   # 结构化取值: 科目|限定|值|章——只信第3列(1993审计: 整行extract会把章号007当账值)
            vals = extract_vals(parts[2])
            good = sorted({v for v in vals if v is not None and in_body(v, body)})
            if good:
                num_items.append(parts[0] + "/".join(str(int(v)) if v == int(v) else str(v) for v in good))
    num_table = "/".join(num_items) if num_items else "无(正文无账面数字)"

    summary = ""
    sb_dir = book / "圣经"
    if sb_dir.is_dir():
        for p2 in sorted(sb_dir.glob("*章摘要.md")):
            for line in p2.read_text(encoding="utf-8").splitlines():
                if re.search(rf"^- 第0?{n}章", line.strip()):
                    summary = line.strip()
                    break

    lines = card.read_text(encoding="utf-8-sig").splitlines()
    out = []
    for l in lines:
        if l.strip().startswith("<!-- generated-by:"):
            if "补录卡" not in l:
                l = l.replace("-->", "补录卡:legacy_cards自动回填2026-09-14,判断字段待修订期人工升级-->")
            out.append(l)
            continue
        m = re.match(r"(- \*\*(.+?)\*\*): ", l)
        if not m:
            out.append(l)
            continue
        field = m.group(2)
        filled = None
        if field == "开场型":
            filled = first_scene_type(body)
        elif field == "钩":
            filled = hook_val
        elif field == "数字表":
            filled = num_table
        elif field == "承接":
            filled = (f"上章末态见时间线;本章: {timeline}") if timeline != "补录待校" else "补录待校"
        elif field == "时间线" or field == "章级":
            filled = timeline if field == "时间线" else l.split(": ", 1)[-1]
        elif field == "beats":
            filled = f"实测口径(补录): 全章{cjk}字|字数带={max(0, cjk - 200)}-{cjk + 400}"
        elif field == "戏剧问题" and summary:
            filled = f"补录(自章摘要): {summary[:46]}"
        out.append(f"- **{field}**: {filled}" if filled else l)
    t = "\n".join(out)
    # 残余占位一律降为诚实标记
    for mk in PLACEHOLDER_MARKS:
        t = t.replace(mk, "（补录待校）")
    t = re.sub(r"（补录待校）[^）]*）", "（补录待校）", t)   # 嵌套括号收敛
    card.write_text(t, encoding="utf-8")
    return n, f"数字表{len(num_items)}项 钩[{hook_val[:14]}]"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    cards = sorted((book / "卡").glob("*.md"))
    filled, skipped = 0, 0
    for c in cards:
        txt = c.read_text(encoding="utf-8-sig")
        if not any(mk in txt for mk in PLACEHOLDER_MARKS):
            continue
        if dry:
            print(f"[dry] {c.name}")
            continue
        n, note = fill_card(c, book)
        if n is None:
            print(f"  [SKIP] {c.name}: {note}")
            skipped += 1
        else:
            print(f"  [FILL] {c.name}: {note}")
            filled += 1
    print(f"回填{filled}张 / 跳过{skipped}张 / 共{len(cards)}卡")
    return 0


if __name__ == "__main__":
    sys.exit(main())
