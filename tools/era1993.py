#!/usr/bin/env python3
"""era1993.py 1993年代词检查器"""
import sys, re, pathlib
ANACHRON = [
    (r"智能手机|刷手机|手机支付|扫码|二维码", "2010s移动支付"),
    (r"微信|朋友圈|公众号|抖音|快手|直播带货", "2010s社交/短视频"),
    (r"外卖平台|饿了么|美团外卖|外卖小哥", "2010s外卖平台"),
    (r"网约车|滴滴|共享单车", "2010s共享经济"),
    (r"人工智能|AI|ChatGPT|大模型", "2020sAI"),
    (r"内卷|躺平|摆烂|凡尔赛|破防|yyds|绝绝子", "2020s网络语"),
    (r"大数据|云计算|区块链|元宇宙", "2010s科技热词"),
    (r"高铁|动车组|复兴号", "2007+高铁"),
    (r"网购|淘宝|京东|电商", "2003+电商"),
]
def check(fp):
    t = pathlib.Path(fp).read_text(encoding="utf-8")
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    issues = []
    for pat, label in ANACHRON:
        for m in re.finditer(pat, t):
            ctx = t[max(0,m.start()-10):m.end()+10]
            issues.append(f"  [{label}] ...{ctx}...")
    if issues:
        print(f"  [FAIL] {pathlib.Path(fp).name} 1993年代词穿帮 {len(issues)}处:")
        for x in issues[:5]: print(x)
        return 1
    return 0
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print("用法: era1993.py <章文件> | era1993.py --scan(已并入era_clean;本工具按章文件扫描)"); sys.exit(0)
    sys.exit(check(sys.argv[1]))
