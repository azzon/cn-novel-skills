# 系统架构（ARCHITECTURE）

> 本文是唯一的架构事实源。技能/工具与本文冲突时，以本文为准并触发skill-sync。
> 诞生背景：audits/01-12（第一轮12路红队）+ audits/13-15（第二轮架构红队）。

## 分层模型

```
┌─────────────────────────────────────────────────────┐
│ L6 手稿层  text/卷*/第*.md + text/卡/                │  唯一权威事实(手稿是唯一权威)
├─────────────────────────────────────────────────────┤
│ L5 状态层  .progress.json(hook重算) + scores.json    │  派生缓存,禁手写
│            ledgers/七账 + 时间线 + 当前时刻卡(手维护) │
├─────────────────────────────────────────────────────┤
│ L4 执行层  tools/pipeline.py(可执行流水线状态机)      │  强制编排
│            gate_chapter.py + check.py + pre-commit   │  强制质量
├─────────────────────────────────────────────────────┤
│ L3 技能层  skills/(SSOT域结构) → .zcode + .claude装出 │  判断与生成工艺
├─────────────────────────────────────────────────────┤
│ L2 规格层  docs/NN(量化规格) + story/50-风格包.md     │  度量基准
├─────────────────────────────────────────────────────┤
│ L1 依据层  story/(前提/主题/人物/情节/定位/圣经)      │  内容事实
└─────────────────────────────────────────────────────┘
```

**依赖方向只能向下**：技能(L3)可引用依据(L1)/规格(L2)；工具(L4)可校验一切；状态(L5)只由L4写入；
禁止任何上层引用具体下层文件路径以外的东西（禁止技能引用"某个commit"或"会话记忆"）。

## 三条铁律（第一轮审计的教训）

1. **凡是没有机器强制的流程，等于不存在。** 79章写作期间六步流水线0步以独立节点执行过（audits/04）。
   → 因此编排必须是可执行的（pipeline.py），质量必须是机器门（gate_chapter/check.py），
   技能文本只承担"怎么做得好"，不承担"必须做"。
2. **状态只能派生，不能手写。** .progress.json/scores.json由工具从L6实扫重算；手写状态必腐烂
   （.pipeline_state.json坏账事故，audits/05/06）。手维护的只有叙事性账本（ledgers七账/圣经）。
3. **恢复靠机器坐标，不靠叙述。** 跨会话恢复先读.progress.json+当前时刻卡，做"机器三问"
   （写到哪/下一章几号/上一章讲什么），对不上先rebuild禁写（audits/10）。

## 强制 vs 劝告矩阵

| 环节 | 级别 | 强制者 |
|---|---|---|
| 场景卡存在+最小内容(章号/场景型/价值/钩) | 硬 | pre-commit卡门v4 + pipeline done |
| 章号重复/跳章挖洞/标题重复 | 硬 | gate_chapter G2/G2b/G3 |
| 卷归属(存量实扫,吞并/影子卷/间隙全拦) | 硬 | gate_chapter G4(v4去自洽) |
| 时序回退(新章≤账面末章须插叙标记) | 硬 | gate_chapter G6(v4解析时间线) |
| 新章字数≥1500 | 硬 | gate_chapter G1(new) |
| check.py 48项(含全角引号＂) | 硬 | pre-commit(豁免仅限waivers.md check门) |
| 章节删除 | 硬 | pre-commit v4删除门(del门授权) |
| 提交信息含章号 | 硬 | commit-msg hook |
| 三树技能一致(全量含域入口) | 硬 | skills_check v3 |
| 读者冷读 | 软+节奏 | pipeline done按cadence(5的倍数/卷首硬,其余软) |
| 七账盖章 | 软 | pipeline done提示(禁无章号记账) |
| 漂移审计每10章 | 软+提醒 | pipeline status + hook REMIND |
| .progress.json | 自愈 | hook对staged版本强制实扫重算覆盖(篡改无效) |

## 威胁模型（诚实声明,audits/13）

所有门都是**客户端hooks**——`--no-verify`或删除hooks即全免。本系统防的是"LLM手滑与流程溃散"
（已实证:重复写章/错放卷/时序倒置三事故），不防恶意操作。硬保证需pre-receive/CI复制关键门（P2排期）。
waiver是门级授权（check/card/del/all），无门id的行不生效，登记即审计对象。
已知残余盲区（记录在案，勿误以为已设防）:G5查重只抓复制不抓复述（同义改写可穿透,P2节拍指纹排期）;
字数三口径（G1的1500/check的2300/定位的2500）暂未统一。

## 写一章的官方路径（v2架构后）

```
pipeline.py next 080      # 工作契约:卡字段/将跑的门/交付物
(按scene-card填卡)
pipeline.py bundle 080    # 上下文装配:固定+按需+摘要三档注入物+预算报告
(按scene-draft生成正文)
pipeline.py check text/卷1/第001章.md
(冷读:reader-proxy,cadence到期时)
pipeline.py done 080      # 提交前验收(commit后可再跑一次作后验刷新scores)
git commit                # hook最后防线
pipeline.py done 080      # 提交后刷新committed状态与scores
```

## 技能库治理

- SSOT = `skills/`(域结构)。`.zcode/skills/`与`.claude/skills/`是装出物（install_skills.sh）。
- 技能变更必须过skills_check（结构/路由/三树一致），由pre-commit在技能文件staged时强制。
- 新技能四件套：frontmatter(name+description含Use when) → 域入口路由行 → 闸门/NEXT-SKILL → 溯源。

## 已知债务登记

- ch4-5回炉扩写至卡带下限（beat-expand批次）
- 9个新技能缺约定件（闸门/NextStep/evals/溯源）——skills_check WARN在册
- docs/规格层为占位——正式规格重建排期
- 工具代码中低危12项（audits/13 v4清单P1-P2）
- 素材库余量<30条时须扩库（当前88条≈29章）

## NN→主题对照表

| NN | 主题 | 主要引用技能 |
|---|---|---|
| 08 | 冷读六项量规 | reader-proxy |
| 09 | 去AI味九类特征 | de-ai |
| 15 | 草蛇灰线追踪 | check.py --threads |
| 19 | 调性排期 | tone-shift/revise域 |
| 20 | 引用最频(待补定义) | 多技能 |
| 21 | 结构(单元×主线咬合) | volume-outline/plot-spine |
| 22 | 评估体系/漂移防御 | drift-audit/audit域 |
| 23 | 喜剧密度规格 | humor-audit |
| 24 | 场景工艺 | scene-card/scene-draft |
| 25 | 钩/获得 | cool-point/钩分布 |
| 26 | 硬线清单 | audit域 |
| 27 | 场景卡模板 | scene-card |
| 30 | 基建层/文件即状态 | ops域全域 |
