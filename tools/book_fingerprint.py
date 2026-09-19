#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""book_fingerprint.py 全书级AI指纹检测(20260919用户令五: 治"AI味"——章级门测不到的跨章签名)

理论: 章级门制造"阈值贴线"(方差卡35→稿33,语气词卡12→稿11.7),而真正的AI味在
跨章尺度——同一批句式模板/同一套段尾收束/同一形状的开头结尾在全书中反复出现。

检测维度(全部跨章聚合):
  ① 房间纹(house tics): 4字n-gram出现在≥N章 = 全书签名词组(如"一笔一笔")
  ② 结尾形状分布: 章末段归类(账本注记/金句/对话/动作)——单一形状占比过高=模板
  ③ 开头形状分布: 章首段归类(时间状语/对话/动作/声音)
  ④ 排比三连: "X，X，X"复读/连续≥3个同头超短段
  ⑤ 明喻率: 像X一样/仿佛/如同 每章分布(贴线3=AI节律)
  ⑥ 对白标签: "说"系标签占比
  ⑦ 章末金句连收: 末两段连续警句

输出: audit/book-fingerprint.md(报告) + audit/book-tics.txt(禁复用清单,bundle注入)
用法: python3 tools/book_fingerprint.py <书根>
"""
import sys, re, pathlib, collections, json

def _cjk(s):
    return re.findall(r"[\u4e00-\u9fff]", s)

def _shape_ending(p):
    if re.search(r"火声簿|记一笔|添了.{0,4}行|记账|账页", p): return "账本注记"
    if p.startswith(("“", "”")): return "对话"
    if re.search(r"(不是.{1,14}(是|而是)|，才是|就得|就会|才值钱|就得等|就是它|睡着|醒着)$", p) and len(p) < 60: return "金句"
    if re.search(r"[。！”]", p) and len(p) <= 30: return "动作/短收"
    return "叙述"

def _shape_opening(p):
    if re.search(r"^(凌晨|天刚|清晨|傍晚|夜里|腊月|进了|第二天|周一|周二|周三|周四|周五|周六|周日|上午|下午|晚上)", p): return "时间状语"
    if p.startswith(("“", "”")): return "对话"
    if re.search(r"(声|响|鸣|噼啪|沙沙|滋滋|咔哒)", p[:24]): return "声音"
    return "动作/叙述"

def main():
    book = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    chapters = sorted((book / "text").rglob("第*章.md"))
    if len(chapters) < 3:
        print("章节不足"); return 1
    texts = {}
    for ch in chapters:
        t = ch.read_text(encoding="utf-8")
        n = re.search(r"第(\d+)章", ch.stem)
        texts[int(n.group(1))] = t

    report, tics = [], []

    # ① 房间纹: 4字n-gram跨章(标点滤除,低频虚词滤除)
    STOP = {"然后说","他说这","的时候","自己的","一个的","了起来"}
    doc_sets = {}
    tic_counter = collections.Counter()
    for n, t in texts.items():
        s = re.sub(r"[\s\u201c\u201d\"。，！？；：、—…]+", "", t)
        grams = {s[i:i+4] for i in range(len(s) - 3)}
        doc_sets[n] = grams
    for g in set.union(*doc_sets.values()):
        if g in STOP: continue
        c = sum(1 for gs in doc_sets.values() if g in gs)
        if c >= max(4, len(texts) // 3):
            tic_counter[g] = c
    report.append("## ① 房间纹(≥4章出现的4字签名词组)——全书AI签名主源")
    for g, c in tic_counter.most_common(20):
        report.append(f"- 「{g}」 {c}章")
        tics.append(g)
    if not tic_counter: report.append("- 无")

    # ②③ 开头/结尾形状
    rep_e, rep_o = collections.Counter(), collections.Counter()
    per_ch_end = {}
    for n, t in sorted(texts.items()):
        paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip() and not p.strip().startswith(("#", "<!--", "【"))]
        if not paras: continue
        e = _shape_ending(paras[-1]); o = _shape_opening(paras[0])
        rep_e[e] += 1; rep_o[o] += 1
        per_ch_end[n] = e
    report.append("\n## ② 章末形状分布(单一形状>50%=模板化)")
    for k, v in rep_e.most_common():
        pct = v * 100 // len(texts)
        report.append(f"- {k}: {v}章({pct}%)")
        if pct >= 50: tics.append(f"[章末形状]{k}")
    report.append("\n## ③ 章首形状分布")
    for k, v in rep_o.most_common():
        report.append(f"- {k}: {v}章({v * 100 // len(texts)}%)")

    # ④ 排比三连/同头超短段连发
    tri = []
    for n, t in sorted(texts.items()):
        body = re.sub(r"[^。！？\n\u4e00-\u9fff]", "", t)
        for m in re.finditer(r"([\u4e00-\u9fff]{2,5})，\1，", body):
            tri.append((n, m.group(0)))
        paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
        run = 0
        for p in paras:
            L = len(_cjk(p))
            if 0 < L <= 6:
                run += 1
                if run >= 3: tri.append((n, "连续超短段×3: " + p[:10])); break
            else: run = 0
    # 2-3字签名(磨刀七批: 4字粒度盲区——"心里明白"级短签名)
    short_sig = collections.Counter()
    short_docs = {}
    for n, t in texts.items():
        s3 = re.sub(r"[\s\u201c\u201d\"。，！？；：、—…]+", "", t)
        short_docs[n] = {s3[i:i+3] for i in range(len(s3) - 2)}
    common3 = set.intersection(*short_docs.values()) if short_docs else set()
    report.append("\n## ③b 2-3字签名(全书每章都出现的3字组合)")
    for g in sorted(common3)[:12]:
        report.append(f"- 「{g}」 21章")

    report.append("\n## ④ 排比三连/同头超短段连发")
    for n, m in tri: report.append(f"- 第{n:03d}章: {m[:20]}")

    # ⑤⑥⑦ 明喻率/对白标签/金句连收
    sim_ch, tag_ratio, aph_end = {}, {}, []
    for n, t in sorted(texts.items()):
        sim_ch[n] = len(re.findall(r"像[^。，]{1,8}一样|仿佛|如同|像一", t))
        quotes = re.findall(r"“[^”]{4,}”(?:，?\s*)(他说|她说|问|答|喊|道|嘀咕|应)", t)
        said = len(re.findall(r"[”」]?\s*(他说|她说)", t))
        tag_ratio[n] = said
        paras = [p.strip() for p in re.split(r"\n\s*\n", t) if p.strip()]
        if len(paras) >= 2:
            tail = paras[-2:]
            if all(_shape_ending(p) == "金句" for p in tail):
                aph_end.append(n)
    report.append("\n## ⑤ 明喻率分布(全贴线3=AI节律)")
    report.append("- " + " ".join(f"ch{n}:{c}" for n, c in sorted(sim_ch.items())))
    report.append("\n## ⑥ '他说/她说'标签计数(>5=单调)")
    report.append("- " + " ".join(f"ch{n}:{c}" for n, c in sorted(tag_ratio.items()) if c > 0))
    report.append("\n## ⑦ 章末金句连收(末两段连续警句)")
    report.append(("- " + " ".join(f"ch{n}" for n in aph_end)) if aph_end else "- 无")

    # 汇总判定
    score = 100 - len(tic_counter) * 3 - len(tri) * 4 - len(aph_end) * 5
    report.insert(0, f"# 全书AI指纹报告({len(texts)}章)\n\n**指纹风险分: {max(score,0)}/100**(越低越机器;房间纹每条-3,排比-4,金句连收-5)\n")

    out = book / "audit" / "book-fingerprint.md"
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    (book / "audit" / "book-tics.txt").write_text("\n".join(tics) + "\n", encoding="utf-8")
    print("\n".join(report[:40]))
    print(f"\n报告: {out}\n禁复用清单: {book}/audit/book-tics.txt(bundle注入,生成时禁用)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
