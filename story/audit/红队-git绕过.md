# 红队报告: git级绕过与多书并行(2026-09-15)

> 对象: `.git/hooks/pre-commit`(转发`tools/pre-commit-hook.sh`)+`.git/hooks/commit-msg`+全部门工具。
> 方法: `git clone`本仓库到`/tmp/rt/repo`,重装同款hooks,全部实验在clone中进行(证据commit均为clone内hash,不污染真库)。
> 每项结论均有实测,未做纸面推断。

---

## 一、成立的绕法(按危险排序)

### B1【最危险】hook自免: 改弱门脚本,门给自己放行
- **实测**: 把`tools/pre-commit-hook.sh`整体替换为`#!/bin/bash\nexit 0`(296行→2行),`git add`后提交该修改——**零阻力通过**(输出"[PASS] 无章节/技能/进度变更，跳过")。随后1字节垃圾章在弱hook下入库。
- 证据commit: `9bade79`(弱hook自提交)→`890a5d1`(弱hook下垃圾章入库)。
- **根因**:
  1. hook第28行`SKILLS_STAGED`只匹配`.zcode/skills/|skills/|.claude/skills/`,**`tools/`变更不触发任何门**(self_test只在SKILLS_STAGED非空时跑);
  2. 第40行早退条件`[ -z "$CHAPTERS" ] && [ -z "$SKILLS_STAGED" ] && [ $PROGRESS_STAGED -eq 0 ] && [ -z "$TEXT_ODD" ]`——纯tools提交直接exit 0;
  3. shim是**live转发**(`exec bash $(git rev-parse --show-toplevel)/tools/pre-commit-hook.sh`),改弱工作区版本的**下一次commit立即生效**,连"安装时快照"的缓冲都没有;
  4. 无pre-push/无server-side/无CI复核,git tracked≠有人审diff。
- **谁该报警**: 没有任何机制。这是当前体系最大的单点。

### B2 `--no-verify`/`-n`裸提交 + 事后审计自动降级
- **实测**: 垃圾第033章`git commit --no-verify`直接入库(证据`8b772e3`),pre-commit与commit-msg同时被跳过。
- **检测面实测**(这是重点):
  - `pipeline.py done 33`对已提交章自动转**后验模式**(`is_committed`为真→`revise=True`)——缺卡/无冷读/八账未盖章/无章摘要**全部降为WARN**,唯一FAIL来自check.py内容质量。内容合格即零拦截。
  - `is_committed()`(tools/pipeline.py:98)用`git status --porcelain -- <path>`判定——**工作区视角**,与"该commit是否经过门"完全无关。门是否跑过在git历史里零痕迹(无note/无标记)。
- 结论: `--no-verify`后,流程审计层面**无任何检测**,只剩内容级(check.py)兜底。

### B3 工作区欺骗全家桶: 流程门查的是工作区文本,不是staged内容
hook的D0.5新章流程硬门(第122-160行)对账本/章摘要/卡/冷读全部`grep 工作区文件`,且只查**字符串包含**。攻击成本=往6个账本各append一行注释:

| 欺骗项 | 实测操作 | 结果 |
|---|---|---|
| 四账+技能执行记录+生成记录 | `printf '<!-- 第033章 第034章 第035章 -->' >> ledgers/<六账>.md` | "[FAIL] 新章流程硬门缺:钩分布 时间线…"**整行消失** |
| 章摘要 | 圣经/章摘要.md追加`## 第033章 占位` | 通过 |
| 场景卡指纹 | 手写卡,伪造`generated-by:skill_protocol`+`场景型/价值/钩/开场型`四字段 | **`[PASS] 场景卡`**——指纹是纯字符串,手写即伪造 |
| 冷读三查 | 900B手写报告,`总分: 9`+`追读判定: 会翻` | 第035章(5倍数硬门章)**全绿入库**(证据`cdea2e6`)——三查(体量/分数/判定)全部只认表面格式 |
| 质量豁免 | waivers.md加无日期行`- ch033: check` | 160处明喻+13处复读的垃圾章**全门通过**(证据`9efdf0f`) |

- **部分staged终态**: 该commit(`9efdf0f`)只含正文+waivers两个文件——账本预埋/假卡/假冷读全部留在工作区**永不入库**。git历史里章是"孤儿"(无账无卡无摘要),门当时全绿。拆分提交攻击(commit1正文→commit2账)反而不必要: 单次部分staged即达同样效果。
- 附带发现: commit-msg对多章staged**任一匹配即放行**(证据`e62fc57`一次带入033/034两章,信息只含"第033章")。

### B4 waiver后门: 无日期永生 + 静默植入
- **实测**:
  - 无日期行`- ch033: check`: 90天过期校验的代码是`if [ -n "$WDATE" ]`——**没日期就完全不校验**,永生豁免(bash验证`SKIPPED(永不校验)`)。
  - waiver-only提交(夹带`- ch40: all (2020-01-01)`等后门行)零阻力入库(证据`e34d67e`)——waivers.md变更不触发任何门。
  - waiver读取同样是**工作区视角**: 不必提交,工作区写一行即豁免。
  - 解析脆弱: waivers.md末行无换行时,`>>`追加会拼进旧行,`^- ch0?N:`行首锚失配(实测踩中)——反方向说明该文件格式无schema校验。
- 有日期且>90天→正确失效(EXPIRED-OK,防御侧这段是好的)。

### B5 路径逃逸: 章文件挪出`text/`=全门失效
| 变体 | 实测 | 结果 |
|---|---|---|
| 多书内改名 | `1993南下的船票/text/卷2/ch34.md` | 入库,**连WARN都没有**(证据`895396e`)——TEXT_ODD哨兵正则是`$2 ~ /^text\//`,只匹配**主书**顶层text/,多书路径`书根/text/...`完全不进哨兵 |
| 书根下草稿目录 | `1993南下的船票/草稿/第040章.md`(181行整章) | 零警告入库(证据`4f28d23`) |
| 无text/书根 | `法医秦见微/第001章.md`(该书**没有text/子目录**,ls实证) | 零门入库(证据`9f01c6a`) |
| 主书text/哨兵 | `text/ch99.md`(主书) | 仅`[WARN]`黄色提示,**不拦截**,commit照常成功(证据`a488591`) |

- 所有章节正则(hook第24-26行、commit-msg第6行)都锚定`text/`(或`/text/`)——正文一旦不在该结构下,从pre-commit到done全链路失明。

### B6 hook本体无完整性校验
- **实测**: `rm .git/hooks/pre-commit`后,1字节章文件入库(证据`fb15add`)。commit-msg只查提交信息含章号,信息补上"第033章"即过。**删除/替换.git/hooks/下任何东西,无任何报警**。
- `.git/`不入库,core.hooksPath未设防——本地hook是"君子协定"。

### B7 多书并行: progress跨书污染+多书机制缺位(无数据互踩)
- **实测1(跨书污染)**: 主书`text/卷1/第001章.md`(untracked,**从未add**)存在时,任何触发G段的提交会`--recompute`根progress(max=1)并`git add`搭车入库(证据`ed33ed7`: 名为"1993书账本维护"的commit夹带主书progress变更)。
- **实测2(多书缺位)**: `gate_chapter.py --recompute`的`PROGRESS = ROOT/.progress.json`硬编码+`chapter_files()`只扫主书text/——**1993书的32章进度在progress里完全不体现**(全0)。
- **实测3(并行安全)**: 双worktree并行commit两个必然FAIL的提交——**均正确FAIL**。门判定全部基于exit code(即时),`/tmp/check_out.txt`等固定路径的竞争只影响显示层,不产生误放行(fail-closed保持,这是防御做得对的地方)。
- BOOKROOT推断: hook用纯路径正则`^[^/]+/text/`,gate_chapter要求书根下`text/`实存——`法医秦见微/`当前无text/,一旦在其下直接放章文件即落入B5变体。两处判定逻辑不一致。
- hook多书硬编码残留: D3冷读软门查`story/audit/`(主书路径,不查$BROOT);E段drift只`find text`(主书)。

### B8 symlink: mode无检查,门读目标(条件性成立)
- **实测**: 章文件symlink以**mode 120000**入库,`git ls-files -s`实证;check.py/gate读的是链接**目标**内容(check PASS)——"被检内容≠入库内容"的分离在机制上成立。
- 但独立使用会被误拦: 书外目标经`p.resolve()`后`book_root()`回退主书(空库)→G2b"超前"FAIL(误拦方向,fail-closed)。需组合B3摆件+书内草稿目标才成完整链。`book_root()`对resolve的脆弱性本身值得修。

### E13附注: 门信号与库内容脱钩(豁免组合下的终态)
- **实测**: `- ch036: check;g1`+注释账本+假卡下,1行垃圾("垃圾一行")入库,门输出"staged全部章节通过/PASS 场景卡/✅ 全门通过"(commit在clone内)。章文件的staged/工作区TOCTOU本身被D0的`fix_quotes && git add`(re-add工作区版)意外堵住——fix_quotes几乎恒exit 0,成功即re-add;失败(文件缺失)则check也会失败。真正的脱钩来自**豁免短路+摆件**,不是staged分离。

---

## 二、实测不成立的绕法(防御到位项)

| 绕法 | 实测结果 |
|---|---|
| 大小写`第034章.MD` | hook第24-26行`tolower($2)`覆盖,**被拦**(check+流程门全FAIL) |
| `git add -N` + `git commit -am` | `-a`先把i-t-a文件完整stage,hook可见并拦截 |
| `git commit <untracked路径>`(pathspec) | git自身报错"pathspec did not match" |
| 拆分提交(commit1正文) | 会被流程硬门拦(摆件不足时);摆件足时单次部分staged即漏(归入B3),无需拆分 |
| 并行commit互踩tmp | 判定全用exit code,双worktree并行均正确FAIL,仅显示层理论串扰 |
| G2b跳章/G4卷归属/G5跨章查重 | 在正常路径上全部有效拦截(实验中多次被它们拦下,包括工作区untracked章也被扫进corpus) |

---

## 三、防御补丁(按优先级)

### P0-1 堵hook自免(对B1/B6,最高优先)
`tools/pre-commit-hook.sh`第18-21行(diff --cached之后)插入:
```bash
# 门自身变更=须显式豁免(红队20260915 B1: 弱化hook可零阻力自提交)
HOOK_SELF=$(echo "$STATUS_OUT" | awk -F'\t' '$2 ~ /^tools\/(pre-commit-hook|commit-msg-hook|gate_chapter|check|card_check|voice_check|skill_protocol|pipeline)\.(sh|py)$/ {print $2}')
if [ -n "$HOOK_SELF" ]; then
    grep -qs "^- hookself: allow" ledgers/waivers.md || {
        echo -e "${RED}[FAIL] 提交修改了门/hook自身: $HOOK_SELF——在ledgers/waivers.md登记'- hookself: allow (日期)'并说明理由后重试${NC}"; exit 1; }
fi
```
同时把第40行早退条件追加`&& [ -z "$HOOK_SELF" ]`。另: 用`git config core.hooksPath .githooks`把hooks搬进**受门管辖的库内目录**(shim本身入库,删改可被上述检查看见)。

### P0-2 流程门从"工作区grep"改为"staged内容"(对B3,根治)
`pre-commit-hook.sh` D0.5(第122-160行)检查对象改为index:
```bash
for led in 钩分布 时间线 数字账 人物状态; do
    if git cat-file -e ":$BROOT/ledgers/${led}.md" 2>/dev/null; then
        git show ":$BROOT/ledgers/${led}.md" | grep -qs "第${CH_NUM}章" || PROC_MISS="$PROC_MISS $led(未随本commit入库)"
    else
        PROC_MISS="$PROC_MISS $led(未staged)"
    fi
done
# 卡/冷读/章摘要同理用 git show :path;检查通过后像progress一样强制 git add(前置件必须随章入库)
```
最低成本版: D0.5检查通过后追加`git add "$BROOT/ledgers" "$CARD_FILE" "$CR_FILE" 2>/dev/null`,强制账/卡/冷读随章入库,消灭"孤儿章"。

### P0-3 waiver无日期=失效(对B4,一行改动)
第55-60行改为:
```bash
WDATE=$(echo "$line" | grep -oE "20[0-9]{2}-[0-9]{2}-[0-9]{2}" | tail -1)
[ -z "$WDATE" ] && return 1                    # 无日期=永生后门,直接失效
if [ "$WDATE" \< "$(date -d '90 days ago' +%F 2>/dev/null || echo 0000-00-00)" ]; then return 1; fi
```
外加: waivers.md自身staged时打YELL0W提醒(变更可审计)。

### P1 路径哨兵全库化(对B5)
- 第37行TEXT_ODD正则`/^text\//`改为`/(^|\/)text\//`(覆盖多书),并保留卡目录豁免;
- 新增任意位置章文件检查:
```bash
STRAY_CH=$(echo "$STATUS_OUT" | awk -F'\t' 'tolower($2) ~ /(^|\/)第[0-9]+章\.md$/ && $2 !~ /(^|\/)text\// {print $2}')
[ -n "$STRAY_CH" ] && { echo "[FAIL] 章文件必须在text/卷N/下: $STRAY_CH"; FAIL=1; }
```
- TEXT_ODD从WARN升FAIL(或要求登记)。

### P2 `--no-verify`检测: 周期git-log对账(对B2)
periodic审计新增一账: `git log --diff-filter=A --name-only -- '*第[0-9]章.md' | 建章→commit映射`,每章核对: (a)该commit是否含账本/卡同批变更或对应waiver;(b)无者列入problems("疑似no-verify入库")。配合done的后验模式收紧: 后验时八账缺失应保持problems而非全降WARN。

### P3 其余
- commit-msg: 多章staged改为**全部**章号都须匹配(堵任一匹配即过);
- progress多书化: `--recompute`按书根分文件(`<书根>/.progress.json`)或根progress改map结构;G段的`git add .progress.json`仅在主书章staged时执行(堵B7跨书搭车);
- `book_root()`不再对staged路径`resolve()`(symlink陷阱): 用`Path.cwd() / p`的词法拼接判定;
- 多书硬编码清理: D3冷读软门、E段drift改用$BROOT;
- waivers.md写入前确保行尾换行+登记行schema校验(ledger_schema.py扩展)。

---

## 四、总体判断

这套门对**意外错误**(忘记账/重复章/跳章/查重/字数)防护扎实——实验中G2b/G4/G5/G1多次有效拦截;但对**主动绕过**,核心弱点只有三个结构性根因:
1. **门检查工作区,不检查staged**(B3/B4/B5的公共根因);
2. **门不保护自己**(B1/B6);
3. **事后审计信任"已提交"这一状态本身**(B2)。
修掉P0三项后,剩余绕法都退化成"内容质量问题"(check.py仍是最硬的墙)。

实验环境: `/tmp/rt/repo`(clone),worktree已清理,真库零改动。
