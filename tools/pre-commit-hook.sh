#!/bin/bash
# pre-commit hook: 焊在git里的质量门
# 安装: cp tools/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e
cd "$(git rev-parse --show-toplevel)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'

echo "═══════════════════════════════════════════"
echo "  PRE-COMMIT QUALITY GATE"
echo "═══════════════════════════════════════════"

# 1. 检查新增/修改的章节文件（用python处理中文字符更可靠）
STAGED_CHAPTERS=$(git diff --cached --name-only --diff-filter=ACM | python3 -c "
import sys, re
for line in sys.stdin:
    line = line.strip()
    if re.match(r'^text/.+第.+章\.md$', line):
        print(line)
" || true)

if [ -z "$STAGED_CHAPTERS" ]; then
    echo -e "${GREEN}[PASS] 无新章节文件，跳过章节质量门。${NC}"
    exit 0
fi

FAIL_COUNT=0
WARN_COUNT=0

for CHAPTER in $STAGED_CHAPTERS; do
    echo ""
    echo "── 检查: $CHAPTER ──"

    # 1a. 运行check.py
    CHECK_RESULT=$(python3 tools/check.py "$CHAPTER" 2>&1)
    CHECK_EXIT=$?

    if [ $CHECK_EXIT -ne 0 ]; then
        # 有FAIL项
        echo -e "${RED}  [FAIL] check.py检测未通过:${NC}"
        echo "$CHECK_RESULT" | grep '\[FAIL\]' | head -5 | sed 's/^/    /'
        FAIL_COUNT=$((FAIL_COUNT + 1))

        # 检查是否有waiver标记
        if grep -q "waiver:" "$CHAPTER" 2>/dev/null; then
            WAIVER_REASON=$(grep "waiver:" "$CHAPTER" | head -1 | cut -d: -f2-)
            echo -e "${YELLOW}  [WAIVER] 此章已标记豁免: $WAIVER_REASON${NC}"
            echo -e "${YELLOW}  豁免章节将在下次红队审计中优先检查。${NC}"
        else
            echo -e "${RED}  此章未标记豁免。修复FAIL项后在commit，或在文件头部添加: <!-- waiver: 原因 -->${NC}"
        fi
    elif echo "$CHECK_RESULT" | grep -q '\[WARN\]'; then
        echo -e "${YELLOW}  [WARN] 有警告项(不阻塞):${NC}"
        echo "$CHECK_RESULT" | grep '\[WARN\]' | head -3 | sed 's/^/    /'
        WARN_COUNT=$((WARN_COUNT + 1))
    else
        echo -e "${GREEN}  [PASS] check.py全项通过。${NC}"
    fi

    # 1b. 检查是否有验收标记（场景文件）
    if echo "$CHAPTER" | grep -q "场景"; then
        if ! grep -q "<!-- 验收: 过 -->" "$CHAPTER" 2>/dev/null; then
            echo -e "${RED}  [FAIL] 场景文件缺少验收标记${NC}"
            FAIL_COUNT=$((FAIL_COUNT + 1))
        fi
    fi
done

# 2. 每10章触发drift-audit提醒
TOTAL_CHAPTERS=$(ls text/卷*/第*章.md 2>/dev/null | grep -v 场景 | wc -l)
if [ $((TOTAL_CHAPTERS % 10)) -eq 0 ] && [ $TOTAL_CHAPTERS -gt 0 ]; then
    LAST_DRIFT=$(ls story/audit/drift-* 2>/dev/null | tail -1)
    if [ -z "$LAST_DRIFT" ]; then
        echo -e "${YELLOW}  [REMINDER] 已写${TOTAL_CHAPTERS}章(10的倍数)，尚无drift审计记录。${NC}"
        echo -e "${YELLOW}  建议运行: drift-audit${NC}"
    fi
fi

# 3. 最终裁决
echo ""
echo "═══════════════════════════════════════════"
if [ $FAIL_COUNT -gt 0 ]; then
    echo -e "${RED}  拒绝COMMIT: ${FAIL_COUNT}章有未豁免的FAIL项。${NC}"
    echo -e "${RED}  修复后重试，或添加waiver标记。${NC}"
    echo "═══════════════════════════════════════════"
    exit 1
else
    echo -e "${GREEN}  质量门通过: FAIL=0, WARN=${WARN_COUNT}${NC}"
    echo "═══════════════════════════════════════════"
    exit 0
fi
