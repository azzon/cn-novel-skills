#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把正文中的直引号/全角引号成对转换为中文弯引号。用法: python3 tools/fix_quotes.py 文件.md"""
import sys

p = sys.argv[1]
t = open(p, encoding="utf-8").read()
out = []
open_q = True
for ch in t:
    if ch in ('"', "\uff02"):
        out.append("\u201c" if open_q else "\u201d")
        open_q = not open_q
    else:
        out.append(ch)
open(p, "w", encoding="utf-8").write("".join(out))
# 校验配对
res = open(p, encoding="utf-8").read()
n_open, n_close = res.count("\u201c"), res.count("\u201d")
print(f"转换完成: 左引号{n_open} 右引号{n_close} {'配对正常' if n_open == n_close else '不配对!需人工检查'}")
