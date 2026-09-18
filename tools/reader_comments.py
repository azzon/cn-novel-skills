#!/usr/bin/env python3
"""reader_comments.py 读者评论区模拟(补系统缺失工序: 读者反馈前置化)
不依赖AI——用文本特征统计生成"预测评论区"(启发式):
  章末钩强度→催更评论; 扩散密度→"爽"评论; 对话占比→角色粉; WARN区→吐槽
用法: python3 tools/reader_comments.py <章文件>
输出: 模拟评论区(5条) + 追读率预估
"""
import re, sys, pathlib

PAT_HOOK = re.compile(r"[?！!]|——|…|突然|忽然|就在这时|却见|赫然|竟是|一声|来了|开门|转身")
PAT_REACT = re.compile(r"震惊|惊呆|哗然|炸了|轰动|全县|传遍|议论|傻眼|服了|倒吸|看傻|围观|打听|排队|传开|念叨|拍大腿|将信将疑|看热闹|人人皆知")
PAT_MONEY = re.compile(r"\d+[块元万毛分]")
PAT_MEM = re.compile(r"想起|记得|当年|小时候|那时候|那年|上辈子|前世|又浮现|冒出来")
PAT_SOCIAL = re.compile(r"拍桌|拍腿|倒吸|炸了|全场|都愣了|鸦雀无声|哄一声|鼓掌|愣住|看傻|哗然")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        print(__doc__ or "用法: reader_comments.py <章文件>"); return 0
    fp = pathlib.Path(sys.argv[1])
    if not fp.exists():
        print(f"文件不存在: {fp}"); return 2
    t = re.sub(r"<!--.*?-->", "", fp.read_text(encoding="utf-8"), flags=re.S)
    cn = len(re.findall(r"[\u4e00-\u9fff]", t))
    tail_lines = [l for l in t.split("\n") if l.strip()][-3:]
    hook = len(PAT_HOOK.findall("".join(tail_lines)))
    if not hook and any(len(re.findall(r"[\u4e00-\u9fff]", l)) <= 10 for l in tail_lines):
        hook = 1  # 短句重音也算钩
    react = len(PAT_REACT.findall(t))
    money = len(PAT_MONEY.findall(t))
    dial = t.count("“") // 2
    print(f"═══ 预测评论区({fp.name}, {cn}字) ═══")
    comments = []
    if hook: comments.append(("催更党", "这章结尾憋死人,下一章呢?!"))
    if react >= 2: comments.append(("爽点党", "这波围观看得舒服,就该这么写!"))
    if react == 0: comments.append(("路人甲", "没感觉,划走了。"))   # W6验证:缺元组括号react==0必TypeError
    if money >= 3: comments.append(("经营党", "数字看得踏实,这作者的账不会崩。"))
    if dial / max(cn/1000,1) < 30: comments.append(("对话党", "叙述有点多,想看人说话。"))
    names = ["老书虫", "白嫖党", "追更中", "夜班工人", "小学生他爹"]
    pool = [c for c in comments if c[1]]
    while len(pool) < 5:
        names.insert(0, "路人")
        pool.insert(0, ("路人", "路过。"))
    for i, (who, txt) in enumerate(pool[:5]):
        print(f"  [{who}]: {txt}")
    # 追读率预估(启发式+三引擎v2: 记忆碎片/社交货币/超短段)
    mem = len(PAT_MEM.findall(t))
    social = len(PAT_SOCIAL.findall(t))
    score = min(10, hook*2 + react + (2 if money >= 2 else 0) + (1 if mem >= 2 else 0) + (1 if social >= 2 else 0))
    ret = 60 + score * 3.5
    print(f"\n  追读率预估: {ret:.0f}% (钩{hook}+扩散{react}+账面{money}+记忆{mem}+社交{social} → score {score}/10)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
