#!/usr/bin/env python3
"""goldmine_audit.py 矿产账审计(2026-09-15 era-goldmine体系配套——重生/穿越书第九账)

原理:
  ledgers/矿产账.md 登记每次时代资产开采(goldmine格式见skills/ideate/era-goldmine)。
  本工具审计:
    1) 双采: 同一[G-n]出现两个"采:"章——读者眼里的刷钱复读
    2) 未排期: 档案里有矿但账里无"排期"也无"采"——矿脉闲置(排纲漏点)
    3) 类别轮换: 连续≥3条同类别已采——等同于好消息确认循环病
    4) 时扰累计: Σ时扰>3——蝴蝶预警,原史依赖的矿须降级
    5) 超窗开采: 采章对应故事时间(时间线账)不在窗口年份内——穿帮级
  非重生书(前提无"重生|穿越|先知")自动跳过;重生书无矿产账=FAIL(硬前置)。

用法:
  python3 tools/goldmine_audit.py [书根]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def parse_rows(path):
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        s = line.strip()
        m = re.match(r"-\s*\[G-(\d+)\]\s*(.+)$", s)
        if not m:
            continue
        rows.append({"gid": m.group(1), "raw": s, "rest": m.group(2)})
    return rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    if not book.is_dir():
        print(f"书根不存在: {book}")
        return 2

    premise = ""
    for c in ("00-前提.md", "story/00-前提.md"):
        f = book / c
        if f.exists():
            premise = f.read_text(encoding="utf-8")
            break
    is_rebirth = bool(re.search(r"重生|穿越|先知|未来记忆|上一世|前世", premise))
    ledger = book / "ledgers" / "矿产账.md"
    archive = book / "00-矿产档案.md"

    if not is_rebirth:
        print(f"非重生/穿越书(前提无标记)——矿产审计跳过")
        return 0
    if not ledger.exists():
        body_files = sorted((book / "text").rglob("第*.md")) if (book / "text").is_dir() else []
        if not body_files:
            print("  [WARN] 重生书缺矿产账且无正文——待重启状态,正常")
            return 0
        print(f"  [FAIL] 重生书缺矿产账({ledger.relative_to(book)})——era-goldmine硬前置: 建账+00-矿产档案.md")
        return 1

    issues, warns = [], []
    rows = parse_rows(ledger)

    # 时间线: 章号→故事年份
    tl_years = {}
    tlf = book / "ledgers" / "时间线.md"
    if tlf.exists():
        for line in tlf.read_text(encoding="utf-8").splitlines():
            m = re.match(r"-\s*第0?(\d+)章\|(\d{4})年?", line.strip())
            if m:
                tl_years[int(m.group(1))] = int(m.group(2))

    mined, scheduled = {}, set()
    drift = 0
    cat_seq = []
    for r in rows:
        rest = r["rest"]
        catm = re.search(r"类别[:：]\s*(\S+?)(?:\s*\||$)", rest)
        cat = catm.group(1) if catm else "?"
        dm = re.search(r"采[:：]\s*第?0?(\d+)章", rest)
        sm = re.search(r"排期[:：]\s*ch?0?(\d+)|排期[:：]\s*第?0?(\d+)章", rest)
        gid = r["gid"]
        if dm:
            ch = int(dm.group(1))
            if gid in mined:
                issues.append(f"[G-{gid}] 双采: 第{mined[gid]:03d}章与第{ch:03d}章重复开采——刷钱复读,读者视角的最快弃书点之一")
            mined[gid] = ch
            cat_seq.append(cat)
            # 超窗: 窗口年份 vs 采章故事年
            wm = re.search(r"窗口[:：]\s*(\d{4})", rest)
            if wm and ch in tl_years:
                if not re.search(r"已过|错过|错过区", rest):
                    wy = int(wm.group(1))
                    if abs(tl_years[ch] - wy) > 1:   # 容差1年(跨年窗口)
                        issues.append(f"[G-{gid}] 超窗开采: 第{ch:03d}章故事时间{tl_years[ch]}年,窗口锚{wy}年——先知记错日子=穿帮")
        if sm:
            scheduled.add(gid)
        tm = re.search(r"时扰[:：]\s*(\d)", rest)
        if dm and tm:
            drift += int(tm.group(1))

    # 未排期(有窗口未错过,却既无排期也无采)
    idle = [r for r in rows if re.search(r"窗口[:：]\s*\d{4}", r["rest"])
            and not re.search(r"错过|已过窗", r["rest"])
            and r["gid"] not in mined and r["gid"] not in scheduled]
    if len(idle) >= 3:
        warns.append(f"矿脉闲置{len(idle)}条(有窗未排未采): {[r['gid'] for r in idle][:6]}——排卷纲时从档案选点")

    # 类别连采
    for i in range(len(cat_seq) - 2):
        if cat_seq[i] == cat_seq[i+1] == cat_seq[i+2]:
            warns.append(f"同类矿连采≥3({cat_seq[i]})——爽点单调,类别轮换(era-goldmine排期2)")
            break

    if drift > 3:
        warns.append(f"时扰累计{drift}(>3)——蝴蝶预警: 原史依赖矿须在档案标'已污染'降级,从错过区补新矿")

    # 档案存在性
    if not archive.exists():
        warns.append("缺00-矿产档案.md(只有账无档案)——档案是排纲选矿的池子,补建")

    for x in issues:
        print(f"  [FAIL] {x}")
    for w in warns:
        print(f"  [WARN] {w}")
    print(f"矿产审计: {'FAIL' if issues else 'PASS'}(已采{len(mined)}条/排期{len(scheduled)}条/时扰{drift})")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
