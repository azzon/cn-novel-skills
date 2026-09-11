---
name: pipeline-chapter
description: 章级流水编排器——串起一场的全部工序(scene-card→scene-draft→scene-audit→[revise回路]→ledger),并守章级检查点。Use when 用户说"写下一场/走流水/这一章推进"。.
---

# pipeline-chapter:章流水

> 溯源:docs/30(基建层)·27(总流程)。本技能是**调度器**:按工序串子技能,自己不写一个字。

## 双轨制(成本纪律)

| 轨 | 适用 | 工序 |
|---|---|---|
| 全装轨 | 卷首末/章王候选/名场面/高潮/开篇弧 | 完整流水:卡→写→16项验收→冷读→alt-takes→台账 |
| 简装轨 | 日常章/过渡章(约七成) | 卡→写→check.py+抽检4项(价值/笑点数/钩/Pre-Post)→台账 |

> 卷纲场景清单预标轨道标签。**把钱花在读者记得住的那10%上。**

## 前置条件

卷纲在册;风格包在册;上一场已归档(六账齐)。缺→先调 continuation 重建状态。

## 流程

**1 取位**
1.1 从卷纲取下一场预标;从时刻卡取当前时间/在场人。

**1.5 机器硬门(每步前跑)**
- 生成前:`python3 tools/gates.py card-exists <卡路径>`(无卡即拦);
- 拼章前:对每个场景文件跑 `audit-marked`;
- 开新场前:`ledger-fresh`(台账落后即拦);
- 写作首启:`style-ready`。硬门FAIL=当场停线,回到对应技能,**禁止绕过**。

**2 标准工序(串行,闸间不放行)**
2.1 `write:scene-card`(填卡)→
2.2 `write:scene-draft`(生成)→
2.3 `audit:scene-audit`(验收;**不过→`revise:scene-rewrite`回路,至多两轮,仍不过→上报卷纲层**)→
2.4 `ops:ledger-update` + `ops:timeline-keeper`(并行记账)→
2.5 本章末场加跑:`write:chapter-assemble`(拼章+卫生)→`audit:reader-proxy`(冷读;硬线→revise回路)。

**3 章完成检查点**
- check.py全绿/冷读硬线过/六账齐/时刻卡新→本章归档;
- 每10章自动触发 `audit:drift-audit`;卷末触发 `audit:consistency-audit`+`audit:foreshadow-audit`+`audit:character-audit`。

**3.5 归档即commit**

章完成检查点通过后执行 `git add -A && git commit -m "第X章"`——忘记commit=正文单份存在,损坏不可逆。此步骤人机同等执行。

**4 中断恢复**
任意步中断→重入本技能,从"已完成的最后一步"续跑(判断依据:产物文件存在性,不靠记忆)。

## 闸门

工序序完整/每闸有产物/回路不超两轮/周期审计自动触发。

## Next Step

循环至本章末场归档→`NEXT-SKILL: pipeline-chapter`(下一场)或周期审计。

## evals

- "写下一场"(→全流水)
- "刚才断在哪了"(→4恢复判断)
- "能不能跳过验收"(→拒,闸间不放行)

## 产物格式与示例

见 `skills/ops/assets/产物模板.md` 对应节。
