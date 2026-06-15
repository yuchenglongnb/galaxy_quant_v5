# Trend Filter Evaluation 20260612

## 1. 验证日期

`20260612`

## 2. 验证目的

说明本次验证是为了确认：`strong_repair 不等于 trend 全开`

## 3. before/after 数量对比

| 指标 | filter off | filter on | 变化 |
|---|---:|---:|---:|
| trend 主列表数量 | 1 | 1 | 0 |
| trend_observation 数量 | 0 | 0 | 0 |
| trend_dropped_debug 数量 | 0 | 0 | 0 |
| CP 数量 | 0 | 0 | 0 |
| reversal 数量 | 0 | 0 | 0 |

## Confirmation Coverage

| metric | value |
|---|---:|
| raw trend signals | 30 |
| confirmation coverage count | 0 |
| confirmation coverage ratio | 0.0 |
| rs_vs_etf available | 0 |
| rs_vs_index available | 0 |
| amount_1m_ratio available | 0 |
| trend_filter_status | degraded_global_missing |

## 4. keep / observe / drop 原因分布

| decision | count | top reasons |
|---|---:|---|
| keep | 30 | relative_strength_unverified(30), non_leading_cluster_unverified(30), global_confirmation_unavailable(30), missing_rs_vs_etf_pct(30), missing_rs_vs_index_pct(30) |
| observe | 0 | - |
| drop | 0 | - |

## 5. trend 主列表变化

- 300489.SZ | 光智科技 | 光学元件 | action_score=98.26 | filter_score=0.00 | rs_vs_etf_pct=None | rs_vs_index_pct=None | reasons=- | risk=relative_strength_unverified;non_leading_cluster_unverified;global_confirmation_unavailable | missing=missing_rs_vs_etf_pct;missing_rs_vs_index_pct;missing_leading_cluster_rank

## 6. observation 代表样本

- 无 observation 样本

## 7. drop 代表样本

- 无 drop 样本

## 8. 潜在误杀检查

- 未发现明显核心票被 drop；若存在降级，更接近 coverage 缺失导致的保守处理

## 9. regime 命中检查

- replay 实际 regime: `strong_repair`
- config 命中: `True`
- 证据: `trend_filter_config.json -> regime_rules`

## 10. 结论

1. trend 主列表未明显收敛。
2. 本次更重要的结论是：`20260612` 的 relative strength 结论是否可信，取决于 confirmation coverage，而不是单看 keep/observe 数量。
3. 当前 status=`degraded_global_missing`，因此本次结果应被解释为 `degraded_global_missing` 模式下的过滤行为。
4. broad_strong_repair / rotational_strong_repair 的拆分可以继续，但前提是先有更多 `active` 状态样本。

## 附加审计

- `trend_observation` 保留状态: `True`
- 证据: AuctionAnalyzer._apply_intraday_confirmation uses shortlist.setdefault("trend_observation", []) and appends rejected trend candidates.
- drop 审计来源: Raw trend candidates remain in result["signals"]["trend"] with trend_filter_decision preserved.
- config 建议: 20260612 had no 09:35 confirmation enrichment; current decisions are dominated by missing confirmation coverage, global coverage guard is active; keep/observe results should be read as data-missing-aware fallback, not relative-strength proof
