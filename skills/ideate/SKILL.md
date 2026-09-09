---
name: ideate
description: 构思域入口与编排器——从一句话想法到可开写的立项,路由并调度25个子技能(标准序列24叶+naming按需),守总闸门,卷首跑ideate-complete门。Use when 用户说"构思新故事/立项/重启构思/接着上次的构思"。.
---

# ideate:构思域编排器

> 溯源:docs/30(技能树)·21(八步)·08(六维)。本技能是**路由器+闸门**,不亲自产出内容;干活的永远是子技能。

## 前置条件

无(域入口)。若 story/ 已有部分产物→先做断点盘点(第4节),从缺件处续跑,禁止推倒重来。

## 流程

**1 意图识别(路由表)**

| 用户说什么 | 走哪里 |
|---|---|
| 想新故事/定方向 | 从头:premise 起(建议先跑market-scan) |
| 扫榜/查市场/拆一本 | market-scan |
| 前三章/开头/黄金三章 | opening-arc |
| 名场面/大场面/这本书记住什么 | set-piece |
| 多线/支线/主线被淹 | thread-weaver |
| 感情线 | romance-line |
| 加戏/加场(给某人) | volume-outline(加场);对象是感情线→romance-line,是配角升格→char-web |
| 定主题/怕说教 | theme-dossier(需00存在) |
| 建世界/设定 | world系七叶(需00/01存在) |
| 立人物/人设崩 | char系三叶 |
| 排主线/卷纲/案子 | plot系六叶 |
| 像不像谁/能过审吗/起名 | positioning |
| 行不行了/可以开写吗 | ideate-audit |
| 人名地名功法名/这个名字行不行 | naming(书名简介→positioning) |
| 接着构思 | 断点盘点后续跑 |

**2 标准序列(新立项全流程,序即依赖)**

premise → theme-dossier → world-rules → world-power → world-map → world-economy → world-history → world-culture → iceberg-budget → char-bible → char-web → char-voice → plot-spine → romance-line → volume-outline → set-piece → opening-arc → unit-designer → foreshadow-plan → reward-economy → pacing-score → thread-weaver → positioning → ideate-audit(naming按需插队)

**3 闸门与推进纪律**

- 每叶产物落盘(story/对应路径)才调下一叶;产物头部 NEXT-SKILL 注与调用指示**双保险**;
- 子技能自检未过→在该叶内返工,**禁带病进下一叶**;
- 用户中途插话改设定→改完回到受影响叶重跑其自检(影响面由各叶产物内的引用关系判断)。

**4 断点盘点(续跑入口)**

4.1 点验 story/00→41 存在性与完整性;
4.2 从第一个缺件叶续跑;已过闸的叶不重跑(除非其上游被改动)。

**4.3 快速启动(fast-start)**

用户不耐烦走24叶?最短路径:premise→char-bible→opening-arc→卷一纲(仅前3章)→风格包→开写。世界后四叶/伏笔总谱/奖励/节奏/多线推迟到第3-10章间异步补齐。**从"我想写"到第一行正文压缩到12步/约30分钟。**

**4.5 机器门**

序列走完先跑 `python3 tools/gates.py ideate-complete`(缺件即拦,清单即续跑路线)。

**5 总闸(与ideate-audit共担)**

全序列过闸+预审致命伤清零 → 组装**用户卡点包**(前提句/设计原则/差异化句/卷一段落/预审结论)→ 呈用户;
用户驳回 → 记录驳回点 → 路由回对应叶;
用户通过 → `NEXT-SKILL: write:style-compiler`(风格包,进入写作域前置)。

## evals

- "构思个新书"(→标准序列起跑)
- "上次构思到一半"(→断点盘点续跑)
- "我不想自己看文档,直接告诉我立项行不行"(→走完audit后只呈卡点包)
