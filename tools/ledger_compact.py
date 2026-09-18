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


ARCHIVE_MAX = 500  # 缺陷18: 归档区上限

def fold(path, keep_pred, archive_head, dry=False):
    """按谓词把行分两组,归档组移到 archive_head 区尾(归档区置于活跃区前,账本读取协议=取尾取最新)"""
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    full = "\n".join(lines)
    if archive_head in full:
        # 二次折叠(W6修复: 旧版引用未定义arch_zone_start=死代码): 只对活跃区折,旧归档块原样保留
        head_i = next(i for i, l in enumerate(lines) if archive_head in l)
        zone_end = head_i
        while zone_end < len(lines) and lines[zone_end].strip():
            zone_end += 1
        old_block = lines[head_i:zone_end]
        active = lines[zone_end:]
        na_idx = [i for i, l in enumerate(active) if keep_pred(l)]
        if not na_idx:
            return 0
        na_set = set(na_idx)
        kept = [l for i, l in enumerate(active) if i not in na_set]
        new_arch = [active[i] for i in na_idx]
        # ARCHIVE_MAX: 归档区超上限时丢最旧(全文在git历史——截断前确保已commit未提交改动)
        old_arch_rows = [l for l in old_block if l.strip().startswith("- ")]
        total_arch = old_arch_rows + new_arch
        if len(total_arch) > ARCHIVE_MAX:
            total_arch = total_arch[-ARCHIVE_MAX:]
        out = lines[:head_i] + [archive_head, f"(共{len(total_arch)}条,滚动归档;全文在git历史——截断前确保已commit未提交改动)"] + total_arch + [""] + kept
        if not dry:
            _before = path.read_text(encoding="utf-8")
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
            if not _tail_check(path, out):
                path.write_text(_before, encoding="utf-8")
                print(f"  [自检失败已回滚] {path.name}: 最大章不在尾部,折叠中止")
                return 0
        return len(new_arch)
    head, active, arch = [], [], []
    for l in lines:
        if l.strip().startswith("- "):
            (arch if keep_pred(l) else active).append(l)
        else:
            head.append(l)
    if not arch:
        return 0
    if len(arch) > ARCHIVE_MAX:
        arch = arch[-ARCHIVE_MAX:]
    out = head + ["", archive_head, f"(共{len(arch)}条,压缩于本周期;全文在git历史——截断前确保已commit未提交改动)"] + arch + [""] + active
    if not dry:
        _before = path.read_text(encoding="utf-8")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        if not _tail_check(path, out):
            path.write_text(_before, encoding="utf-8")
            print(f"  [自检失败已回滚] {path.name}: 最大章在归档区,折叠中止——人工处理")
            return 0
    return len(arch)


def _tail_check(path, out, window=60):
    """写后自检: 全文最大章号必须仍在尾部window行内(防活性反转)"""
    import re as _re
    _allch = [int(x) for x in _re.findall(r"第0?(\d{1,3})章", "\n".join(out))]
    _tailch = [int(x) for x in _re.findall(r"第0?(\d{1,3})章", "\n".join(out[-window:]))]
    return not (_allch and _tailch and max(_allch) not in _tailch)

def keep_tail(path, prefix, keep, archive_head, dry=False):
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    full = "\n".join(lines)
    idx = [i for i, l in enumerate(lines) if l.strip().startswith(prefix)]
    if len(idx) <= keep:
        return 0
    if archive_head in full:
        # 二次keep_tail(W6修复: 旧版after含旧归档行→重折旧行=灾难性条目×2): 活跃区=归档块(到第一个空行)之后
        head_i = next(i for i, l in enumerate(lines) if archive_head in l)
        zone_end = head_i
        while zone_end < len(lines) and lines[zone_end].strip():
            zone_end += 1
        old_block = lines[head_i:zone_end]
        active = lines[zone_end:]
        a_idx = [i for i, l in enumerate(active) if l.strip().startswith(prefix)]
        if len(a_idx) <= keep:
            return 0
        fold_n = len(a_idx) - keep
        fold_set = set(a_idx[:fold_n])
        new_arch = [active[i] for i in sorted(fold_set)]
        kept = [l for i, l in enumerate(active) if i not in fold_set]
        old_rows = [l for l in old_block if l.strip().startswith(prefix)]
        total_arch = old_rows + new_arch
        if len(total_arch) > ARCHIVE_MAX:
            total_arch = total_arch[-ARCHIVE_MAX:]
        out = lines[:head_i] + [archive_head, f"(共{len(total_arch)}条,滚动归档;全文在git历史——截断前确保已commit未提交改动)"] + total_arch + [""] + kept
        if not dry:
            _before = path.read_text(encoding="utf-8")
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
            if not _tail_check(path, out):
                path.write_text(_before, encoding="utf-8")
                print(f"  [自检失败已回滚] {path.name}: 最大章不在尾部,折叠中止")
                return 0
        return fold_n
    fold_n = len(idx) - keep
    fold_set = set(idx[:fold_n])
    kept = [l for i, l in enumerate(lines) if i not in fold_set]
    arch = [lines[i] for i in sorted(fold_set)]
    out = ["", archive_head, f"(前{fold_n}条折叠;全文在git历史——截断前确保已commit未提交改动)"] + arch + [""] + kept  # P1-035: 归档区在前,活跃区在后
    if not dry:
        _before = path.read_text(encoding="utf-8")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        if not _tail_check(path, out):
            path.write_text(_before, encoding="utf-8")
            print(f"  [自检失败已回滚] {path.name}: 最大章在归档区,折叠中止——人工处理")
            return 0
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
    # 红队20260919长跑修复: 补8账全覆盖(此前人物状态/梗/数字账/口碑账/线弦零压缩→900章裸涨)
    total += keep_tail(L / "人物状态.md", "- 第", 60, "## 归档(人物状态·折叠)", dry)
    total += keep_tail(L / "梗.md", "- ", 80, "## 归档(梗·折叠)", dry)
    total += keep_tail(L / "时间线.md", "- 第", 60, "## 前史(折叠)", dry)  # 幂等:已折则查活跃区
    total += keep_tail(L / "线弦.md", "- 第", 40, "## 归档(线弦·折叠)", dry)
    total += keep_tail(L / "类型轮换.md", "- 第", 60, "## 归档(类型轮换·折叠)", dry)
    # W6验证:原前缀"# 技能执行记录"只命中标题行=永久no-op,改"- "
    total += keep_tail(L / "技能执行记录.md", "- ", 30, "## 归档(技能记录·折叠)", dry)
    # 数字账/口碑账: 结构化行(非"第N章"前缀),按行数保尾
    for _fname, _keep_n in [("数字账.md", 200), ("口碑账.md", 100)]:
        _fp = L / _fname
        if _fp.exists():
            _lines = _fp.read_text(encoding="utf-8").splitlines()
            _data = [l for l in _lines if l.strip().startswith("- ")]
            if len(_data) > _keep_n:
                _fold_n = len(_data) - _keep_n
                _fold = _data[:_fold_n]
                _keep = _data[_fold_n:]
                _head = [l for l in _lines if not l.strip().startswith("- ") and l.strip()]
                _out = _head + ["", f"## 归档({_fname}·折叠)", f"(前{_fold_n}条;全文在git历史——截断前确保已commit未提交改动)"] + _fold + [""] + _keep
                if not dry:
                    _fp.write_text("\n".join(_out) + "\n", encoding="utf-8")
                total += _fold_n
    tag = "[dry] " if dry else ""
    print(f"{tag}账本压缩: 归档{total}条 → {L}")
    return 0


if __name__ == "__main__":
    sys.exit(main())