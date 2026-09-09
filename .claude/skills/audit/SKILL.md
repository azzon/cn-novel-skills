---
name: audit
description: 审计域入口与编排器——场景验收/读者冷读/喜剧审计/漂移/一致性/伏笔/人设/知情八审的路由与周期调度。Use when 用户说"检查/验收/审计/冷读/有没有问题"。.
---

# audit:审计域编排器

> 溯源:docs/26(三层评估)·30。原则:**卫生(check.py)≠质量;质量结论只出自本域+用户卡点**。

## 路由表

| 粒度/用户说什么 | 走哪里 |
|---|---|
| 单场景验收 | scene-audit(答案式15项) |
| 整章好不好看 | reader-proxy(冷读+锚定) |
| 不好笑了/笑点数据 | humor-audit(近期专项;周期性趋势归drift-audit) |
| 走形了(每10章) | drift-audit |
| 前后矛盾(卷末) | consistency-audit |
| 伏笔忘了(卷末) | foreshadow-audit |
| 人设崩了 | character-audit |
| 他怎么知道的/穿帮 | knowledge-audit |
| 整卷行不行/通读/弃书点 | arc-review(卷末) |

## 周期调度(自动触发点,与pipeline联动)

每场:scene-audit|每章:reader-proxy|每10章:drift-audit|每卷末:consistency+foreshadow+character(合并为卷末报告)。

## 域闸门

0. **编辑层级闸**:先结构后文笔(给可能被重构的场景抛光是浪费);归因二分——演对了beat但笨拙=执行问题(重写);演错beat=结构问题(润色无用)。

1. 审计产出必带**引文证据**(禁空评);
2. 硬线清单(docs/26)命中即出返工指令→revise域;
3. 两章连续平庸→暂停流水,回风格包校准(调性警报);
4. 审计自身要锚定(reader-proxy的劣稿锚校验)——防裁判失真。

## Next Step

通过→`NEXT-SKILL: ops:ledger-update`;打回→`revise:scene-rewrite`。

## evals

- "检查一下"(→按粒度路由)
- "到卷末了"(→卷末三审合并)
- "我不信这个评分"(→4锚定校验)
