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
    full = "\n".join(lines)
    if archive_head in full:
        # 红队20260919长跑修复: 归档区已存在≠永久免疫——活跃区再次堆积>阈值时允许二次折叠
        # (旧逻辑:归档头存在即return 0,900章时账本裸涨830章)
        arch_zone_start = full.find(archive_head)
        arch_zone_end = full.find("\n\n", arch_zone_start)
        # 统计归档区之后的活跃行数
        after_arch = full[arch_zone_end:] if arch_zone_end > 0 else ""
        active_lines = [l for l in after_arch.split("\n") if l.strip().startswith("- ")]
        if len(active_lines) < 40:   # 活跃区<40行=健康,不折
            return 0
        # 二次折叠: 把归档区后的活跃区中可折叠行追加进归档区
        head = lines[:arch_zone_start.count("\n") + 1]
        existing_arch = []
        active = []
        in_arch = False
        for l in lines:
            if archive_head in l:
                in_arch = True
                continue
            if in_arch and l.strip() == "":
                in_arch = False
                continue
            if in_arch:
                existing_arch.append(l)
            elif l.strip().startswith("- "):
                active.append(l)
            else:
                head.append(l)
        # 对活跃区应用谓词,可折的追加到归档区
        new_arch = [l for l in active if keep_pred(l)]
        active = [l for l in active if not keep_pred(l)]
        if not new_arch:
            return 0
        arch = existing_arch + new_arch
        # 重写
        out = head + ["", archive_head, f"(累计{len(arch)}条,二次折叠于本周期;全文在git历史)"] + arch + [""] + active
        if not dry:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return len(new_arch)
    head, active, arch = [], [], []
    for l in lines:
        if l.strip().startswith("- "):
            (arch if keep_pred(l) else active).append(l)
        else:
            head.append(l)
    if not arch:
        return 0
    # 红队20260915: 归档区必须置于活跃区之前——账本读取协议是"取尾部=取最新",
    # 归档在尾部会让近窗注入喂到旧账(story_time从090跳回030实测)
    out = head + ["", archive_head, f"(共{len(arch)}条,压缩于本周期;全文在git历史)"] + arch + [""] + active
    if not dry:
        _before = path.read_text(encoding="utf-8")
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        # 写后自检: 全文最大章号必须仍在尾部60行内(防活性反转),失败即回滚
        import re as _re
        _allch = [int(x) for x in _re.findall(r"第0?(\d{1,3})章", path.read_text(encoding="utf-8"))]
        _tailch = [int(x) for x in _re.findall(r"第0?(\d{1,3})章", "\n".join(out[-60:]))]
        if _allch and _tailch and max(_allch) not in _tailch:
            path.write_text(_before, encoding="utf-8")
            print(f"  [自检失败已回滚] {path.name}: 最大章在归档区,折叠中止——人工处理")
            return 0
    return len(arch)


def keep_tail(path, prefix, keep, archive_head, dry=False):
    if not path.exists():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    full = "\n".join(lines)
    idx = [i for i, l in enumerate(lines) if l.strip().startswith(prefix)]
    if len(idx) <= keep:
        return 0
    # 红队20260919长跑修复: 归档头存在时,检查归档区之后的行是否超keep
    if archive_head in full:
        arch_pos = full.find(archive_head)
        after = full[arch_pos:]
        after_idx = [i for i, l in enumerate(after.split("\n")) if l.strip().startswith(prefix)]
        if len(after_idx) <= keep:
            return 0
        # 二次keep_tail: 对归档区之后的行再执行
        lines_after = after.split("\n")
        fold_n = len(after_idx) - keep
        fold_set = set(after_idx[:fold_n])
        kept = [l for i, l in enumerate(lines_after) if i not in fold_set]
        arch = [lines_after[i] for i in sorted(fold_set)]
        # 合并旧归档+新归档
        old_arch_start = full.find(archive_head)
        old_arch_end = full.find("\n\n", old_arch_start)
        old_arch_block = full[old_arch_start:old_arch_end] if old_arch_end > 0 else full[old_arch_start:]
        pre = full[:old_arch_start].split("\n")
        out = pre + ["", archive_head, f"(累计折叠;全文在git历史)"] + old_arch_block.split("\n")[2:] + arch + kept
        if not dry:
            path.write_text("\n".join(out) + "\n", encoding="utf-8")
        return fold_n
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
    # 红队20260919长跑修复: 补8账全覆盖(此前人物状态/梗/数字账/口碑账/线弦零压缩→900章裸涨)
    total += keep_tail(L / "人物状态.md", "- 第", 60, "## 归档(人物状态·折叠)", dry)
    total += keep_tail(L / "梗.md", "- ", 80, "## 归档(梗·折叠)", dry)
    total += keep_tail(L / "时间线.md", "- 第", 60, "## 前史(折叠)", dry)  # 幂等:已折则查活跃区
    total += keep_tail(L / "线弦.md", "- 第", 40, "## 归档(线弦·折叠)", dry)
    total += keep_tail(L / "类型轮换.md", "- 第", 60, "## 归档(类型轮换·折叠)", dry)
    total += keep_tail(L / "技能执行记录.md", "# 技能执行记录", 30, "## 归档(技能记录·折叠)", dry)
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
                _out = _head + ["", f"## 归档({_fname}·折叠)", f"(前{_fold_n}条;全文在git历史)"] + _fold + [""] + _keep
                if not dry:
                    _fp.write_text("\n".join(_out) + "\n", encoding="utf-8")
                total += _fold_n
    tag = "[dry] " if dry else ""
    print(f"{tag}账本压缩: 归档{total}条 → {L}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
