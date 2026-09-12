#!/bin/bash
# pre-commit hook v4: 质量门 + 流程合规门 + 韧性门
# v4(audits/13攻防): name-status处理删除(D)/大小写不敏感(.MD逃逸)/progress单独staged不早退/
#   waiver门级化(check|card|del分权+格式校验)/场景卡最小内容门
# 安装: cp tools/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
FAIL=0

echo "═══════════════════════════════════════════"
echo "  PRE-COMMIT v4: 质量+流程+韧性门"
echo "═══════════════════════════════════════════"

# quotepath=false: 否则默认配置下CJK路径被八进制转义,所有匹配失灵(audits/06 P0)
# name-status: 必须看见删除(D)——ACM过滤曾使"git rm整卷"零阻力穿透(audits/13攻击4)
if ! STATUS_OUT=$(git -c core.quotepath=false diff --cached --name-status --diff-filter=ACMRD 2>/tmp/gate_git_err.txt); then
    echo -e "${RED}[FAIL] git diff失败(fail-closed): $(cat /tmp/gate_git_err.txt)${NC}"
    exit 1
fi

# 重命名(R)按新路径判定: text/→archive/的归档移动自然豁免(audit修正)
NEW_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /^text\/卷[^\/]+\/第[0-9]+章\.md$/ && $1=="A" {print $2}')
MOD_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /^text\/卷[^\/]+\/第[0-9]+章\.md$/ && $1=="M" {print $2} tolower($3) ~ /^text\/卷[^\/]+\/第[0-9]+章\.md$/ && $1 ~ /^R/ {print $3}')
DEL_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /^text\/卷[^\/]+\/第[0-9]+章\.md$/ && $1=="D" {print $2}')
CHAPTERS=$( { [ -n "$NEW_CH" ] && echo "$NEW_CH"; [ -n "$MOD_CH" ] && echo "$MOD_CH"; [ -n "$DEL_CH" ] && echo "$DEL_CH"; } )
SKILLS_STAGED=$(echo "$STATUS_OUT" | awk -F'\t' '$2 ~ /^(\.zcode\/skills\/|skills\/|\.claude\/skills\/)/ {print $2}')
PROGRESS_STAGED=$(echo "$STATUS_OUT" | awk -F'\t' '$2 == ".progress.json"' | wc -l)
# text/下既非章节又非已知目录的新增文件(改名逃逸哨兵,audits/13攻击4)
TEXT_ODD=$(echo "$STATUS_OUT" | awk -F'\t' '$1=="A" && $2 ~ /^text\// && tolower($2) !~ /第[0-9]+章\.(md)$/ && $2 !~ /^text\/卡\// {print $2}')

if [ -z "$CHAPTERS" ] && [ -z "$SKILLS_STAGED" ] && [ "$PROGRESS_STAGED" -eq 0 ] && [ -z "$TEXT_ODD" ]; then
    echo -e "${GREEN}[PASS] 无章节/技能/进度变更，跳过。${NC}"
    exit 0
fi

# waiver登记制v4: 门级授权。格式: - chNNN: <门id>[;<门id>...] (日期)  门id∈{check,card,del,all}
# 一行只豁免列出的门;无门id的旧行不生效。删除章必须del门;check.py全项=check门。
waiver_registered() {  # $1=章号 $2=门id
    [ -f ledgers/waivers.md ] || return 1
    local line
    line=$(grep -E "^- ch0?$1:" ledgers/waivers.md 2>/dev/null | tail -1)
    [ -z "$line" ] && return 1
    echo "$line" | grep -qE "(^|[;:（([:space:]])($2|all)([;)）;:[:space:]]|$)"
}

# ── A. 韧性门(整批一次: 章号重复/标题重复/卷归属/跨章查重/字数/时序) ──
# gate_chapter.py只认第一个模式词;新增/修改必须分两次调用,否则第二个模式词被当成路径(读空=0字假FAIL)
GATE_FAIL_ALL=0
: > /tmp/gate_ch_out.txt
if [ -n "$NEW_CH" ]; then
    python3 tools/gate_chapter.py new $NEW_CH >> /tmp/gate_ch_out.txt 2>&1 || GATE_FAIL_ALL=1
fi
if [ -n "$MOD_CH" ]; then
    python3 tools/gate_chapter.py modified $MOD_CH >> /tmp/gate_ch_out.txt 2>&1 || GATE_FAIL_ALL=1
fi
if [ -n "$NEW_CH" ] || [ -n "$MOD_CH" ]; then
    echo ""
    echo "── 韧性门(章号/标题/卷归属/跨章查重/字数/时序) ──"
    if [ "$GATE_FAIL_ALL" != "0" ]; then
        echo -e "${RED}  [FAIL] 韧性门未过:${NC}"
        grep '\[FAIL\]' /tmp/gate_ch_out.txt | head -6 | sed 's/^/    /'
        FAIL=1
    else
        echo -e "${GREEN}  [PASS] staged全部章节通过${NC}"
        grep '\[WARN\]' /tmp/gate_ch_out.txt | sort | uniq -c | sed 's/^/    /'
    fi
fi

# ── B. 章节删除门(新,v4): 删章=结构性变更,必须del门或走arc-restructure记录 ──
if [ -n "$DEL_CH" ]; then
    echo ""
    echo "── 章节删除门 ──"
    for DCH in $DEL_CH; do
        DN=$(echo "$DCH" | grep -o '第[0-9]*章' | grep -o '[0-9]*')
        if waiver_registered "$DN" "del"; then
            echo -e "${YELLOW}  [WAIVER] 删除第${DN}章(已登记del门)${NC}"
        else
            echo -e "${RED}  [FAIL] 删除章节未授权: $DCH ——删除须登记ledgers/waivers.md del门(结构性重排请走arc-restructure并留审计记录)${NC}"
            FAIL=1
        fi
    done
fi

# ── C. 逃逸哨兵(新,v4): text/下无法识别的新文件(如第087章.MD之外的花样) ──
if [ -n "$TEXT_ODD" ]; then
    echo ""
    echo -e "${YELLOW}  [WARN] text/下新增了非常规文件(确认非逃逸): ${NC}"
    echo "$TEXT_ODD" | sed 's/^/    /'
fi

for CHAPTER in $NEW_CH $MOD_CH; do
    echo ""
    echo "── $CHAPTER ──"
    CH_NUM=$(echo "$CHAPTER" | grep -o '第[0-9]*章' | grep -o '[0-9]*')
    MODERN_FLAG=""
    [ -f "text/.modern" ] && MODERN_FLAG="--modern"

    # ── D1. 质量门: check.py(豁免需check门) ──
    CHECK_EXIT=$(python3 tools/check.py $MODERN_FLAG "$CHAPTER" > /tmp/check_out.txt 2>&1; echo $?)
    if [ -n "$CH_NUM" ] && waiver_registered "$CH_NUM" "check"; then
        echo -e "${YELLOW}  [WAIVER] check.py豁免(ch${CH_NUM}登记check门)${NC}"
    elif [ "$CHECK_EXIT" != "0" ]; then
        echo -e "${RED}  [FAIL] check.py未通过:${NC}"
        grep '\[FAIL\]' /tmp/check_out.txt | head -3 | sed 's/^/    /'
        FAIL=1
    else
        echo -e "${GREEN}  [PASS] check.py质量门${NC}"
    fi

    # ── D2. 场景卡门(v4: 存在性+最小内容) ──
    if [ -n "$CH_NUM" ]; then
        CARD=$(ls text/卡/*第${CH_NUM}章*.md 2>/dev/null | head -1)
        if [ -z "$CARD" ]; then
            if waiver_registered "$CH_NUM" "card"; then
                echo -e "${YELLOW}  [WAIVER] 无场景卡(ch${CH_NUM}登记card门)${NC}"
            else
                echo -e "${RED}  [FAIL] 无场景卡(text/卡/*第${CH_NUM}章*)——先走scene-card${NC}"
                FAIL=1
            fi
        elif [ ! -s "$CARD" ] || ! grep -q "第${CH_NUM}章" "$CARD" || ! grep -qE "场景型|价值|钩" "$CARD"; then
            echo -e "${RED}  [FAIL] 空壳卡/缺关键字段(需含:第${CH_NUM}章+场景型|价值|钩): $CARD${NC}"
            FAIL=1
        elif echo "$NEW_CH" | grep -q "第${CH_NUM}章" && ! grep -qE "^[-*][[:space:]]*\*{0,2}开场型\*{0,2}[:：][[:space:]]*(对话直入|动作直入|异常直入|判断句)" "$CARD"; then
            # 大审计-08/11: 25章100%时间状语开场=同构固化;新章卡必须声明开场型且非时间状语
            echo -e "${RED}  [FAIL] 新章卡缺'开场型'字段(须为:对话直入|动作直入|异常直入|判断句)——禁时间状语开场: $CARD${NC}"
            FAIL=1
        else
            echo -e "${GREEN}  [PASS] 场景卡(${CARD##*/})${NC}"
        fi
    fi

    # ── D3. 冷读记录(软门) ──
    if [ -n "$CH_NUM" ] && ! [ -e "story/audit/冷读-第${CH_NUM}章.md" ]; then
        if ! grep -q "冷读.*过\|cold-read.*pass" "$CHAPTER" 2>/dev/null; then
            echo -e "${YELLOW}  [WARN] 无冷读记录(story/audit/冷读-第${CH_NUM}章.md)——建议reader-proxy${NC}"
        fi
    fi
done

# ── E. drift调度提醒(每10章) ──
if [ -n "$NEW_CH" ]; then
    TOTAL=$(find text -regex 'text/卷[^/]*/第[0-9]*章\.[mM][dD]' | wc -l)
    if [ $((TOTAL % 10)) -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
        echo -e "${YELLOW}  [REMIND] 全书已达${TOTAL}章(10倍数)——应运行drift-audit并落盘story/audit/漂移审计-*${NC}"
    fi
fi

# ── F. 技能库一致性门(skills/为SSOT) ──
if [ -n "$SKILLS_STAGED" ]; then
    echo ""
    echo "── 技能库一致性门 ──"
    if python3 tools/skills_check.py > /tmp/sc_out.txt 2>&1; then
        echo -e "${GREEN}  [PASS] skills_check${NC}"
    else
        echo -e "${RED}  [FAIL] 技能库体检未过:${NC}"
        grep -E "^ -|问题" /tmp/sc_out.txt | head -5 | sed 's/^/    /'
        FAIL=1
    fi
fi

# ── G. .progress.json: 唯一权威=文件系统实扫。单独staged也必须过重算校验(禁早退,audits/13攻击2b) ──
if [ "$PROGRESS_STAGED" -gt 0 ] || [ -n "$CHAPTERS" ]; then
    python3 tools/gate_chapter.py --recompute >/dev/null 2>&1
    if [ "$PROGRESS_STAGED" -gt 0 ]; then
        git add .progress.json 2>/dev/null
        echo -e "${GREEN}  [PASS] .progress.json已按实扫重算并覆盖staged版本${NC}"
    else
        git add .progress.json 2>/dev/null
    fi
fi

echo ""
echo "═══════════════════════════════════════════"
if [ "$FAIL" -eq 1 ]; then
    echo -e "${RED}  ❌ 拒绝COMMIT: 存在未授权的违规(豁免=ledgers/waivers.md门级登记)${NC}"
    exit 1
else
    echo -e "${GREEN}  ✅ 质量+流程+韧性门通过${NC}"
fi
echo "═══════════════════════════════════════════"
exit 0
