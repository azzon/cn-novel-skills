#!/usr/bin/env python3
"""anchor_canary.py 锚漂移哨兵(红队冷读可信度: 分数爬升可能是裁判失灵而非质量上升)

机制: 冷读出处账每满10次硬门冷读,须混入一次"金丝雀"——把劣锚样张伪装成被测章
交给同一裁判评分。劣锚若被打≥7分=裁判失灵,近10次冷读全部作废重评。
用法: python3 tools/anchor_canary.py <书根>   # 返回: 需要金丝雀/正常/金丝雀失败警报
"""
import re, sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CYCLE = 10


def main():
    book = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
    pro = book / "ledgers" / "冷读出处.md"
    if not pro.exists():
        print("无冷读出处账——硬门冷读须落账(pipeline done出处门会拦)")
        return 0
    rows = [l for l in pro.read_text(encoding="utf-8").splitlines()
            if l.strip().startswith("- 第") and "hash" in l]
    canaries = []
    for l in pro.read_text(encoding="utf-8").splitlines():
        m = re.search(r"canary[^\d]*([0-9](?:\.[0-9])?)", l)
        if m:
            canaries.append(float(m.group(1)))
    n = len(rows)
    since = n % CYCLE
    # 最近一次金丝雀之后的冷读数
    print(f"冷读累计{n}次,金丝雀{len(canaries)}次(周期{CYCLE})")
    if canaries and canaries[-1] >= 7:
        print("  [FAIL] 金丝雀锚被打≥7分——裁判失灵!近10次冷读作废,重配锚样本并重评")
        return 1
    if n > 0 and n % CYCLE == 0 and (not canaries or n - canaries.index(canaries[-1]) * CYCLE >= CYCLE if canaries else True):
        print("  [ACTION] 冷读满10次: 本轮须混入金丝雀(劣锚样张伪装成被测章,同一裁判评分,结果记入本账 canary行)")
        return 0
    print("  正常(距下次金丝雀还有%d次)" % (CYCLE - since))
    return 0


if __name__ == "__main__":
    sys.exit(main())
