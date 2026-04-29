---
cfa_topic: portfolio_management
id: concept_volatility
related_concepts:
- risk_tolerance
- drawdown
- sharpe_ratio
- tail_risk
sources:
- evidence: 年化波动率通常基于连续复利日收益标准差，乘以年交易天数平方根换算。
  path: staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 1 Quantitative
    Methods, Economics (CFA Institute) (Z-Library).md
  query: ''
- evidence: 组合波动率主要受资产间平均协方差驱动；相关性上升会推高整体风险。
  path: staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 2 Portfolio
    Management, Corporate Issuers, Financial Statement Analysis (CFA Institute) (Z-Library).md
  query: ''
- evidence: 工具波动率直接影响维持保证金要求；企业可能通过会计选择平滑盈利波动。
  path: staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 3 Financial
    Statement Analysis, Equity Investments (CFA Institute) (Z-Library).md
  query: ''
status: draft
title: Volatility
type: concept
updated: '2026-04-28'
---

# Volatility

## Definition

波动率（Volatility）是衡量资产收益率双向波动程度的统计指标，通常以标准差表示。

## Why it matters

高波动率会导致组合净值在短期内剧烈震荡。当波动超出投资者的风险承受能力时，极易引发恐慌性抛售，使其在低点离场并错失后续反弹。

在资产配置中主动管理波动率，本质上是为了控制行为风险（behavioral risk），帮助投资者跨越市场周期、长期持有。同时，波动率也是定价风险溢价与构建有效前沿的核心输入变量。

## Key points

- 年化波动率通常通过周期标准差乘以时间平方根换算（如日频×√250，月频×√12）。
- 投资组合的整体波动率主要由资产间的平均协方差与相关性驱动，而非单一资产方差。
- 作为最常用的风险代理指标，波动率假设收益分布对称，无法充分捕捉尾部风险。
- 波动率上升时，风险厌恶型投资者会沿无差异曲线要求更高的预期收益补偿。

## Common confusions

- 误将波动率等同于下行风险（实际同时衡量上涨与下跌的双向偏离）。
- 混淆历史波动率与隐含波动率（前者回溯已实现数据，后者定价未来市场预期）。
- 认为分散化可消除全部波动（仅能降低非系统性风险，系统性波动依然存在）。

## Related concepts

- [[risk_tolerance]]
- [[drawdown]]
- [[sharpe_ratio]]
- [[tail_risk]]

## Sources

- `staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 1 Quantitative Methods, Economics (CFA Institute) (Z-Library).md` — 年化波动率通常基于连续复利日收益标准差，乘以年交易天数平方根换算。
- `staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 2 Portfolio Management, Corporate Issuers, Financial Statement Analysis (CFA Institute) (Z-Library).md` — 组合波动率主要受资产间平均协方差驱动；相关性上升会推高整体风险。
- `staging/markdown/cfa/2024 CFA© Program Curriculum Level I Volume 3 Financial Statement Analysis, Equity Investments (CFA Institute) (Z-Library).md` — 工具波动率直接影响维持保证金要求；企业可能通过会计选择平滑盈利波动。
