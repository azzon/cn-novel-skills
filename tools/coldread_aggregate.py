#!/usr/bin/env python3
"""coldread_aggregate.py 冷读分数聚合器(账本自动化批:METRICS行有格式无消费者)

用法: python3 tools/coldread_aggregate.py [书根]
扫 story/audit/冷读-第*章.md(书根=audit/)提取 [COLDREAD-METRICS] 机器行,输出:
  1) 30章前向滑窗峰值红线(窗满10章且峰值<8=红灯,drift-audit峰值红线的机器化)
  2) 钩强度全序列斜率(线性回归,连续负斜率=钩力衰减黄牌)
退出: 0=健康 1=红线/黄牌 2=无数据
"""
import re, sys, pathlib, statistics

ROOT = pathlib.Path(__file__).resolve().parent.parent
PAT = re.compile(r"\[COLDREAD-METRICS\]\s*章[:：]\s*(\d+).*?钩强度[:：]\s*([\d.]+).*?追读[:：]\s*([\d.]+)")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    book = pathlib.Path(args[0]).resolve() if args else ROOT
    adir = book / "audit" if book != ROOT else book / "story" / "audit"
    rows = {}
    if adir.exists():
        for f in sorted(adir.glob("冷读-第*章.md")):
            m = PAT.search(f.read_text(encoding="utf-8", errors="ignore"))
            if m:
                rows[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))
    if not rows:
        print(f"无COLDREAD-METRICS数据({adir}/冷读-*.md)——reader-proxy机器行未落盘或骨架未更新")
        return 2
    chs = sorted(rows)
    hooks = [rows[c][0] for c in chs]
    reds = []
    for i, c in enumerate(chs):
        win = chs[max(0, i - 29):i + 1]
        if len(win) >= 10 and max(rows[w][0] for w in win) < 8:
            reds.append(c)
    slope = 0.0
    if len(chs) >= 5:
        slope = statistics.linear_regression(range(len(chs)), hooks).slope
    print(f"冷读聚合: {len(chs)}章({chs[0]}-{chs[-1]})")
    print(f"  钩强度均值{statistics.mean(hooks):.1f} 最近10章均值{statistics.mean(hooks[-10:]):.1f}")
    if reds:
        print(f"  [FAIL] 峰值红线: 第{reds[0]}章起30章窗无钩强度≥8——名场面章必须显式冲峰")
    if slope < -0.05:
        print(f"  [WARN] 钩力衰减: 全序列斜率{slope:.3f}<0——钩强度逐章走低,alt-takes冲峰或换钩型")
    print(f"聚合: {'PASS' if not reds and slope >= -0.05 else 'FAIL' if reds else 'WARN'}")
    return 1 if reds else (0 if slope >= -0.05 else 0)


if __name__ == "__main__":
    sys.exit(main())
