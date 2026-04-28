---
id: concept_volatility
type: concept
cfa_topic: ""
status: reviewed
title: Volatility
created: 2026-04-26
updated: 2026-04-26
related_concepts:
  - concept_risk_tolerance
  - concept_drawdown
  - concept_sharpe_ratio
sources: []
---

# Volatility

## Definition

波动率（Volatility）是衡量资产收益（returns）波动程度的指标，
通常用标准差（standard deviation）表示。

## Why it matters

高 Volatility 会导致组合净值在短期内出现大幅波动，
即使长期收益为正，用户仍可能因为阶段性亏损而产生不安。

当波动超过 Risk Tolerance 时，
用户容易在市场下跌阶段进行恐慌卖出（panic selling），
从而在低点退出市场，错失后续反弹。

因此，在资产配置中控制 Volatility，
本质上是为了降低用户行为风险（behavioral risk），
确保用户能够长期持有（stay invested）。

## Related concepts

- [[risk_tolerance]]
- [[drawdown]]
- [[sharpe_ratio]]

## Notes

年化波动率（annualized volatility）通常计算为：

```
std(R_t) × √12（基于月度收益）
```

Volatility 是最常用的风险 proxy，但并不能完全反映尾部风险（tail risk）。
