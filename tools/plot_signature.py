#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plot_signature.py 情节签名比对器(红队20260919: 概念级重复检测)

问题: 两个完全不同表述的相同桥段,文字级查重检测不到。
方案: 每章提取四元组签名——(场景型,冲突源,价值转换方向,获得类型)
     相似签名跨章比对,连续3章以上同签名=结构性重复。

用法:
  python3 tools/plot_signature.py [书根] [--threshold 0.6]
输出: 签名矩阵+重复警告
"""
import sys, pathlib, re, json
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

def extract_signature(card_path, ch_num):
    """从场景卡提取四元组签名"""
    if not card_path.exists():
        return None
    t = card_path.read_text(encoding="utf-8")
    
    sig = {"ch": ch_num, "场景型": "", "冲突源": "", "价值转换": "", "获得": ""}
    
    for field in ["场景型", "冲突源", "价值", "获得"]:
        m = re.search(rf'\*\*{field}\*\*[：:]\s*(.+?)(?=\n-|\Z)', t, re.S)
        if m:
            val = m.group(1).strip()[:30]
            sig[field] = val
    
    return sig if any(sig.values()) else None

def similarity(a, b):
    """简化相似度: 共同字符比例"""
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / max(len(sa | sb), 1)

def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    threshold = 0.6
    if "--threshold" in sys.argv:
        threshold = float(sys.argv[sys.argv.index("--threshold") + 1])
    
    cards = sorted((book / "卡").glob("卷*-第*-场1.md"))
    if not cards:
        print("无场景卡"); return 0
    
    sigs = []
    for c in cards:
        m = re.search(r'第(\d+)章', c.stem)
        if m:
            s = extract_signature(c, int(m.group(1)))
            if s:
                sigs.append(s)
    
    if len(sigs) < 3:
        print(f"章数不足({len(sigs)}),跳过签名比对"); return 0
    
    print(f"═══ 情节签名矩阵({len(sigs)}章) ═══\n")
    
    # 提取核心维度(场景型/价值转换方向)
    dims = []
    for s in sigs:
        d = f"{s.get('场景型','?')}|{s.get('价值转换','?')[:20]}|{s.get('获得','?')[:10]}"
        dims.append(d)
    
    # 检测连续同签名
    issues = []
    for i in range(2, len(dims)):
        if dims[i] == dims[i-1] == dims[i-2]:
            issues.append(f"第{sigs[i-2]['ch']}-{sigs[i]['ch']}章: 连续3章签名相同[{dims[i][:30]}]")
    
    if issues:
        print("❌ 结构性重复:")
        for iss in issues:
            print(f"  ⚠️ {iss}")
        return 1
    else:
        print("✅ 无连续同签名(结构新鲜度合格)")
    
    # 输出签名分布
    print(f"\n签名分布:")
    for s in sigs:
        print(f"  第{s['ch']:03d}章: {s['场景型'][:12]} | {s['冲突源'][:16]} | {s['获得'][:10]}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
