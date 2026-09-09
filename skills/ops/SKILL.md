---
name: ops
description: 记账基建域入口——六台账/时间线/章流水/技能同步的调度,全系统的状态层与维护层。Use when 用户说"记账/更新状态/走章流水/时间线/同步技能库"。.
---

# ops:记账基建域编排器

> 溯源:docs/30(文件即状态/基建层)。本域是系统的**状态机**:对话不承担记忆,一切状态活在文件里。

## 路由表

| 用户说什么/何时 | 走哪里 |
|---|---|
| 记账/这场记一下(每场归档) | ledger-update |
| 现在几点/时间线(每场归档) | timeline-keeper |
| 下一场/全流程/写到哪了 | pipeline-chapter |
| docs改了/技能要同步 | skill-sync |
| 发书/上架/存稿 | publish-prep |
| 记个点子/灵感 | idea-inbox |
| 新冒出的设定记哪 | canon-update(已成文) / idea-inbox(仅想法) |
| 以后都这样写/别再这样(用户偏好) | author-memory |
| 回顾剧情/故事圣经 | story-bible |
| 账乱了/台账损坏/重建 | rebuild |

## 域闸门

1. **不记账,不开下一场**(六账齐+时刻卡新,才算归档);
2. 记账纪律:数值凡加必有源,凡减必有处;野伏笔当场归谱;
3. pipeline是默认写作入口(write域路由会推荐它);
4. skill-sync在每次docs复盘更新后**必跑**(防体系漂移)。

## 目录约定(文件即状态)

```
story/    构思产物(00前提→41预审→50风格包)
text/     正文(卡/审/卷N)
ledgers/  六台账+时间线+时刻卡
```

## Next Step

按路由;流水归档后→`NEXT-SKILL: pipeline-chapter`(循环)。

## evals

- "记录一下"(→ledger六账)
- "状态乱了"(→六账+时刻卡重建)
- "规则改过了"(→skill-sync)
