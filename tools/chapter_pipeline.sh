#!/bin/bash
# chapter_pipeline.sh 单章确定性生产流水线
# 用法: bash tools/chapter_pipeline.sh <章号> [skip_draft]
# 自动执行: 质检→修复→结构门→evals→台账提醒→时刻卡提醒→验收→提交
# 人工只负责: 写场景卡→写正文→审阅

set -e

N=$1
SKIP_DRAFT=${2:-}
NN=$(printf "%03d" $N)

# 多书隔离(docs/多书隔离协议.md): BOOK_ROOT 环境变量指书根; 默认仓库根=主书
# 用法: BOOK_ROOT=法医秦见微 bash tools/chapter_pipeline.sh 2
BOOK_ROOT=${BOOK_ROOT:-.}
# 找文件
VOL=""
for v in 卷1 卷2 卷3; do
  if [ -f "$BOOK_ROOT/text/$v/第${NN}章.md" ]; then VOL=$v; break; fi
done
if [ -z "$VOL" ]; then echo "❌ 第${NN}章文件不存在($BOOK_ROOT/text/)"; exit 1; fi
FILE="$BOOK_ROOT/text/$VOL/第${NN}章.md"
CARD=$(ls $BOOK_ROOT/text/卡/*第${NN}章*.md $BOOK_ROOT/卡/*第${NN}章*.md 2>/dev/null | head -1)
# 声口卡: 书根有则用书根的(多书隔离)
VOICE_ARGS=""
if [ -f "$BOOK_ROOT/声口卡.md" ] && [ "$BOOK_ROOT" != "." ]; then VOICE_ARGS="--card $BOOK_ROOT/声口卡.md"; fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  第${NN}章 生产流水线 (${VOL})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: 场景卡检查 ──
echo ""
echo "▶ Step 1: 场景卡检查"
if [ -z "$CARD" ]; then
  echo "  ❌ 场景卡不存在——先走scene-card"
  exit 1
fi
echo "  ✅ $CARD"

# ── Step 2: 引号三重修复(直引号/弯引号方向/反向对——法医ch001事故管线化) ──
echo ""
echo "▶ Step 2: 引号三重修复"
python3 tools/fix_quotes.py "$FILE"

# ── Step 3: check.py 质量门 ──
echo ""
echo "▶ Step 3: check.py 质量门"
CHECK_OUT=$(python3 tools/check.py --modern "$FILE" 2>&1)
CHECK_STATUS=$(echo "$CHECK_OUT" | tail -1)
FAIL_COUNT=$(echo "$CHECK_OUT" | grep -o "FAIL [0-9]*章" | grep -o "[0-9]*" | tail -1)
echo "  $CHECK_STATUS"
if [ "$FAIL_COUNT" != "0" ] && [ -n "$FAIL_COUNT" ]; then
  echo "  ❌ check.py有${FAIL_COUNT}个FAIL:"
  echo "$CHECK_OUT" | grep "FAIL\]" | head -5 | sed 's/^/     /'
  echo "  → 修复后重新运行本脚本"
  exit 1
fi

# ── Step 3b: 声口卡禁词门 + 场景卡数字对账(法医ch001/主书ch007事故管线化) ──
echo ""
echo "▶ Step 3b: 声口门+数字对账"
VOICE_OUT=$(python3 tools/voice_check.py "$FILE" $VOICE_ARGS 2>&1)
if echo "$VOICE_OUT" | grep -q "FAIL]"; then
  echo "  ❌ 声口门FAIL:"
  echo "$VOICE_OUT" | grep "FAIL]" | head -4 | sed 's/^/     /'
  exit 1
fi
echo "  ✅ 声口门PASS"
CARD_NUM=$(echo "$CARD" | grep -o "第[0-9]*章" | grep -o "[0-9]*" | head -1)
CARD_VOL=$(echo "$VOL" | grep -o "[0-9]*")
CARD_OUT=$(python3 tools/card_check.py "${CARD_NUM:-$N}" --volume "${CARD_VOL:-1}" 2>&1 || true)
echo "  $CARD_OUT" | grep -E "WARN|FAIL|对上" | head -3 | sed 's/^/     /'

# ── Step 4: gate_chapter 韧性门 ──
echo ""
echo "▶ Step 4: gate_chapter 韧性门"
MODE="modified"
git diff --cached --name-only 2>/dev/null | grep -q "第${NN}章" && MODE="new"
GATE_OUT=$(python3 tools/gate_chapter.py "$MODE" "$FILE" 2>&1)
if echo "$GATE_OUT" | grep -q "FAIL"; then
  echo "  ❌ gate_chapter FAIL:"
  echo "$GATE_OUT" | grep "FAIL\]" | head -3 | sed 's/^/     /'
  exit 1
fi
echo "  ✅ gate_chapter PASS"

# ── Step 5: 台账检查 ──
echo ""
echo "▶ Step 5: 台账盖章检查"
MISSING_LEDGERS=""
for ledger in 伏笔 梗 钩分布 类型轮换 人物状态 线弦 时间线; do
  LP="ledgers/${ledger}.md"
  if [ -f "$LP" ] && ! grep -q "第${NN}章" "$LP" 2>/dev/null; then
    MISSING_LEDGERS="${MISSING_LEDGERS} ${ledger}"
  fi
done
if [ -n "$MISSING_LEDGERS" ]; then
  echo -e "  ⚠ 未盖章:${MISSING_LEDGERS}——请先运行ledger-update"
else
  echo "  ✅ 台账已盖章"
fi

# ── Step 6: 章摘要检查 ──
echo ""
echo "▶ Step 6: 章摘要检查"
if [ -f "story/60-圣经/章摘要.md" ] && grep -q "| ${NN} |" "story/60-圣经/章摘要.md" 2>/dev/null; then
  echo "  ✅ 章摘要已更新"
else
  echo -e "  ⚠ 章摘要缺第${NN}章条目"
fi

# ── Step 7: 当前时刻卡检查 ──
echo ""
echo "▶ Step 7: 当前时刻卡检查"
if [ -f "ledgers/当前时刻卡.md" ] && grep -q "第${NN}章" "ledgers/当前时刻卡.md" 2>/dev/null; then
  echo "  ✅ 当前时刻卡已更新"
else
  echo -e "  ⚠ 当前时刻卡未更新——请更新下一章指向和上一章末拍"
fi

# ── Step 8: evals回归 ──
echo ""
echo "▶ Step 8: evals回归"
if [ -f "evals_baseline.json" ]; then
  EVALS=$(python3 tools/evals.py check 2>&1 | tail -1)
  if echo "$EVALS" | grep -q "无回归"; then
    echo "  ✅ $EVALS"
  else
    echo -e "  ⚠ $EVALS"
  fi
else
  echo "  ⚠ 无evals基线——运行 python3 tools/evals.py record"
fi

# ── 汇总 ──
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  第${NN}章 流水线完成"
echo "  下一步: python3 tools/pipeline.py done ${N}"
echo "  然后: git add -A && git commit && git push"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
