#!/bin/bash
# pre-commit hook v3: 质量门 + 流程合规门 + 韧性门(进度/查重/卷归属)
# 安装: cp tools/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# v3变更(audits/06,10): quotepath修复(默认配置下CJK路径转义导致全门失效)、
#   fail-closed、章号/标题/跨章查重、卷归属校验、字数硬底线、waiver登记制、
#   场景卡强制(取消/tmp三振)、drift文件名修复、progress.json自动重算、技能库一致性门
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
FAIL=0

echo "═══════════════════════════════════════════"
echo "  PRE-COMMIT v3: 质量+流程+韧性门"
echo "═══════════════════════════════════════════"

# quotepath=false: 否则默认配置下CJK路径被八进制转义,下面所有匹配全部失灵(audit06-P0)
if ! STAGED_ALL=$(git -c core.quotepath=false diff --cached --name-only --diff-filter=ACM 2>/tmp/gate_git_err.txt); then
    echo -e "${RED}[FAIL] git diff失败( fail-closed ): $(cat /tmp/gate_git_err.txt)${NC}"
    exit 1
fi

CHAPTERS=$(echo "$STAGED_ALL" | grep -E '^text/卷[^/]+/第[0-9]+章\.md$' || true)
NEW_CH=$(git -c core.quotepath=false diff --cached --name-only --diff-filter=A | grep -E '^text/卷[^/]+/第[0-9]+章\.md$' || true)
MOD_CH=$(git -c core.quotepath=false diff --cached --name-only --diff-filter=M | grep -E '^text/卷[^/]+/第[0-9]+章\.md$' || true)
SKILLS_STAGED=$(echo "$STAGED_ALL" | grep -E '^(skills/|\.zcode/skills/|\.claude/skills/)' || true)

if [ -z "$CHAPTERS" ] && [ -z "$SKILLS_STAGED" ]; then
    echo -e "${GREEN}[PASS] 无章节/技能变更，跳过。${NC}"
    exit 0
fi

# ── S. 技能库一致性门(skills/为SSOT;三树漂移即拒) ──
if [ -n "$SKILLS_STAGED" ]; then
    echo ""
    echo "── 技能库一致性门 ──"
    if python3 tools/skills_check.py; then
        echo -e "${GREEN}  [PASS] skills_check${NC}"
    else
        echo -e "${RED}  [FAIL] 技能库体检未过(结构/路由/三树漂移)${NC}"
        FAIL=1
    fi
fi

# waiver登记制: 正文里的"waiver:"字符串不再有豁免力,必须登记在 ledgers/waivers.md
waiver_registered() {  # $1=章号
    [ -f ledgers/waivers.md ] && grep -Eq "^- ch0?$1:" ledgers/waivers.md
}

# ── A. 韧性门(整批一次: 章号重复/标题重复/卷归属/跨章查重/字数硬底线) ──
GATE_INPUT=""
[ -n "$NEW_CH" ] && GATE_INPUT="$GATE_INPUT new $NEW_CH"
[ -n "$MOD_CH" ] && GATE_INPUT="$GATE_INPUT modified $MOD_CH"
if [ -n "$NEW_CH" ] || [ -n "$MOD_CH" ]; then
    GATE_EXIT=$(python3 tools/gate_chapter.py $GATE_INPUT > /tmp/gate_ch_out.txt 2>&1; echo $?)
    echo ""
    echo "── 韧性门(章号/标题/卷归属/跨章查重/字数) ──"
    if [ "$GATE_EXIT" != "0" ]; then
        echo -e "${RED}  [FAIL] 韧性门未过:${NC}"
        grep '\[FAIL\]' /tmp/gate_ch_out.txt | head -6 | sed 's/^/    /'
        FAIL=1
    else
        echo -e "${GREEN}  [PASS] staged全部章节通过${NC}"
        grep '\[WARN\]' /tmp/gate_ch_out.txt | sort | uniq -c | sed 's/^/    /'
    fi
fi

for CHAPTER in $CHAPTERS; do
    echo ""
    echo "── $CHAPTER ──"
    CH_NUM=$(echo "$CHAPTER" | grep -o '第[0-9]*章' | grep -o '[0-9]*')
    MODERN_FLAG=""
    [ -f "text/.modern" ] && MODERN_FLAG="--modern"

    # ── B. 质量门: check.py ──
    CHECK_EXIT=$(python3 tools/check.py $MODERN_FLAG "$CHAPTER" > /tmp/check_out.txt 2>&1; echo $?)
    if [ -n "$CH_NUM" ] && waiver_registered "$CH_NUM"; then
        echo -e "${YELLOW}  [WAIVER] check.py豁免(登记制)${NC}"
    elif [ "$CHECK_EXIT" != "0" ]; then
        echo -e "${RED}  [FAIL] check.py未通过:${NC}"
        grep '\[FAIL\]' /tmp/check_out.txt | head -3 | sed 's/^/    /'
        FAIL=1
    else
        echo -e "${GREEN}  [PASS] check.py质量门${NC}"
    fi

    # ── C1. 场景卡强制门(单票FAIL;豁免走登记) ──
    if [ -n "$CH_NUM" ]; then
        CARDS=$(ls text/卡/*第${CH_NUM}章*.md 2>/dev/null | wc -l)
        if [ "$CARDS" -eq 0 ]; then
            if waiver_registered "$CH_NUM"; then
                echo -e "${YELLOW}  [WAIVER] 无场景卡(已登记)${NC}"
            else
                echo -e "${RED}  [FAIL] 无场景卡(text/卡/*第${CH_NUM}章*)——先走scene-card,确无则登记ledgers/waivers.md${NC}"
                FAIL=1
            fi
        else
            echo -e "${GREEN}  [PASS] 场景卡(${CARDS}张)${NC}"
        fi
    fi

    # ── C2. 冷读记录(软门) ──
    if [ -n "$CH_NUM" ]; then
        COLD_READ=$(grep -l "第${CH_NUM}章.*冷读\|冷读.*第${CH_NUM}章" ledgers/*.md story/audit/*.md 2>/dev/null | head -1)
        if [ -z "$COLD_READ" ] && ! grep -q "冷读.*过\|cold-read.*pass" "$CHAPTER" 2>/dev/null; then
            echo -e "${YELLOW}  [WARN] 无冷读记录(建议reader-proxy)${NC}"
        else
            echo -e "${GREEN}  [PASS] 冷读记录${NC}"
        fi
    fi

done

# ── C3. drift调度提醒(修复:实际文件名为"漂移审计-*";旧代码找drift-*永不命中) ──
if [ -n "$CHAPTERS" ]; then
    TOTAL=$(find text -regex 'text/卷[^/]*/第[0-9]*章\.md' | wc -l)
    if [ $((TOTAL % 10)) -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
        RECENT_DRIFT=$(find story/audit -name "漂移审计-*" -newer "$(echo "$CHAPTERS" | head -1)" 2>/dev/null | head -1)
        if [ -z "$RECENT_DRIFT" ]; then
            echo -e "${YELLOW}  [REMIND] 全书已达${TOTAL}章(10倍数)——应运行drift-audit${NC}"
        fi
    fi
fi

# ── D. .progress.json 重算(文件系统唯一权威;禁手写) ──
if [ -n "$CHAPTERS" ]; then
    python3 tools/gate_chapter.py --recompute >/dev/null && git add .progress.json 2>/dev/null
    echo -e "${GREEN}  [PASS] .progress.json已重算并入库${NC}"
fi

echo ""
echo "═══════════════════════════════════════════"
if [ "$FAIL" -eq 1 ]; then
    echo -e "${RED}  ❌ 拒绝COMMIT: 存在未豁免的违规(豁免=登记ledgers/waivers.md)${NC}"
    exit 1
else
    echo -e "${GREEN}  ✅ 质量+流程+韧性门通过${NC}"
fi
echo "═══════════════════════════════════════════"
exit 0
