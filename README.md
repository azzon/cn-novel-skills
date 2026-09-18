# CN Novel Skills

从构思到审计的全流程AI协作长篇小说创作技能系统。80个技能覆盖构思、写作、修订、审计、记账五大域，专为200万字级中文网络小说设计。

## 这是什么

一套安装到 Claude Code 的技能系统，让AI按照经过验证的网文工艺写作长篇小说。不是"帮你写一段"的提示词，而是从立项到发布全流程的工程化体系。

**核心能力**：
- 构思一个原创长篇小说(前提句/人物/世界/情节/名场面/定位/红队预审)
- 逐场景生成正文(风格包校准/场景卡闸门/五件套注入)
- 审计质量(场景验收/冷读代理/漂移检测/一致性/知情状态)
- 200万字长跑(六台账/时间线/伏笔总谱/滚动压缩/灾备重建)

## 快速开始

### 安装

```bash
# 方法1：克隆到你的项目目录
git clone https://github.com/azzon/cn-novel-skills.git
cd cn-novel-skills

# 方法2：复制到已有项目(复制后在项目内运行安装脚本同步三份副本)
cp -r skills/ tools/ docs/ /path/to/your-project/ && cd /path/to/your-project && bash tools/install_skills.sh
```

打开 Claude Code，技能自动生效。

### 使用

在 Claude Code 中直接说：

| 你想做什么 | 说什么 | 走哪个入口 |
|---|---|---|
| 从零写一本新书 | "我想写一本小说" | `ideate` |
| 调研市场再立项 | "现在什么火" | `ideate:market-scan` |
| 写下一场 | "写下一场" | `ops:pipeline-chapter` |
| 检查这一章 | "这章行不行" | `audit:reader-proxy` |
| 去AI味 | "有股AI味" | `revise:de-ai` |

### 两种使用方式

- **流水线模式**：从构思到发布全流程走完，适合新手或AI全自动
- **工具箱模式**：自己写正文，只借用一致性审计/伏笔管理/机检脚本，适合有经验的作者

## 五域入口

```
ideate(30叶) → write(11叶) → revise(8叶) → audit(9叶) → ops(10叶)
   构思           写作         修订          审计         记账基建
```

<details>
<summary>全部80个技能清单</summary>

**构思域 ideate**
story-incubate · trial-write · market-scan · premise · theme-dossier · world-rules · world-power · world-map · world-economy · world-history · world-culture · iceberg-budget · char-bible · char-web · char-voice · romance-line · plot-spine · volume-outline · set-piece · opening-arc · unit-designer · foreshadow-plan · reward-economy · pacing-score · thread-weaver · positioning · naming(按需) · ideate-audit · author-persona · plot-freshness

**写作域 write**
style-compiler · scene-card · scene-draft · chapter-assemble · continuation · alt-takes · writing-heart · scene-discipline · dialogue-engine · duanzhang(可选范式) · golden-opening

**修订域 revise**
line-polish · scene-rewrite · beat-expand · tighten · de-ai · tone-shift · dialogue-doctor · arc-restructure

**审计域 audit**
scene-audit · reader-proxy · humor-audit · drift-audit · consistency-audit · foreshadow-audit · character-audit · knowledge-audit · arc-review

**记账基建域 ops**
ledger-update · timeline-keeper · pipeline-chapter · skill-sync · publish-prep · idea-inbox · canon-update · author-memory · story-bible · rebuild

</details>

## 工具脚本

| 脚本 | 用途 |
|---|---|
| `tools/pipeline.py` | **可执行流水线状态机(架构v2核心)**:status/next/bundle(上下文装配器)/check/done/scores |
| `tools/check.py` | 章节机检65项(禁词/装饰修辞/重复段/工程词泄漏/引号族/对话占比/心理密度)+METRICS机器输出 |
| `tools/gate_chapter.py` | 章级韧性门v4(章号/跳章/标题/跨章查重/卷归属去自洽/时序门/字数硬底线)+`.progress.json`重算 |
| `archive/tools-deprecated/gates.py` | 旧硬门(已退役,由pipeline bundle/done收编) |
| `tools/skills_check.py` | 技能库体检v3(结构/路由/死引用/三树全量比对;缺树=硬FAIL) |
| `tools/install_skills.sh` | skills/(SSOT)→.claude/skills/+.zcode/skills/ 安装+孤儿清理 |
| `tools/pre-commit-hook.sh` | 提交门v4:质量+流程+韧性(删除门/大小写逃逸/progress自愈/waiver门级化/卡内容门) |
| `tools/commit-msg-hook.sh` | 提交信息必须含staged章号(git log可机器解析为二级信源) |
| `tools/fix_quotes.py` | 直引号→中文弯引号 |
| `.progress.json` / `scores.json` | 进度指针/质量仪表(hook与pipeline自动重算,禁手写) |

## 核心工艺

**具体 > 修辞，事实 > 比较，留白 > 猜测 — 白描是最高级的修辞。**

本系统最重要的发现：AI的默认写作模式是"每个描写点挂一个比喻"(码得像牌位/像品茶/推着一整个早晨)，这不是文笔，是用修辞密度掩盖观察空洞。真人白金作者用白描+动作+对话，比喻只在关键处偶尔出现。

`skills/ops/assets/工艺载药包.md` 包含"反比喻处方"(AI写法vs真人写法替换表)和展开四拍法。

## 目录结构

```
cn-novel-skills/
├── skills/          # 80个SKILL.md域结构(唯一事实源SSOT)
│   └── assets/      # 工艺载药包/术语微词典/产物模板
├── docs/            # 规格占位层(docs/NN溯源,待正式规格重建)
├── tools/           # 运行脚本+钩子
├── .claude/skills/  # Claude Code自动发现的技能副本(装出物)
├── .zcode/skills/   # ZCode运行时技能副本(装出物)
├── story/           # 你的小说项目数据(设定/大纲/风格包/圣经/审计报告)
├── text/            # 正文+场景卡(text/卡/)
├── ledgers/         # 八账(重生书+矿产账=九账)+时间线+当前时刻卡+waivers+发布检查单
├── audits/          # 系统审计报告(红队产出)
└── .progress.json   # 进度指针(hook自动重算)
```

## 当前作品

**《重生2005：从电子城柜台开始》**（进行中，前9章已入库）

前作《回响》已归档（archive/新书一-回响），经验资产已沉淀进系统。

## 历史验证

- 构思域24叶全流程试跑通过(gates GREEN,盲评"立项")
- 首章3617字(FAIL=0,装饰性修辞=0,冷读追读7/10)
- 12路红队终审(200万字长跑/MFA对照/跨类型/白金作者/故障级联/经济成本/风格鲁棒性/全链时间/读者行为/多作者/知识新鲜度/终极盲测)
- 52轮迭代，~100次subagent审计

## 已知局限

- 笑点密度约为白金水平的1/3(白金≈每300字一个可传播点，我们≈每600字)
- AI句长方差仅为人类的6-12%(已用叙事温度字段/开头型轮换/方差工程缓解)
- 冷读代理存在同温层(需引入真实读者数据回流校准)

## License

MIT

## 致谢

本系统的工艺层借鉴了以下开源项目的优秀实践：
- [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) - 中文网文全流程
- [creative-writing-skills](https://github.com/haowjy/creative-writing-skills) - 英文AI协作写作
- [story-skills](https://github.com/danjdewhurst/story-skills) - 确定性审计CLI

## 快速开始(新人必读)

```bash
# 1. 安装Git钩子(必须!没有钩子=整个强制链不存在)
bash tools/install_skills.sh

# 2. 自检(确认环境正常)
python3 tools/self_test.py

# 3. 新书启动
# 详见 docs/新书启动流程.md 和 docs/滚动前瞻模式.md
```
