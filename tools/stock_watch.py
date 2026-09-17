#!/usr/bin/env python3
"""stock_watch.py 存稿水位监控(红队系统#12 + publish.yaml落地)
存稿=已done章数与最新发布章数的差;低于安全线→警报
用法: python3 tools/stock_watch.py [--book 书根] [--min N]
"""
import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

def count(text_dir):
    return len(list(text_dir.glob("第*.md"))) if text_dir.exists() else 0

def main():
    book = pathlib.Path(sys.argv[sys.argv.index("--book") + 1]) if "--book" in sys.argv else ROOT
    min_n = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 0  # 边写边发模式: 存稿≥0即过
    tdir = book / "text" / "卷1"
    total = count(tdir)
    # 已发布=git中存在的章(简化: 以done记录为准)
    done_log = book / "ledgers" / "技能执行记录.md"
    done_ch = set()
    if done_log.exists():
        import re
        for m in re.finditer(r"第(\d{3})章", done_log.read_text(encoding="utf-8")):
            done_ch.add(int(m.group(1)))
    published = len(done_ch)  # 全部已归档视为已发布(本书未上架)
    stock = total - published
    status = "✅" if stock >= min_n else ("🟡" if stock >= min_n // 2 else "🔴")
    print(f"═══ 存稿水位({book.name if book != ROOT else '主书'}) ═══")
    print(f"  已归档章: {total} | 已发布口径: {published} | 存稿: {stock}")
    print(f"  {status} 安全线: {min_n} | {'达标' if stock >= min_n else '低于安全线——停止发布,全力生产'}")
    return 0 if stock >= min_n else 1

if __name__ == "__main__":
    sys.exit(main())
