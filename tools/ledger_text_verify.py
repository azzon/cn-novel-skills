#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger_text_verify.py 账-正文对账验证器(盲区046)

问题: 所有伏笔审计完全信任账本("状态:已收"不验正文),账实分离不可见。
本工具做反向验证: 账本说埋了/收了的事,在正文里能不能找到。

用法: python3 tools/ledger_text_verify.py [书根]
周期: 每20章或卷末
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def verify_foreshadow(ledger, files):
    """伏笔账-正文对账: 账说埋在第N章的事,第N章正文里有没有"""
    issues = []
    if not ledger.exists():
        return issues
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("- ["):
            continue
        # 解析: [F-N] 描述 | 埋:第NNN章 | ...
        m = re.search(r'\[([FA])-?\d+\]\s*(.{5,40})\|?\s*埋[:：]第?(\d+)', line)
        if not m:
            continue
        ftype, desc, ch = m.group(1), m.group(2).strip(), int(m.group(3))
        # 找到对应章的正文
        target_file = None
        for f in files:
            if f.stem == f"第{ch:03d}章" or re.search(rf'第{ch}章', f.stem):
                target_file = f
                break
        if not target_file:
            issues.append(f"伏笔账说第{ch:03d}章埋了[{desc[:20]}],但该章正文不存在")
            continue
        # 在正文中搜索关键词(取描述中的核心词)
        body = target_file.read_text(encoding="utf-8")
        # 取描述中2-4字的关键词
        keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', desc)
        found = any(kw in body for kw in keywords[:5])  # 前5个关键词任一命中
        if not found:
            issues.append(f"伏笔账说第{ch:03d}章埋了[{desc[:20]}],但正文找不到相关内容(账实分离——章漏写则按账补埋设段;改稿漂移则同步伏笔账条目)")
    return issues

def verify_numbers(num_ledger, files):
    """数字账-正文对账: 账说第N章有金额X,正文里有没有"""
    issues = []
    if not num_ledger.exists():
        return issues
    for line in num_ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("- "):
            continue
        # 解析: 科目|限定|值|第NNN章
        m = re.search(r'([^|]+)\|[^|]*\|([^|]+)\|第?(\d+)', line)
        if not m:
            continue
        subj, val, ch = m.group(1).strip(), m.group(2).strip(), int(m.group(3))
        target_file = None
        for f in files:
            if re.search(rf'第{ch}章', f.stem):
                target_file = f
                break
        if not target_file:
            continue
        body = target_file.read_text(encoding="utf-8")
        # 检查值是否在正文中(数字或中文)
        val_clean = re.sub(r'[^\d.]', '', val)
        if val_clean and val_clean not in body:
            # 尝试中文变体(简化)
            issues.append(f"数字账: 第{ch:03d}章[{subj}]={val},正文可能不含此值(检查是否修改)")
    return issues

def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    files = sorted(book.glob("text/卷*/第*.md"))
    if not files:
        print("无章节可对账"); return 0
    
    print(f"═══ 账-正文对账({len(files)}章) ═══\n")
    all_issues = []
    
    # 1. 伏笔对账
    fs = verify_foreshadow(book / "ledgers" / "伏笔.md", files)
    print(f"── 伏笔对账: {len(fs)}项账实分离 ──")
    for i in fs[:5]:
        print(f"  ⚠️ {i}")
    all_issues.extend(fs)
    
    # 2. 数字对账
    ns = verify_numbers(book / "ledgers" / "数字账.md", files)
    print(f"\n── 数字对账: {len(ns)}项可疑 ──")
    for i in ns[:5]:
        print(f"  ⚠️ {i}")
    all_issues.extend(ns)
    
    print(f"\n═══ 总计: {len(all_issues)}项账实分离 ═══")
    return 1 if all_issues else 0

if __name__ == "__main__":
    sys.exit(main())
