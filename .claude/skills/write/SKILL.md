---
name: write
description: 写作域入口与编排器——从风格包到成章的路由与调度(风格/卡/生成/拼章/续写)。Use when 用户说"开写/写作/继续写下一场/做风格包"。.
---

# write:写作域编排器

> 溯源:docs/30。路由器+闸门,不亲自写。

## 路由表

| 用户说什么 | 走哪里 |
|---|---|
| 定文风/做风格包/文风校准 | style-compiler |
| 填卡/下一场准备 | scene-card |
| 生成/写这场 | scene-draft(无卡拒工→先scene-card) |
| 再来一版/哪版好(关键场) | alt-takes |
| 拼章/过卫生 | chapter-assemble |
| 接着写(新会话/中断恢复) | continuation(重建状态后→scene-card);**同会话连写直接走pipeline** |
| 一场到章全流程 | ops:pipeline-chapter(推荐默认) |
| 对话专项修订/对话引擎 | dialogue-engine |
| 可选范式,用户点名"断章法"时 | duanzhang(默认仍走pipeline-chapter逐场流水) |
| 前三章成稿打磨 | golden-opening(与opening-arc分工见其卡) |
| 写场景前的行为铁律 | scene-discipline |
| 重点章/情感重场的灵魂层 | writing-heart(硬门冲突时硬门优先) |

## 域闸门

1. **无风格包,不写作**(style-compiler先行——立项过审后第一件事);
2. **无卡不生成,无验收不归档,无记账不开下一场**(三连闸,与pipeline共担);
3. 修订需求一律转 revise 域(写作域不自我修订——生成与修订分离,防"边写边改"的补丁病)。

## Next Step

默认推荐:`NEXT-SKILL: ops:pipeline-chapter`(场级全流水)。

## evals

- "开写吧"(→查风格包→pipeline)
- "接着上次的写"(→continuation)
- "帮我改改这段"(→转revise域)
