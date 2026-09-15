#!/usr/bin/env python3
"""ledger_schema.py 账本盖章格式验证器(大审计-35 backlog P1: "- 第N章 空话"式token盖章可骗done)

原理: done的八账盖章此前只查"该账有列表行含章号"——一行废话即过(红队流水线实测)。
本工具按账定义最小schema,盖章行必须格式合规才算数:
  钩分布    - 第NNN章 [形态] ≥4字说明     (形态∈对话切|悬念|叙述收|事件|反转…)
  时间线    - 第NNN章|时间|地点|事件       (4段管道,时间含"年")
  数字账    - 科目|限定|值|第NNN章         (值可解析:数字/中文数字/正负/小数)
  人物状态  - 第NNN章盖章: ≥6字           ("空话"/"待记"不算)
  伏笔      - [F|A-N] 描述 |埋:…|状态:…   (id+至少两段)
  梗/线弦/类型轮换/口碑账 - 列表行含第NNN章且≥8字
豁免行: 含"待记/TODO/占位"直接FAIL(红队: 占位不是盖章)。

用法(done内嵌):
  from ledger_schema import chapter_stamps_ok
  ok, notes = chapter_stamps_ok(book, n)   # notes为不合格账名清单
"""
import re, sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from card_check import extract_vals   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

PLACEHOLDER = re.compile(r"待记|TODO|占位|待补|空话")


def _lines_with(ledger_path, n):
    toks = (f"第{n}章", f"第{n:03d}章")
    out = []
    if not ledger_path.exists():
        return out
    for line in ledger_path.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        if s.startswith("- ") and any(t in s for t in toks):
            out.append(s[2:])
    return out


def _clean_len(s):
    return len(re.sub(r"[\s\-|（）()：:，,。/第0-9章]", "", s))


def chapter_stamps_ok(book, n):
    """返回 (合格账集, 不合格明细[(账, 原因)])"""
    led = pathlib.Path(book) / "ledgers"
    bad = []
    good = set()

    def rule(name, fn):
        rows = _lines_with(led / f"{name}.md", n)
        if not rows:
            return   # 缺账由done原有的"未盖章"报,不重复
        errs = fn(rows)
        if errs:
            bad.append((name, errs))
        else:
            good.add(name)

    rule("钩分布", lambda rs: [r for r in rs if not re.match(rf"第0?0*{n}章\s*\[[^\]]{{2,6}}\]\s*\S", r)][:1]
         or [r for r in rs if PLACEHOLDER.search(r)][:1] or [])
    rule("时间线", lambda rs: [r for r in rs if not (r.count("|") >= 3 and "年" in r.split("|")[1])][:1])
    rule("数字账", lambda rs: [r for r in rs
                               if not (("(" in r and "=" in r)   # 恒等式行: 目标(说明) = A ± B
                                       or (r.count("|") >= 3 and extract_vals(r.split("|")[2])))][:1])
    rule("人物状态", lambda rs: [r for r in rs if _clean_len(r) < 6 or PLACEHOLDER.search(r)][:1])
    rule("伏笔", lambda rs: [r for r in rs if not re.match(r"\[?[FA]-\d+\]?", r)][:1])
    for plain in ("梗", "线弦", "口碑账"):
        rule(plain, lambda rs: [r for r in rs if _clean_len(r) < 8 or PLACEHOLDER.search(r)][:1])
    rule("类型轮换", lambda rs: [r for r in rs
                                  if not re.match(rf"第0?0*{n}章\s*\S{{1,6}}[·・—-]\S{{1,8}}$", r)
                                  or PLACEHOLDER.search(r)][:1])   # 账本历史格式"类型·词"
    return good, bad


if __name__ == "__main__":
    _book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    _n = int(re.sub(r"\D", "", sys.argv[2]) or 0) if len(sys.argv) > 2 else 0
    if not _n:
        print("用法: ledger_schema.py <书根> <章号>")
        sys.exit(2)
    g, b = chapter_stamps_ok(_book, _n)
    for name, errs in b:
        for e in errs:
            print(f"  [FAIL] {name}: 盖章行不合规——{e[:60]}")
    print(f"账本盖章格式: {'FAIL' if b else 'PASS'}({len(g)}账合规)")
    sys.exit(1 if b else 0)
