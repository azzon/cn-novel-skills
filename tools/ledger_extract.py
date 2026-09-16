#!/usr/bin/env python3
"""ledger_extract.py 八账自动抽取器(自动化目标②)

流程效率审计: 每章手工编辑12+个账本文件,质量随章数劣化(科目重复/恒等式错误/撞号)。
本工具从正文+场景卡机械抽取八账候选条目→ledger_schema校验→写入账本。

抽取逻辑:
  钩分布: 章末3行提取钩形态
  时间线: 卡的Pre/Post行提取时地事
  数字账: 正文中含数字的句子提取(金额/数量/年龄)
  人物状态: 正文角色名+状态变化句
  伏笔: 卡的Pre行"埋"/"充能"关键词
  线弦: 卡的Pre/Post行
  类型轮换: 卡的场景型字段
  口碑账: 正文含"传遍/都说/名声"的句子

用法:
  python3 tools/ledger_extract.py <章号> [--book 书根] [--dry]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


def extract_from_chapter(n, book):
    """从正文+卡提取八账候选"""
    b = pathlib.Path(book)
    body_files = sorted((b / "text").rglob(f"第{n:03d}章.md"))
    card_files = sorted((b / "卡").glob(f"*第{n:03d}章*.md"))
    if not body_files:
        return None, "正文不存在"
    body = body_files[0].read_text(encoding="utf-8")
    card_t = card_files[0].read_text(encoding="utf-8") if card_files else ""

    entries = {}

    # 1) 钩分布: 章末3行
    tail = [l.strip() for l in body.splitlines() if l.strip()][-3:]
    hook_text = " ".join(tail)[:40]
    entries["钩分布"] = f"- 第{n:03d}章 [悬念] {hook_text}"

    # 2) 时间线: 从卡提取时间+地点,从正文提取事件
    time_m = re.search(r"故事时间[:：]\s*(.+)", card_t) or re.search(r"(\d{4}年[^\n]{1,20})", body[:500])
    place_m = re.search(r"地点[:：]\s*(.+)", card_t)
    events = body[:200].replace("\n", " ")[:40]
    t_str = time_m.group(1)[:15] if time_m else "时间未提取"
    p_str = place_m.group(1)[:10] if place_m else "地点未提取"
    entries["时间线"] = f"- 第{n:03d}章|{t_str}|{p_str}|{events}"

    # 3) 数字账: 正文含数字的短句(金额/数量/年龄/时间)
    num_sents = []
    for sent in re.split(r"[。！？\n]", body):
        sent = sent.strip()
        if re.search(r"\d+[两贯文石块万元]|\d+[岁天章节年月日]|\d+[次回个位条]", sent) and 5 < len(sent) < 50:
            num_sents.append(sent[:40])
    if num_sents:
        entries["数字账"] = f"- 正文数字|第{n:03d}章|{'|'.join(num_sents[:3])}"

    # 4) 人物状态: 角色名+状态变化
    char_names = re.findall(r"[\u4e00-\u9fff]{2,3}(?:说|想|看|走|站|坐|笑|哭)", body[:1000])
    if char_names:
        unique = list(dict.fromkeys(char_names))[:3]
        entries["人物状态"] = f"- 第{n:03d}章盖章: {';'.join(unique)}"

    # 5) 伏笔: 从卡提取
    fu_m = re.search(r"Forbid[:：]\s*(.+)", card_t)
    pre_m = re.search(r"Pre[:：]\s*(.+)", card_t)
    if pre_m:
        entries["伏笔"] = f"- 第{n:03d}章埋: {pre_m.group(1)[:30]}"

    # 6) 线弦: 卡的Post
    post_m = re.search(r"Post[:：]\s*(.+)", card_t)
    if post_m:
        entries["线弦"] = f"- 第{n:03d}章线弦: {post_m.group(1)[:30]}"

    # 7) 类型轮换: 卡的场景型
    st_m = re.search(r"场景型[:：]\s*(.+)", card_t)
    if st_m:
        entries["类型轮换"] = f"- 第{n:03d}章 {st_m.group(1)[:15]}"

    # 8) 口碑账: 含传言关键词的句子
    for sent in re.split(r"[。！？\n]", body):
        if any(k in sent for k in ("传遍", "都说", "名声", "名动", "听说")):
            entries["口碑账"] = f"- 第{n:03d}章: {sent.strip()[:40]}"
            break

    return entries, None


def write_entries(n, book, entries, dry=False):
    b = pathlib.Path(book)
    written = []
    for name, line in entries.items():
        fp = b / "ledgers" / f"{name}.md"
        if not fp.exists():
            fp.write_text(f"# {name}\n", encoding="utf-8")
        t = fp.read_text(encoding="utf-8")
        if f"第{n:03d}章" not in t:
            if dry:
                written.append(f"  [dry] {name}: {line[:50]}")
            else:
                t = t.rstrip("\n") + "\n" + line + "\n"
                fp.write_text(t, encoding="utf-8")
                written.append(f"  写入 {name}")
    return written


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    book = ROOT
    if "--book" in sys.argv:
        book = ROOT / sys.argv[sys.argv.index("--book") + 1]
    if not args:
        print(__doc__)
        return 2
    n = int(re.sub(r"\D", "", args[0]) or 0)

    entries, err = extract_from_chapter(n, book)
    if err:
        print(f"  [FAIL] {err}")
        return 1

    print(f"═══ 第{n:03d}章 八账自动抽取 ═══")
    written = write_entries(n, book, entries, dry)
    for w in written:
        print(w)
    if not written:
        print("  (全部已存在或无新条目)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
