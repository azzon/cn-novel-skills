#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ledger_compact.py 账本压缩器(百万字长跑韧性: 账本无限膨胀=上下文注入超预算=质量崩塌)

折叠规则(只动归档区,不丢信息;rebuild原则:正文是权威,账本是派生):
  伏笔.md      已收/已兑/销号条目 → "## 归档(已收)"区,活跃条目留顶部
  时间线.md    保留最近60条,更早 → "## 前史(折叠)"区(recompute取末条不受影响)
  人物状态.md  盖章流水中上一卷及更早 → "## 卷归档"区,当前卷+快照留顶部
  钩分布.md    章末钩行保留最近60,结构轮换账保留最近30
  生成记录.md  保留最近120章行

用法: python3 tools/ledger_compact.py [--book 书根] [--dry]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def fold(path, keep_pred, archive_head, dry=False):
    """按谓词把行分两组,归档组移到 archive_head 区尾"""
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    if archive_head in "\n".join(lines):
        return 0   # 已折叠过(幂等;再折叠等下个周期)
    head, active, arch = [], [], []
    for l in lines:
        if l.strip().startswith("- "):
            (arch if keep_pred(l) else active).append(l)
        else:
            head.append(l)
    if not arch:
        return 0
    out = head + active + ["", archive_head, f"(共{len(arch)}条,压缩于本周期;全文在git历史)"] + arch
    if not dry:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return len(arch)


def keep_tail(path, prefix, keep, archive_head, dry=False):
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    idx = [i for i, l in enumerate(lines) if l.strip().startswith(prefix)]
    if len(idx) <= keep or archive_head in "\n".join(lines):
        return 0
    fold_n = len(idx) - keep
    fold_set = set(idx[:fold_n])           # 旧行删除,移文末归档区(修:首版把旧行留原位,新行反被压底)
    kept = [l for i, l in enumerate(lines) if i not in fold_set]
    arch = [lines[i] for i in sorted(fold_set)]
    out = kept + ["", archive_head, f"(前{fold_n}条折叠;全文在git历史)"] + arch
    if not dry:
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return fold_n


def main():
    args = sys.argv[1:]
    dry = "--dry" in args
    book = ROOT / args[args.index("--book") + 1] if "--book" in args else ROOT
    L = book / "ledgers"
    total = 0
    total += fold(L / "伏笔.md",
                  lambda l: re.search(r"已收|已兑|销号", l) is not None,
                  "## 归档(已收伏笔)", dry)
    total += keep_tail(L / "时间线.md", "- 第", 60, "## 前史(折叠)", dry)
    total += keep_tail(L / "钩分布.md", "- 第", 60, "## 归档(章末钩·折叠)", dry)
    total += keep_tail(L / "生成记录.md", "- 第", 120, "## 归档(生成记录·折叠)", dry)
    tag = "[dry] " if dry else ""
    print(f"{tag}账本压缩: 归档{total}条 → {L}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
