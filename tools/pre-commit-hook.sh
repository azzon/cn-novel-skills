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
NEW_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /第[0-9]+章\.md$/ && (substr($2,1,5)=="text/" || index($2,"/text/")>0) && ($1=="A" || $1 ~ /^R/) {print $2}')   # W6: git mv外来稿进text/曾跳过新章全流程门
MOD_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /第[0-9]+章\.md$/ && (substr($2,1,5)=="text/" || index($2,"/text/")>0) && $1=="M" {print $2} tolower($3) ~ /第[0-9]+章\.md$/ && (substr($3,1,5)=="text/" || index($3,"/text/")>0) && $1 ~ /^R/ {print $3}')
DEL_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /第[0-9]+章\.md$/ && (substr($2,1,5)=="text/" || index($2,"/text/")>0) && $1=="D" {print $2} tolower($3) ~ /第[0-9]+章\.md$/ && (index($3,"/text/")==0) && $1 ~ /^R/ {print $2}')   # W6: R移出text/曾逃逸del门
CHAPTERS=$( { [ -n "$NEW_CH" ] && echo "$NEW_CH"; [ -n "$MOD_CH" ] && echo "$MOD_CH"; [ -n "$DEL_CH" ] && echo "$DEL_CH"; } )
SKILLS_STAGED=$(echo "$STATUS_OUT" | awk -F'\t' '$2 ~ /^(\.zcode\/skills\/|skills\/|\.claude\/skills\/)/ {print $2}')
# 脚手架门(Python单点;磨刀十三批H0修复: 失败立即exit——此前只置FAIL会被'无变更跳过'分支exit 0吞掉)
if ! python3 tools/skill_protocol.py audit-cards > /tmp/hook_scaffold.txt 2>&1; then
    cat /tmp/hook_scaffold.txt
    echo -e "${RED}  ❌ 脚手架门未过(骨架残留/缺指纹)${NC}"
    exit 1
fi
PROGRESS_STAGED=$(echo "$STATUS_OUT" | awk -F'\t' '$2 == ".progress.json"' | wc -l)
# text/下既非章节又非已知目录的新增文件(改名逃逸哨兵,audits/13攻击4)
# 红队git绕过#5: 路径逃逸——章文件必须活在某书根text/下;text/内非章节文件也拦
TEXT_ODD=$(echo "$STATUS_OUT" | awk -F'\t' '$1=="A" && $2 ~ /(^|\/)text\// && tolower($2) !~ /第[0-9]+章\.(md)$/ && $2 !~ /\/卡\// {print $2}')
STRAY_CH=$(echo "$STATUS_OUT" | awk -F'\t' '$1=="A" && tolower($2) ~ /(^|\/)第[0-9]+章\.md$/ && $2 !~ /(^|\/)text\// {print $2}')   # 红队试产修复: 锚定basename开头,否则"冷读-第001章.md"误伤

CARDS_STAGED=$(echo "$STATUS_OUT" | awk -F'\t' '$1=="A" || $1=="M" {if ($2 ~ /卡\/.*第[0-9]+章.*\.md$/ || $3 ~ /卡\/.*第[0-9]+章.*\.md$/) print $2}')
# QW-015: skills变更时自动重装三树(消灭"检测到漂移但不修复"的窗口)
if git diff --cached --name-only 2>/dev/null | grep -q "^skills/"; then
    bash tools/install_skills.sh --silent 2>/dev/null || true
fi

# 红队git绕过#1: 门自身文件被staged=hook自免攻击面——须waivers登记hookself(人审)
HOOK_SELF=$(echo "$STATUS_OUT" | awk -F'\t' '$1 ~ /^[AM]/ && ($2 ~ /^tools\/pre-commit-hook.sh$/ || $2 ~ /^\.githooks\// || $2 ~ /^tools\/(skill_protocol|check|gate_chapter|card_check|voice_check|pipeline)\.py$/) {print $2}')
HOOKSELF_OK=0
    _HS_LINE=$(grep -E "^- hookself:.*hookself" ledgers/waivers.md 2>/dev/null | tail -1)
    _HS_DATE=$(echo "$_HS_LINE" | grep -oE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" | head -1)
    case "$_HS_DATE" in 3*|2[1-9]*) _HS_DATE="" ;; esac
    if [ -n "$_HS_DATE" ] && [ "$_HS_DATE" \< "$(date +%F)" ] && [ "$_HS_DATE" \< "$(date -d '89 days ago' +%F 2>/dev/null || echo 1999-01-01)" ]; then
      : # hookself登记超90天=过期,须复验重登
    else
      HOOKSELF_OK=1   # W6: 原只验存在=一次登记永生
    fi
    if [ -n "$HOOK_SELF" ] && [ "$HOOKSELF_OK" != "1" ]; then
    echo -e "${RED}  [FAIL] 门自身文件被修改且staged: $HOOK_SELF${NC}"
    echo -e "${RED}  ——hook自免=最高危攻击面;人工复核后ledgers/waivers.md登记 '- hookself: hookself (批准:人名 日期)' 同批提交${NC}"
    exit 1
fi

if [ -z "$CHAPTERS" ] && [ -z "$SKILLS_STAGED" ] && [ "$PROGRESS_STAGED" -eq 0 ] && [ -z "$TEXT_ODD" ] && [ -z "$HOOK_SELF" ]; then
    echo -e "${GREEN}[PASS] 无章节/技能/进度变更，跳过。${NC}"
    exit 0
fi

# waiver登记制v4: 门级授权。格式: - chNNN: <门id>[;<门id>...] (日期)  门id∈{check,card,del,all}
# 一行只豁免列出的门;无门id的旧行不生效。删除章必须del门;check.py全项=check门。
waiver_registered() {  # $1=章号 $2=门id [$3=书根账路径]
    local LEDG="ledgers/waivers.md"
    [ -n "${3:-}" ] && [ -f "$3" ] && LEDG="$3"   # 清盘bug修复: set -u下$3未传参崩溃
    [ -f "$LEDG" ] || return 1
    local line
    line=$(grep -E "^- ch0?$1:" "$LEDG" 2>/dev/null | tail -1)
    [ -z "$line" ] && return 1
    # 红队20260915: waiver永不过期=后门;90天自动失效,需复验日期重登记
    WDATE=$(echo "$line" | grep -oE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" | head -1)   # W6: 原tail -1,行内附2099即永生
    [ -z "$WDATE" ] && return 1   # 红队git绕过#4: 无日期=永生后门,一律失效重登记
    case "$WDATE" in
      3*|2[1-9]*) return 1 ;;   # W6: 未来日期(21xx+/3xxx)一律无效
    esac
    if [ -n "$WDATE" ]; then
      if [ "$WDATE" \< "$(date -d '90 days ago' +%F 2>/dev/null || echo 1999-01-01)" ]; then   # W6: date失败原回退0000-00-00=fail-open永不过期
        return 1
      fi
    fi
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

# ── B0. 游离章门(红队git绕过#5: 草稿/第040章.md类零门入库)
if [ -n "$STRAY_CH" ]; then
    echo -e "${RED}  [FAIL] 章节文件逃逸text/目录: $STRAY_CH ——正文必须活在书根text/卷N/下,移入或删除${NC}"
    FAIL=1
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
    BDIR=$(dirname "$(dirname "$(dirname "$CHAPTER")")")   # 文件→卷→text→书根(主书时=".")"
    [ -f "$BDIR/text/.modern" ] && MODERN_FLAG="--modern"

    # ── D0.5 新章流程硬门(1993ch031事故: 正文可裸提,记账/记忆/填卡全跳过无拦截) ──
    # 只对新增章(status A)生效;存量章修复(M)不要求重记账。
    if [ -n "$CH_NUM" ] && git diff --cached --name-status -- "$CHAPTER" 2>/dev/null | grep -q "^A"; then
      BROOT=$(dirname "$(dirname "$(dirname "$CHAPTER")")")   # 文件→卷→text→书根(主书时=".")
      PROC_MISS=""
      # 红队git绕过#3: 流程门查staged版(index)——工作区装饰骗门根除;账/卡未staged=孤儿章
      stgrep() { git show ":$1" 2>/dev/null | grep -qs -- "$2"; }
      for led in 钩分布 时间线 数字账 人物状态; do
        stgrep "${BROOT}/ledgers/${led}.md" "第${CH_NUM}章" || PROC_MISS="$PROC_MISS $led"
      done
      stgrep "${BROOT}/ledgers/技能执行记录.md" "第${CH_NUM}章" || PROC_MISS="$PROC_MISS 技能执行记录"
      stgrep "${BROOT}/ledgers/生成记录.md" "第${CH_NUM}章" || PROC_MISS="$PROC_MISS 生成记录"
      SB_OK=0
      for sb in "${BROOT}"/圣经/*章摘要.md "${BROOT}"/ledgers/章摘要.md "${BROOT}"/故事圣经.md; do
        stgrep "${sb#./}" "第${CH_NUM}章" && SB_OK=1
      done
      [ "$SB_OK" = "0" ] && PROC_MISS="$PROC_MISS 章摘要"
      CARD_FILE=$(ls "$BROOT"/卡/*第${CH_NUM}章*.md 2>/dev/null | head -1)
      if [ -z "$CARD_FILE" ]; then
        PROC_MISS="$PROC_MISS 场景卡"
      else
        git show ":${CARD_FILE#./}" 2>/dev/null | grep -qE "（填）|（四选一|（本章全部数字事实" && PROC_MISS="$PROC_MISS 卡未填"
        git diff --cached --name-only | grep -qs -- "$CARD_FILE" || PROC_MISS="$PROC_MISS 卡未staged(孤儿章)"
      fi
      # 冷读硬门: 逢5的倍数或卷首章,新章commit必须带冷读报告(done的同款硬门,hook级前移)
      CH_NUM_INT=$((10#$CH_NUM))
      VOL_DIR=$(dirname "$CHAPTER")
      IS_VOLFIRST=0
      [ "$(ls "$VOL_DIR"/第*.md 2>/dev/null | wc -l)" = "1" ] && IS_VOLFIRST=1
      if [ $((CH_NUM_INT % 5)) -eq 0 ] || [ "$IS_VOLFIRST" = "1" ]; then
        CR_FILE=$(ls "$BROOT"/audit/冷读-第${CH_NUM}章.md "$BROOT"/audit/冷读-第${CH_NUM_INT}章.md 2>/dev/null | head -1)
        # 红队20260915: 一行文"总分:9"可伪造——三查: 存在+体量≥600B+分数≥7且非"不会翻"
        if [ -z "$CR_FILE" ]; then
          PROC_MISS="$PROC_MISS 冷读报告(硬门章)"
        elif [ "$(stat -c%s "$CR_FILE" 2>/dev/null || echo 0)" -lt 600 ]; then
          PROC_MISS="$PROC_MISS 冷读报告过薄(<600B,疑似一行文伪造)"
        else
          CR_SCORE=$(grep -oE "总分[:：][[:space:]]*\*{0,2}[0-9]+(\.[0-9])?" "$CR_FILE" | grep -oE "[0-9]+(\.[0-9])?" | head -1)
          if [ -z "$CR_SCORE" ]; then
            PROC_MISS="$PROC_MISS 冷读无总分数字"
          elif awk "BEGIN{exit !($CR_SCORE < 7)}"; then
            PROC_MISS="$PROC_MISS 冷读${CR_SCORE}分(<7,打回重写非放行)"
          elif grep -q "追读判定:[[:space:]]*不会翻" "$CR_FILE"; then
            PROC_MISS="$PROC_MISS 冷读判定不会翻"
          fi
        fi
      fi
      if [ -n "$PROC_MISS" ] && ! waiver_registered "$CH_NUM" "card" "$BROOT/ledgers/waivers.md"; then
        echo -e "${RED}  [FAIL] 新章流程硬门缺:$PROC_MISS ——记账/章摘要/填卡是commit前置件,不得事后补(1993ch031事故)${NC}"
        FAIL=1
      fi
    fi

    # ── D0. 引号三重修复(自动修+重新暂存)+声口门+卡文对账门(磨刀第七批集成:此前绕过chapter_pipeline.sh直提时三道门不生效) ──
    echo "$CHAPTER" | grep -q "\.md$" && python3 tools/fix_quotes.py "$CHAPTER" > /tmp/fq_out.txt 2>&1 && git add "$CHAPTER" 2>/dev/null
    if [ -n "$CH_NUM" ] && ! waiver_registered "$CH_NUM" "card" "$(dirname "$(dirname "$(dirname "$CHAPTER")")")/ledgers/waivers.md"; then
      VOICE_ARGS=""
      BOOKROOT=$(echo "$CHAPTER" | grep -oE '^[^/]+/text/' | cut -d/ -f1)
      if [ -n "$BOOKROOT" ] && [ -f "$BOOKROOT/声口卡.md" ]; then VOICE_ARGS="--card $BOOKROOT/声口卡.md"; fi
      VOICE_OUT=$(python3 tools/voice_check.py "$CHAPTER" $VOICE_ARGS 2>&1)
      if echo "$VOICE_OUT" | grep -q "FAIL]"; then
        echo -e "${RED}  [FAIL] 声口门(${CHAPTER}):${NC}"
        echo "$VOICE_OUT" | grep "FAIL]" | head -3 | sed 's/^/    /'
        FAIL=1
      fi
      CARD_VOL=$(echo "$CHAPTER" | grep -oE '卷[0-9]+' | grep -oE '[0-9]+')
      CARD_OUT=$(python3 tools/card_check.py "${CH_NUM}" --volume "${CARD_VOL:-1}" ${BOOKROOT:+--book $BOOKROOT} 2>&1)
      if echo "$CARD_OUT" | grep -q "FAIL]"; then
        echo -e "${RED}  [FAIL] 卡文对账(${CHAPTER}):${NC}"
        echo "$CARD_OUT" | grep "FAIL]" | head -3 | sed 's/^/    /'
        FAIL=1
      fi
    fi

    # ── D1. 质量门: check.py(豁免需check门) ──
    CHECK_EXIT=$(python3 tools/check.py $MODERN_FLAG "$CHAPTER" > /tmp/check_out.txt 2>&1; echo $?)
    if [ -n "$CH_NUM" ] && waiver_registered "$CH_NUM" "check" "$(dirname "$(dirname "$(dirname "$CHAPTER")")")/ledgers/waivers.md"; then
        echo -e "${YELLOW}  [WAIVER] check.py豁免(ch${CH_NUM}登记check门)${NC}"
    elif [ "$CHECK_EXIT" != "0" ]; then
        echo -e "${RED}  [FAIL] check.py未通过:${NC}"
        grep '\[FAIL\]' /tmp/check_out.txt | head -3 | sed 's/^/    /'
        FAIL=1
    else
        echo -e "${GREEN}  [PASS] check.py质量门${NC}"
    fi

    # ── D2. 场景卡门(v4;磨刀十八批收口: 仅当本章节文件本身staged时才查卡——设计层提交(无正文staged)不应被工作区未填卡阻断) ──
    if [ -n "$CH_NUM" ] && echo "$CHAPTER" | grep -qE "(^|/)text/"; then
        BOOKROOT=$(echo "$CHAPTER" | grep -oE '^[^/]+/text/' | cut -d/ -f1)
        if [ -n "$BOOKROOT" ]; then
            CARD=$(ls $BOOKROOT/text/卡/*第${CH_NUM}章*.md $BOOKROOT/卡/*第${CH_NUM}章*.md 2>/dev/null | head -1)
        else
            CARD=$(ls text/卡/*第${CH_NUM}章*.md 2>/dev/null | head -1)
        fi
        if [ -z "$CARD" ]; then
            if waiver_registered "$CH_NUM" "card" "$(dirname "$(dirname "$(dirname "$CHAPTER")")")/ledgers/waivers.md"; then
                echo -e "${YELLOW}  [WAIVER] 无场景卡(ch${CH_NUM}登记card门)${NC}"
            else
                echo -e "${RED}  [FAIL] 无场景卡(text/卡/*第${CH_NUM}章*)——先走scene-card${NC}"
                FAIL=1
            fi
        elif [ ! -s "$CARD" ] || ! grep -q "第${CH_NUM}章" "$CARD" || ! grep -qE "场景型|价值|钩" "$CARD"; then
            echo -e "${RED}  [FAIL] 空壳卡/缺关键字段(需含:第${CH_NUM}章+场景型|价值|钩): $CARD${NC}"
            FAIL=1
        elif grep -q "（填）" "$CARD"; then
            echo -e "${RED}  [FAIL] 骨架卡残留（填）: $CARD——scene-draft对骨架卡拒工,逐字段填完(磨刀十二批: 技能编译脚手架,填空式作业)${NC}"
            FAIL=1
        elif ! grep -q "generated-by:skill_protocol" "$CARD"; then
            echo -e "${RED}  [FAIL] 卡非脚手架产物(缺generated-by指纹): $CARD——从零手写=绕过scene-card技能;重跑: python3 tools/skill_protocol.py gen card ${CH_NUM}${NC}"
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
# W6: 工具自测从SKILLS_STAGED门内解嵌——只改tools/*.py不碰skills/时自测永不触发
if git diff --cached --name-only | grep -qE "^tools/.*\.py$"; then
      if ! python3 tools/self_test.py > /tmp/st_out.txt 2>&1; then
        echo -e "${RED}  [FAIL] 工具自测(self_test)未过——tools/*.py变更触发:${NC}"
        grep "✗" /tmp/st_out.txt | head -3 | sed 's/^/    /'
        FAIL=1
      fi
fi
# 技能库一致性门(W6: 原[self_test嵌在SKILLS_STAGED门内],现SKILLS_STAGED仍管体检;tools-only提交已由上面self_test覆盖)
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
    # 长跑回归闸(advisory,大审计-11 evals可执行化): 基线存在时跑diff
    # 红队冷读可信: 原只查主书基线=1993书基线从未被自动检查——按staged书根逐书检查
    for EVB in "$@" ; do :; done
    EV_BOOKS=""
    for BK in $(echo "$STATUS_OUT" | awk -F'\t' '{print $2}' | cut -d/ -f1 | sort -u); do
        [ -f "$BK/evals_baseline.json" ] && EV_BOOKS="$EV_BOOKS $BK"
    done
    [ -f evals_baseline.json ] && EV_BOOKS="$EV_BOOKS ."
    for BK in $EV_BOOKS; do
        EV=$(python3 tools/evals.py check $BK 2>&1 | tail -1)
        case "$EV" in
            无回归*) echo -e "${GREEN}  [PASS] evals回归(${BK}): ${EV}${NC}" ;;
            *) echo -e "${YELLOW}  [WARN] evals回归(${BK}): ${EV}${NC}" ;;
        esac
    done
fi
echo "═══════════════════════════════════════════"
exit 0
