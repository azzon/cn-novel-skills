#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
exemplar_flywheel.py 范例段飞轮(提上限的核心机制: 模型从自己最好的文字里学)

原理: 冷读报告会引原文圈出"最强段落/白金手感段"——这些是本书自己的高光文字。
本工具把它们收割进 <书根>/风格包范例段库.md(按五型: 对话/动作/情感/收尾/生活,每型保3段),
bundle 生成下一章时注入2段匹配型——上限随写作推进自我抬升。

红队20260915(注入质量红队)收割卫生重写,四类历史事故全堵:
  1. "待agent"占位收割(ch001/003冷读残留→库→曾入bundle)——占位词表拦截;
  2. 模板栏头自回显(031/032冷读"最强段落摘录（…）："整行入库)——栏头回显拦截+
     标签解析改"剥括号组→剥冒号"(全角/半角括号都吃;旧`\)\s*[:：]`只配半角右括号,
     配不中时re.split原样返回整行,占位栏头就成了"范例"——事故根因);
  3. 非摘录区引文误收(030"每段有一件具体的事在发生"/"美凤那半句…"来自白金锚对照
     行的判词与读者提问)——废除40字泛关键词窗口,只从"最强段落摘录/生活气摘录"
     栏本行+其引用块正文收割;
  4. 正文里不存在的"摘录"(评语/判词混入)——入库前对第NNN章正文做溯源验证:
     摘录按省略号切块,最长块(去引号/空白后>=12字)必须在正文命中,否则丢弃。

库为冷读报告的纯函数: 每次全量重建(不回读旧库),历史污染随重建自动清除。

用法: python3 tools/exemplar_flywheel.py harvest [书根]   # 从audit/冷读-*.md收割
      python3 tools/exemplar_flywheel.py show [书根]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ---- 收割卫生(红队20260915) ----
PLACEHOLDER_RE = re.compile(r"（填）|\(填\)|待agent|待填|待补|待冷读|TODO|占位|待收割|^\s*_+\s*$")
HEADER_ECHO_RE = re.compile(r"^[\s\->#*]*(最强段落摘录|生活气摘录|劣锚样张|白金锚|追读判定)")
FIELD_RE = re.compile(r"^-\s*(最强段落摘录|生活气摘录)")
LOCATOR_RE = re.compile(r"^(行\s*\d+(?:[-+]\d+)*(?:\s*\+\s*行\s*\d+)*|第\s*\d+\s*段)\s*[——\-]*\s*")
QUOTE_ANY = r"[“「\"]"


def is_garbage(seg):
    """占位/模板行/非正文来源统一闸门。"""
    s = seg.strip()
    if len(s) < 12:                                   # 太短=残渣/栏名碎片
        return True
    if not re.search(r"[\u4e00-\u9fff]", s):          # 无汉字=非正文
        return True
    if PLACEHOLDER_RE.search(s) or HEADER_ECHO_RE.match(s):
        return True
    return False


def strip_label(rest):
    """剥掉栏头标签里的说明括号组与结尾冒号(组内可含冒号,如'待agent一段烟火气: 物件/…')。"""
    rest = rest.strip()
    while True:
        nxt = re.sub(r"^[（(][^（）()]*[）)]\s*", "", rest)
        if nxt == rest:
            break
        rest = nxt
    return re.sub(r"^[:：]\s*", "", rest).strip()


def inline_variants(rest):
    """旧格式候选,按保真度排序:
    ① 首引号→末引号整段(保内层短引号,如015"可我惦记"); ② 引号跨度拼接(内层短引号
    被丢,但能甩掉引号外的评语尾巴); ③ 砍定位符后的裸行(无引号栏用)。
    哪个能过正文溯源用哪个(验证即预言机)。"""
    body = strip_label(rest)
    if not body:
        return []
    out = []
    m = re.search(r'["“「].*["”」]', body, re.S)
    if m:
        out.append(m.group(0).strip())
    qs = re.findall(r'["“「]([^"”」]{12,})["”」]', body)
    if qs:
        out.append("\n".join(q.strip() for q in qs if len(q.strip()) >= 12))
    raw = LOCATOR_RE.sub("", body).strip()
    if raw:
        out.append(raw)
    return out


def _norm(s):
    return re.sub(r"[\s“”\"「」‘’'…·]", "", s)


def in_chapter_text(seg, ch_path):
    """溯源验证: 摘录按省略号/换行/斜杠分隔切块,最长块(>=12字归一化后)须出现在该章正文里。"""
    if ch_path is None:
        return True   # 正文文件不在(如外部书根)——放行并提示
    body = _norm(ch_path.read_text(encoding="utf-8"))
    chunks = [c for c in re.split(r"…+|\n|（…*）|\(…*\)|[/／]", seg) if len(_norm(c)) >= 12]
    if not chunks:
        return False
    best = max(chunks, key=lambda c: len(_norm(c)))
    return _norm(best) in body


def chapter_text(book, ch):
    for p in sorted(book.glob(f"text/卷*/第{int(ch):03d}章.md")):
        return p
    for p in sorted(book.glob(f"text/**/第{int(ch):03d}章*.md")):
        return p
    return None


def classify(q):
    if re.search(r"[饭菜品摊烟钱票布碗盆秤]", q) and not re.search(QUOTE_ANY, q[:5]):
        return "生活"
    if re.search(QUOTE_ANY, q):
        return "对话"
    if re.search(r"收|末|钩", q[:6]):
        return "收尾"
    return "情感" if re.search(r"[心头疼暖哭酸紧]", q) else "动作"


def harvest(book):
    audit = book / "audit"
    lib = book / "风格包范例段库.md"
    if not audit.is_dir():
        print(f"无audit目录: {audit}")
        return 2
    entries = []   # (章,型,段)
    saw_field = False
    for f in sorted(audit.glob("冷读-第*章.md")):
        m = re.match(r"冷读-第(\d+)章", f.name)
        ch = m.group(1) if m else "?"
        lines = f.read_text(encoding="utf-8").splitlines()
        ch_path = chapter_text(book, ch) if ch.isdigit() else None
        # 冷读骨架"最强段落摘录/生活气摘录"双栏: 本行内联(旧格式)或下一组blockquote(新格式)
        for i, line in enumerate(lines):
            if not FIELD_RE.match(line.strip()):
                continue
            saw_field = True
            seg = ""
            for cand in inline_variants(re.sub(r"^-\s*(最强段落摘录|生活气摘录)", "", line.strip())):
                if cand and not is_garbage(cand) and in_chapter_text(cand, ch_path):
                    seg = cand
                    break
            if not seg:   # 新格式: 正文在随后的 > 引用块里,收到非>行为止
                buf = []
                for nxt in lines[i + 1:]:
                    mq = re.match(r"^\s*>(.*)$", nxt)
                    if mq:
                        buf.append(mq.group(1).strip())
                    elif nxt.strip() == "" and buf:
                        break    # 引用块已开,遇空行结束
                    elif nxt.strip() != "":
                        break
                cand = "\n".join(b for b in buf if b)
                if cand and not is_garbage(cand) and in_chapter_text(cand, ch_path):
                    seg = cand
                elif cand:
                    print(f"  [溯源失败·丢弃] 第{ch}章: {cand[:30]}…")
            if seg:
                entries.append((ch, classify(seg), seg.strip()))
    if not saw_field:
        print("冷读报告未含最强段落摘录/生活气摘录栏——无收割物")
        return 0
    # 全量重建: 库=冷读报告的纯函数,历史污染不回读;每型保最新3段,去重
    from collections import defaultdict
    byt, seen = defaultdict(list), set()
    for ch, tp, seg in entries:
        key = re.sub(r"\W", "", seg[-40:])
        if key in seen:
            continue
        byt[tp].append(f"- 第{ch}章 | {seg}")
        seen.add(key)
    kept = {tp: byt.get(tp, [])[-3:] for tp in ("对话", "动作", "情感", "收尾", "生活")}
    out = ["# 风格包范例段库(冷读高光收割·飞轮)", "> tools/exemplar_flywheel.py 自动维护;每型保最新3段;bundle按场景型注入2段", ""]
    for tp in ("对话", "动作", "情感", "收尾", "生活"):
        out.append(f"## {tp}型")
        out.extend(kept[tp])
        out.append("")
    lib.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"收割{len(entries)}段(去重前) → {lib.name}(每型最新3段,共{sum(len(v) for v in kept.values())}段入库)")
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mode = args[0] if args else "harvest"
    book = ROOT / args[1] if len(args) > 1 else ROOT
    if mode == "show":
        f = book / "风格包范例段库.md"
        print(f.read_text(encoding="utf-8") if f.exists() else "库不存在")
        return 0
    return harvest(book)


if __name__ == "__main__":
    sys.exit(main())
