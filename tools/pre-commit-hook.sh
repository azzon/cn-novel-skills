#!/bin/bash
# pre-commit hook v2: 质量门 + 流程合规门
# 安装: cp tools/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit

set -e
cd "$(git rev-parse --show-toplevel)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
FAIL=0

echo "═══════════════════════════════════════════"
echo "  PRE-COMMIT: 质量门 + 流程合规门"
echo "═══════════════════════════════════════════"

# 获取新增/修改的章节文件
STAGED=$(git diff --cached --name-only --diff-filter=ACM | python3 -c "
import sys, re
for line in sys.stdin:
    line = line.strip()
    if re.match(r'^text/.+第.+章\.md$', line):
        print(line)
" || true)

if [ -z "$STAGED" ]; then
    echo -e "${GREEN}[PASS] 无新章节，跳过。${NC}"
    exit 0
fi

for CHAPTER in $STAGED; do
    echo ""
    echo "── $CHAPTER ──"

    # ── A. 质量门: check.py ──
    CHECK_EXIT=$(python3 tools/check.py "$CHAPTER" > /tmp/check_out.txt 2>&1; echo $?)
    if [ "$CHECK_EXIT" != "0" ]; then
        if grep -q "waiver:" "$CHAPTER" 2>/dev/null; then
            echo -e "${YELLOW}  [WAIVER] check.py有FAIL但已豁免${NC}"
        else
            echo -e "${RED}  [FAIL] check.py未通过:${NC}"
            grep '\[FAIL\]' /tmp/check_out.txt | head -3 | sed 's/^/    /'
            FAIL=1
        fi
    else
        echo -e "${GREEN}  [PASS] check.py质量门${NC}"
    fi

    # ── B. 流程合规门 ──

    # B1. 场景卡存在性检查
    CH_NUM=$(echo "$CHAPTER" | python3 -c "
import sys, re
line = sys.stdin.read().strip()
m = re.search(r'第(\d+)章', line)
print(m.group(1) if m else '')
")
    VOL=$(echo "$CHAPTER" | python3 -c "
import sys, re
line = sys.stdin.read().strip()
m = re.search(r'(卷.+?)/', line)
print(m.group(1) if m else '')
")

    if [ -n "$CH_NUM" ]; then
        CARD_PATTERN="text/卡/*${CH_NUM}*"
        CARDS=$(ls $CARD_PATTERN 2>/dev/null | wc -l)

        if [ "$CARDS" -eq 0 ]; then
            if grep -q "no-card:" "$CHAPTER" 2>/dev/null; then
                echo -e "${YELLOW}  [WAIVER] 无场景卡但已标记${NC}"
            else
                echo -e "${YELLOW}  [WARN] 无场景卡(首次违规不阻塞,连续3次将阻塞)${NC}"
                echo "$CHAPTER" >> /tmp/no_card_log.txt
                NO_CARD_COUNT=$(grep -c . /tmp/no_card_log.txt 2>/dev/null || echo 0)
                if [ "$NO_CARD_COUNT" -ge 3 ]; then
                    echo -e "${RED}  [FAIL] 连续${NO_CARD_COUNT}章无场景卡——流程违规${NC}"
                    FAIL=1
                fi
            fi
        else
            echo -e "${GREEN}  [PASS] 场景卡(${CARDS}张)${NC}"
            # 清除计数
            rm -f /tmp/no_card_log.txt
        fi
    fi

    # B2. 冷读记录检查（查台账或专用文件）
    if [ -n "$CH_NUM" ]; then
        COLD_READ=$(grep -l "第${CH_NUM}章.*冷读\|冷读.*第${CH_NUM}章" ledgers/*.md story/audit/*.md 2>/dev/null | head -1)
        if [ -z "$COLD_READ" ]; then
            # 检查章文件内是否有冷读标记
            if grep -q "冷读.*过\|cold-read.*pass" "$CHAPTER" 2>/dev/null; then
                echo -e "${GREEN}  [PASS] 冷读标记${NC}"
            else
                echo -e "${YELLOW}  [WARN] 无冷读记录(建议运行reader-proxy)${NC}"
            fi
        else
            echo -e "${GREEN}  [PASS] 冷读记录存在${NC}"
        fi
    fi

    # B3. Drift-audit调度检查（每10章）
    TOTAL=$(ls text/卷*/第*章.md 2>/dev/null | python3 -c "
import sys, re
count = 0
for line in sys.stdin:
    if '场景' not in line:
        count += 1
print(count)
")
    if [ $((TOTAL % 10)) -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
        RECENT_DRIFT=$(find story/audit -name "drift-*" -newer "$CHAPTER" 2>/dev/null | head -1)
        if [ -z "$RECENT_DRIFT" ]; then
            echo -e "${YELLOW}  [REMIND] 第${TOTAL}章(10倍数)——应运行drift-audit${NC}"
        fi
    fi

done

echo ""
echo "═══════════════════════════════════════════"
if [ "$FAIL" -eq 1 ]; then
    echo -e "${RED}  ❌ 拒绝COMMIT: 存在未豁免的违规${NC}"
    exit 1
else
    echo -e "${GREEN}  ✅ 质量门+流程门通过${NC}"
fi
echo "═══════════════════════════════════════════"
