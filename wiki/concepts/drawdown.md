---
id: concept_drawdown
type: concept
cfa_topic: ""
status: draft
title: Drawdown
created: 2026-04-26
updated: 2026-04-26
related_concepts:
  - concept_volatility
  - concept_risk_tolerance
  - concept_max_drawdown
sources: []
---

# Drawdown

## Definition

回撤（Drawdown）是指组合净值从历史高点（peak）下降到最低点（trough）的幅度。

## Why it matters

相比 Volatility，用户对 Drawdown 更敏感，
因为用户感知的是"实际亏损"，而不是波动本身。

当出现较大 Drawdown 时，
用户会直观感受到资产缩水，
从而产生恐慌情绪，甚至中断投资（stop investing）或全部赎回（full redemption）。

因此，控制 Drawdown（尤其是 Max Drawdown），
是投顾系统中最关键的用户保护机制之一，
其目标不是提升收益，而是防止用户在低点离场。

## Related concepts

- [[volatility]]
- [[risk_tolerance]]
- [[max_drawdown]]

## Notes

最大回撤（Max Drawdown）用于衡量历史最极端亏损。

在面向个人投资者的产品中，
控制 Drawdown 往往比提升收益更重要。
