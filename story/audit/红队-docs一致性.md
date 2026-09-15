# 红队-docs一致性审计（2026-09-15）

> 对象: docs/ 全部文档 + AGENTS.md + README.md + skills/*/SKILL.md 的 frontmatter 与正文引用 + workflows/*.yaml + 主书 story/ 依据层。
> 方法: 全量 grep 交叉引用 + ls 逐路径验证 + 每个工具真实执行验证。只读操作。
> 结论速览: 硬死引用 **15** 条; 数字口径冲突 **8** 组; AGENTS 裸条款 **4.5** 条(半背书2条); 主书重启必重做 TOP3 见 §4; 规格真空 19 个占位中被实质引用 **17** 个编号。

---

## 一、死引用清单(硬15条)

| # | 位置 | 引用 | 实况 | 应指向 |
|---|---|---|---|---|
| 1 | skills/ideate/positioning/SKILL.md:8 | `docs/07(合规要求R10/R11)` | docs/07-规格.md 不存在(docs 仅有 01,08,09,11,12,15-27,30) | 补 docs/07 或并入 docs/26 并改引 |
| 2 | skills/ideate/ideate-audit/SKILL.md:8 | `docs/14(红队模式)` | 不存在 | 同上(红队模式可并入 docs/18) |
| 3 | skills/ops/skill-sync/SKILL.md:8 | `docs/28(迭代史)` | 不存在 | 删除编号或落盘迭代史 |
| 4 | docs/多书隔离协议.md:37 | `pipeline_runner.py` | tools/ 无此文件 | 改为 `pipeline.py --book <书根>` |
| 5 | AGENTS.md:18 / docs/商业质量线.md:38 | `ledgers/生成记录.md`(主书) | 主书 ledgers/ 无此账(1993 书有);pre-commit:126 对 staged 章会因缺账 FAIL | 主书跑一次 `pipeline.py bundle` 自动建账 |
| 6 | skills/ops/idea-inbox/SKILL.md:8 | 产物 `ledgers/灵感箱.md` | 主书不存在,且 ledger-update 初始化八账不含它(无任何机器初始化路径) | 列入初始化清单或改挂 ledger-update |
| 7 | skills/ops/author-memory/SKILL.md:8 | 产物 `ledgers/作者偏好.md` | 主书不存在,同上无初始化器 | 同上 |
| 8 | skills/write/continuation/SKILL.md:41 | 产物 `ledgers/续写衔接.md` | 主书不存在,同上 | 同上 |
| 9 | skills/ops/story-bible/SKILL.md:8 | 产物三件套含 `story/60-圣经/卷摘要.md` | 主书 60-圣经/ 无卷摘要;1993 另用 `圣经/卷N章摘要.md` 布局——两种圣经布局并存 | 统一圣经目录契约 |
| 10 | skills/ideate/positioning/SKILL.md:8 | 产物 `story/40-定位.md` | 主书 story/ 无 40-定位(主书从未做定位) | 重启必补 |
| 11 | workflows/chapter_production.yaml(machine_gates) | `voice_check.py --card <书根>/声口卡.md` | 主书书根=仓库根,顶层无声口卡.md(实际在 story/60-圣经/声口卡.md);1993 在顶层——三口径 | 模板路径统一或工具兜底搜两级 |
| 12 | tools/workflow.py 模块 docstring | "book_design 新书设计(Phase 1-6 + 终门)" | 实际 yaml 为 phase_0_isolation/0_genre/0_goldmine/1~7/final_gate;且 workflow.py 未列 publish 工作流 | 更新 docstring |
| 13 | docs/新书启动流程.md Phase2 Step1 | "场景卡 **v2**" | scene-card 技能已声明 **v3**(skills/write/scene-card/SKILL.md:8 引"docs/27 场景卡v3模板") | 统一 v3 |
| 14 | story/60-圣经/声口卡/(无扩展名) | — | 空目录残留(与声口卡.md 并存) | 删除 |
| 15 | **检测盲区**: tools/skills_check.py:80 | 正则 `docs/(\d+)` 抓不到"·07/·14/·28"简写 | 实测 positioning 仅捕获 ['11'],ideate-audit 仅 ['08','18']——三条死引用全部漏检,机器绿灯虚假 | 正则改 `docs/(\d+)|(?:·)(\d+)` 双捕获 |

**工具引用核验**: docs/skills 引用的 14 个 tools/*.py|sh 全部存在且可真实执行(bash -n / --help 实测)。唯 quality_score.py 与 system_readiness.py 把 `--help` 当文件参数(前者直接 traceback)——轻微,不算死引用。

**workflows phase 引用**: chapter_production/book_design/periodic/publish 四文件内的 script 命令(check/gate/voice/card/legacy_audit/ledger_compact/四账审计/genre_contract/goldmine_audit)逐一验证存在且参数签名匹配(--modern/--scene/--volume/--card 均在实现中)。book_design phase_5 引用的 `story/audit/研究-网文爽点设计2026.md` 存在。

---

## 二、数字口径冲突清单(8组)

| # | 项 | 各处口径 | 实测基准 | 建议 |
|---|---|---|---|---|
| 1 | **账数** | README:13"六台账"/README:109"七账"· ARCHITECTURE:13/35/53"七账"· 技能-检测对齐表:37"七账"· pipeline-chapter SKILL:32"七账"· 产物模板/术语微词典/rebuild"六账" ‖ AGENTS/活文档协议/新书启动流程/AI协作法/ledger-update/chapter_production.yaml/pipeline.py=**八账** · era-goldmine/goldmine_audit=**第九账矿产** | `pipeline.py:57 LEDGER_NAMES`=八账(伏笔/梗/钩分布/类型轮换/人物状态/线弦/时间线/数字账)+附账(口碑/爽点管道)+条件第九账 | 全库统一"八账+口碑/爽点管道两附账+条件矿产账";README/ARCHITECTURE/对齐表/pipeline-chapter 五处"六/七账"改"八账" |
| 2 | **check.py 项数** | README:79"35项" · ARCHITECTURE:48"48项" · AI协作法:61"42项" | 编号 #0-#66(跳#45)=**65 门** | 三处全改"65 项(编号#0-#66)";以后由 skills_check 顺带输出实数防止再漂 |
| 3 | **技能总数** | README"73 个"(ideate 30/write 11) | skills_check 实测 **80**(ideate 35 叶/write 13 叶/revise 8/audit 9/ops 10 + 5 域入口) | README 更新为 80 并补 era-goldmine/genre-playbook/book-plan/premise-fit/reader-persona/cool-point/dialogue-voice 七叶 |
| 4 | **ideate 子技能数** | ideate SKILL description"25 个子技能(标准序列24叶+naming按需)" | 实际 **35** 叶 | description 改 35 或去掉数字 |
| 5 | **de-ai 类数** | docs/09 占位+对齐表"九类硬特征(#34-#44)" · de-ai 正文标题"流程(十类)" · de-ai description"十一类(编号0-10)" | 正文实编 **0-10 共 11 类** | 三处统一"十一类(0-10)" |
| 6 | **流派数** | genre-playbook description"14 流派" | 档案库 **13** 个流派节 + 第 14 节是"跨界混搭原则"(非流派);genre_contract.py 已知列表 13 | description 改"13 流派+混搭原则" |
| 7 | **audit 域** | audit description"八审" | 9 叶(八审+arc-review 卷级连读) | 改"八审+卷级连读" |
| 8 | **素材库红线** | ARCHITECTURE 债务表"<30 条**须扩库**(当前88条)" ‖ 商业质量线/periodic"<40 条**强制扩容**(≈13章)" ‖ AI协作法"<30 条红灯" | 现行协议=两级(40 强制扩容/30 红灯),但 ARCHITECTURE 措辞"须扩库"与 40 线撞车;且"当前88条"陈旧(实测 98 条) | ARCHITECTURE 改"<40 强制扩容(13章预警),<30 红灯;当前 98 条" |

另: 冷读量规存在**同名双体系**——reader-proxy"六项冷读量规(笑/跳/爽/追读/硬特征/成对)"与 docs/08"神作六维(概念/情绪/世界/人物/价值观/声音,premise/ideate-audit 立项用)"。reader-proxy 已自标"非 docs/08 神作六维"消歧,但 docs/08 是 4 行占位,**两套六维均无落盘定义**——见 §5。

---

## 三、AGENTS.md 铁律可执行性逐条审

### 有机器门背书(实测确认)

| 条款 | 背书者 | 验证点 |
|---|---|---|
| 铁律1 禁止从零手写脚手架产物 | skill_protocol.py `audit-cards` + pre-commit-hook.sh:36-39 | 指纹(generated-by)缺失=FAIL(221-225行);"（填）"等占位残留=FAIL(221-222行);失败立即 exit 1 ✅ |
| 铁律2 后半"完成后打勾" | pipeline.py done 6.95 节(763-785) | 未全勾/缺章条目/自证打勾无"→产物:路径"证据链 = problems 拦截 ✅ |
| 铁律4 done 审计技能执行率 | pipeline.py:771 调 skill_protocol audit --evidence | ✅ |
| 四门(check/gate/voice/card) | pre-commit-hook.sh | gate_chapter(69/72)·voice_check(173)·card_check(180)·check.py(189) 全接线 ✅ |
| bundle 落盘生成记录 | pipeline.py:805-808 + pre-commit:126 | 无记录=done problems/提交拦截 ✅ |
| 章摘要+人物圣经演进层(done 验) | pipeline.py 6.95 H3-H6 | ✅ |
| periodic 四账审计(伏笔/数字/期待链/就绪度) | periodic.yaml ledger_audits 步骤 | 四工具存在可跑 ✅——但**周期触发本身无门**(对齐表自标"drift-audit 无触发器❌",P1 待补仍在册) |
| .git/hooks/pre-commit 安装态 | 实测 .git/hooks/pre-commit 为转发 shim→tools/pre-commit-hook.sh | ✅(薄转发,单点事实源) |

### 裸条款(无机器背书,纯靠自觉)

1. **铁律2 前半"type=agent 步骤执行前必读 SKILL.md 全文"——纯裸**。机器只能验"打勾+产物引用"这一自证链;读没读无法机检,pipeline.py:775 注释自己承认"自证打勾=可偷懒"。当前缓解(--evidence 要求产物路径)只是把谎言成本提高一档。
2. **铁律3"type=script 必须真实执行命令,禁等效手写"——半裸**。script 步骤的下游产物多有门(check 输出/bundle 落盘/done 返回值),但"等效手写脚本逻辑"本身不可检;报告类 script(如 periodic conflict_check 原为中文伪 script,红队 20260915 才改 review 标注)无产物门。
3. **"固定动作"第 3 条(无脚手架产物头部 `<!-- skill:名 -->` 注释)——纯裸**。audit-cards 只管卡/冷读两类,其他产物(总谱/审计报告/圣经)的 skill 注释无任何门查验。
4. **纠错管道三件套(autopilot 铁律)——两件半裸**。仅第 2 件有机器(genre_contract.py 流派/矿产硬前置,实测对主书已输出 2 条 WARN);第 1 件(genre-playbook 档案条目更新)与第 3 件(写作技能更新+install_skills.sh 重装)无门;"用户第二次说同一件事=系统失败记入大审计"无检测器。
5. **铁律2 覆盖面漏洞**: periodic.yaml 的 drift_audit/style_recal/voice_check/volume_retro 四个 type:agent 步骤**无 skill 字段**(技能执行记录里印着"技能: (无)")——铁律2 对它们空转,等于这四步的"读技能"义务不存在。

---

## 四、主书 story/ 依据层陈旧度(重启必重做清单)

主书现状: 00-前提为"清稿态+待重启声明(重生系)",text/卷1 空,ledgers 半空(伏笔 0 条/时刻卡"未开笔"),story/audit/ 存留 40 章旧冷读遗产。对照 1993 书已实证的新体系:

### 必重做 TOP3

1. **人物圣经按 v2 模板重写 + 线弦欲望线登记**。story/20-人物/人物圣经.md 仍是 v1 自由体(ghost/wound/lie/want/need 内容在但无三层结构);1993 人物圣经已按 docs/人物圣经模板v2 完整落地(恒定层/欲望引擎四件套/对手威胁兑现表/关系不可逆移动表/演进层卷末快照)。硬约束: system_readiness 要求"人物圣经含引擎字段(Ghost/Want 等)+线弦账首条=欲望线",主书线弦首条仍是占位"（构思阶段登记…）"——**现状直接开写=🔴先修再产拦截**。
2. **声纹表/声口卡双轨合并为单张声口卡并定死路径**。story/20-人物/声纹表.md(char-voice 系:句长/语气/口头禅/人格宣言/绝不说+闲谈域)与 story/60-圣经/声口卡.md(dialogue-voice 系:聪明等级/知识域/禁词/碎片习惯/信息盲区等 10 字段)对同一批人物双头维护=漂移源;voice_check.py 只解析声口卡格式;1993 已收敛为书根顶层单卡。另需消路径三口径(workflow 模板 `<书根>/声口卡.md` 对主书指向不存在文件)与清掉 60-圣经/声口卡/ 空目录。
3. **按 book_design 终门重跑缺件**。story/10-世界 仅 3 文件(时代记忆库/行业经营/金手指地图),缺规则/经济日常/地图/文化/历史/呈现预算/读者画像/商业计划;story/30-情节 缺伏笔总谱/单元库/多线表/节奏总谱/奖励经济/开篇弧/名场面谱;无 story/40-定位.md;**无题材配置.md**(check.py 卡带/质量线/对话/心理四阈值的配置源,主书跑 check 全吃默认值);**重生系硬前置缺**——genre_contract 实测 2 WARN: 缺 00-矿产档案.md + 缺 ledgers/矿产账.md(第九账)。

### 次级(随上述三项带出)

- ledgers 重建: 伏笔账(0 条,foreshadow_audit 判 FAIL)、技能执行记录(现为 periodic 步骤集错标"第001章"且全未勾——无效产物)、生成记录/灵感箱/作者偏好/续写衔接四账从未建。
- 圣经层: 60-圣经 用单文件章摘要,1993 用"圣经/卷N章摘要"分卷;缺卷摘要.md;story-bible 技能产物契约与两书实况三方不一致。
- 素材库 98 条(ARCHITECTURE 写 88 条已陈旧): 格式仍有效(年代锚+已用标记),可续用,但按 40 条红线须先核算剩余可用量。
- 风格包 v1(重生2005)完整度高,未被 1993"应急版"格式超越,可保留;但 1993 新增的独立"风格包范例段库.md"+exemplar_flywheel 范例段收割机制值得并入主书(范例段现在只嵌在风格包正文内,无收割闭环)。

---

## 五、规格真空(docs 声称存在 vs 实际未写)

docs/ 共 20 个 NN-规格文件,**19 个是 4 行占位**(唯 docs/23 落了喜剧十四型正文)。被实质引用的占位编号 **17** 个——即 ARCHITECTURE L2"规格层=量化规格"名存实亡,ARCHITECTURE 自己在债务表承认"docs/规格层为占位",但下游仍在按"有规格"引用:

| 占位 | 被谁实质引用(引用内容=真空) |
|---|---|
| **docs/20**("引用最频,待补定义"——ARCHITECTURE 自认) | line-polish"docs/20 禁词表"·style-compiler"文笔论三层模型"·scene-audit"文笔自查"·de-ai·tighten"删段测试" |
| **docs/25** | pacing-score:46"**燃泪数值规格以 docs/25 为单一权威**"·reward-economy"填 docs/25 的表模板"·drift-audit"钩实际频率 vs 预算(docs/25)"——三个技能的量化基准悬空 |
| docs/17 | publish-prep:34"首订 1000 及格/3000 精品(docs/17)"·D16/D17/D18 发布策略数据锚 |
| docs/27 | scene-card"场景卡 v3 模板"(真骨架在 skill_protocol.py,不在 docs) |
| docs/08 | premise/ideate-audit 立项"六维"评分——与 reader-proxy 冷读六项同名并存,两套定义均未落盘 |
| docs/09 | ARCHITECTURE NN 表"去AI味九类特征"——实际十一类(见 §2#5) |
| docs/15/16/18/19/21/22/23/24/26/30/01/11/12 | 各技能溯源行按编号引用,内容全空(docs/23 除外) |

**专项核查**:
- "docs/23 笑点编号"——**存在**(十四型编号枚举,磨刀十五批落盘),humor-audit/scene-card/genre-playbook 引用有效 ✅。
- **"商业质量线"引用共 7 处**(system_readiness.py 2 处存在性检查·publish.yaml 3 处·大审计-33·红队-预验尸),定义本身一致(单章发布线 5 维/上架线 4 条),无版本打架 ✅。但执行真空: "质量分≥题材线"的判定器 quality_score.py **未接线任何 publish 门**(publish stockpile_check 只跑 pipeline.py status——红队-工作流.md:89 已在案未修),且主书无题材配置.md,"默认 70"仅写在文档里。**单章线五维中三维(冷读拉力判据/期待链≥2/质量分)无机器判定进入发布门**——商业线目前是"文档级宣示"。

---

## 六、修复优先级建议

1. **P0 修 skills_check 正则**(§1#15): 死引用检测被"·NN"简写绕过是系统性盲区,修一行正则,07/14/28 三条立刻现形。
2. **P0 统一账数口径**: README:13/109、ARCHITECTURE:13/35/53、对齐表:37、pipeline-chapter:32 五处"六/七账"改"八账"——与 pipeline.py 硬门对齐,否则文档教人数七账、done 按八账拦。
3. **P1 三处数字就地更新**: check 65 项(README/ARCHITECTURE/AI协作法)、技能 80(README+ideate desc)、de-ai 十一类(对齐表+docs/09 占位注释)。
4. **P1 docs/25 与 docs/20 落盘**: 两份是被声明为"单一权威/引用最频"的占位,优先级高于其余占位(其余可按 skill-sync 流程分批内化确认后改"已内化"声明)。
5. **P1 死引用清理**: pipeline_runner.py 改名、场景卡 v2→v3、声口卡路径三口径统一(建议: 书根顶层为唯一权威,voice_check 默认路径改双级探测)。
6. **P2 主书重启前置单**: §4 TOP3 三项列为"开写前必过 system_readiness 绿灯"的验收项,并把生成记录/灵感箱/作者偏好/续写衔接四个无初始化器的账挂进 ledger-update 初始化清单。
