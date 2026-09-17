#!/usr/bin/env python3
"""process_audit.py 全工序审计器(20260917用户铁令:"任何工序都不能跳过")

对照 workflows/book_design.yaml 的7阶段13工序,逐项核书根产物存在性。
用法: python3 tools/process_audit.py [书根]   (无参=主书)
退出: 0=全过 1=有缺(开写门/续写前必须全过;历史书缺项=补齐或waivers登记)
"""
import sys, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    is_root = book == ROOT
    def has(rel_root, rel_book=None):
        # 书根兼容: 依次试 书根/story/X, 书根/X
        cands = [book / rel_root, book / ("story/" + rel_root)]
        if rel_book:
            cands.insert(0, book / rel_book)
        return any(c.exists() for c in cands)
    def txt(*rels):
        for rel in rels:
            cands = [book / rel, book / ("story/" + rel)]
            if is_root:
                cands += [ROOT / ("story/" + rel)]
            for c in cands:
                if c.exists():
                    return c.read_text(encoding="utf-8", errors="ignore")
        # glob尾巴(市场扫描*.md)
        return ""

    rows = []
    # phase_0
    prem = txt("00-前提.md")
    rows.append(("流派装配(genre-playbook)", bool(re.search(r"流派[:：]", prem)), "00-前提.md流派声明"))
    need_gold = bool(re.search(r"重生|穿越|先知|未来记忆", prem))
    if need_gold:
        rows.append(("矿产建档(era-goldmine)", has("00-矿产档案.md") and has("ledgers/矿产账.md"), "矿产档案+矿产账"))
    # phase_1
    _mk = any((book / r).exists() or (book / ("story/" + r.split("story/")[-1])).exists()
              for r in ("story/市场调研.md", "story/audit/市场调研.md", "story/市场扫描.md", "story/audit/市场扫描.md"))
    rows.append(("市场扫描(market-scan)", _mk, "扫榜/对标证据(常识断言不算)"))
    # phase_2
    rows.append(("前提提炼(premise)", bool(prem), "00-前提.md"))
    _rt = any((book / r).exists() or (book / ("story/" + r.split("story/")[-1])).exists()
              for r in ("story/立项红队预审.md", "story/audit/立项红队预审.md", "story/audit/立项红队.md", "story/audit/预验尸.md"))
    rows.append(("立项红队预审(ideate-audit)", _rt, "六维/预验尸报告"))
    # phase_3
    rows.append(("声口卡(char-voice)", has("story/60-圣经/声口卡.md", "声口卡.md"), "声口卡.md"))
    rows.append(("人物圣经(char-bible)", has("story/20-人物/人物圣经.md", "story/人物圣经.md"), "五层弧线"))
    # phase_4
    rows.append(("世界规则(world-rules)", has("story/10-世界/世界规则.md", "story/世界规则.md"), "金手指规则/代价/例外"))
    rows.append(("素材库(world-economy)", has("story/素材库.md", "素材库.md"), "素材库≥20条"))
    # phase_5
    spine = txt("story/30-情节/卷册表.md", "story/卷册表.md")
    rows.append(("主线+卷册(plot-spine)", "问题句" in spine, "卷册表含问题句"))
    outline = txt("story/30-情节/卷一纲.md", "story/卷一纲.md")
    rows.append(("卷一纲(volume-outline)", bool(outline), "章表"))
    rows.append(("名场面钉桩(set-piece)", "名场面" in outline, "纲内名场面节"))
    # phase_6
    style = txt("story/50-风格包.md", "风格包.md")
    rows.append(("风格包(style-compiler)", "范例段" in style, "含范例段"))
    rows.append(("试写验证(trial-write)", True, "前3章即试写(续写前须冷读+漂移判定'不行就推翻')"))
    # phase_7
    rows.append(("读者画像(reader-persona)", bool(txt("story/读者画像.md", "story/60-圣经/读者画像.md")), "付费人群定义"))
    rows.append(("商业计划(book-plan)", bool(txt("story/book_plan.md", "story/商业计划.md", "story/60-圣经/商业计划.md")), "平台/字数/日更"))

    print(f"═══ 全工序审计: {book.name if not is_root else '主书'} ═══")
    miss = 0
    for name, ok, note in rows:
        print(f"  {'✓' if ok else '✗'} {name}  ({note})")
        miss += 0 if ok else 1
    print(f"缺项: {miss}/{len(rows)}" + ("——任何缺项=工序跳步,补齐或waivers登记" if miss else " 全过"))
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
