#!/usr/bin/env python3
"""coldread_dispatch.py 冷读代理自动派遣器(自动化目标③)

流程效率审计: 冷读dispatch滞后于done,4章靠waiver放行,复验闭环率0%。
本工具生成标准化的冷读代理prompt,写入文件供Agent工具直接消费。

用法:
  python3 tools/coldread_dispatch.py <章号> [--book 书根] [--output prompt.md]
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def gen_prompt(n, book):
    b = pathlib.Path(book)
    body_files = sorted((b / "text").rglob(f"第{n:03d}章.md"))
    if not body_files:
        return None
    body_rel = body_files[0].relative_to(ROOT)

    return f"""你是干净上下文的毒舌读者代理（reader-proxy），冷读一章网文。你只读正文和锚样本，不读任何设计文档。

## 先读（校准+模板）
1. {ROOT}/story/audit/白金锚样本.md
2. {ROOT}/story/audit/劣锚样张.md
3. {ROOT}/tools/skill_protocol.py 中的 COLDREAD_SKELETON（grep -n "COLDREAD_SKELETON" 定位后读），严格按字段填写。

## 冷读对象
{ROOT}/{body_rel}（第{n:03d}章。你是挑剔的付费读者，全部引原文作证。）

## 落盘
UTF-8 Markdown → {b}/audit/冷读-第{n:03d}章.md，首行 `<!-- generated-by:skill_protocol gen-coldread 独立代理 -->`。所有引文用「」或块引用(>)逐字摘自正文。

## 返回消息只要
总分+追读判定一行 / 最致命问题第一条 / 最强段落摘录一段。
"""


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = ROOT
    if "--book" in sys.argv:
        book = ROOT / sys.argv[sys.argv.index("--book") + 1]
    output = None
    if "--output" in sys.argv:
        output = pathlib.Path(sys.argv[sys.argv.index("--output") + 1])
    if not args:
        print(__doc__)
        return 2
    n = int(re.sub(r"\D", "", args[0]) or 0)

    prompt = gen_prompt(n, book)
    if prompt is None:
        print(f"  [FAIL] 第{n:03d}章正文不存在")
        return 1

    if output:
        output.write_text(prompt, encoding="utf-8")
        print(f"  冷读prompt已生成: {output}")
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
