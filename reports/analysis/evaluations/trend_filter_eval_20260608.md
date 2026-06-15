# Trend Filter Evaluation 20260608

## 1. 验证日期

`20260608`

## 2. 验证目的

说明本次验证是为了确认：`strong_repair 不等于 trend 全开`

## 3. before/after 数量对比

| 指标 | filter off | filter on | 变化 |
|---|---:|---:|---:|
| trend 主列表数量 | 0 | 0 | 0 |
| trend_observation 数量 | 0 | 0 | 0 |
| trend_dropped_debug 数量 | 0 | 4 | 4 |
| CP 数量 | 0 | 0 | 0 |
| reversal 数量 | 0 | 0 | 0 |

## Confirmation Coverage

| metric | value |
|---|---:|
| raw trend signals | 4 |
| confirmation coverage count | 4 |
| confirmation coverage ratio | 1.0 |
| benchmark_etf_mapping_ratio | 0.25 |
| benchmark_index_mapping_ratio | 1.0 |
| rs_vs_etf available | 1 |
| rs_vs_index available | 4 |
| rs_vs_etf_coverage_ratio | 0.25 |
| rs_vs_index_coverage_ratio | 1.0 |
| amount_1m_ratio available | 4 |
| trend_filter_status | active |

## 4. keep / observe / drop 原因分布

| decision | count | top reasons |
|---|---:|---|
| keep | 0 | - |
| observe | 0 | - |
| drop | 4 | non_leading_cluster_unverified(4), missing_leading_cluster_rank(4), strong_vs_index(3), missing_rs_vs_etf_pct(3), strong_vs_etf(1) |

## 5. trend 主列表变化

- 无 trend 主列表保留样本

## 6. observation 代表样本

- 无 observation 样本

## 7. drop 代表样本

- 002361.SZ | 神剑股份 | 合成树脂 | action_score=21.13 | filter_score=14.00 | rs_vs_etf_pct=10.9745 | rs_vs_index_pct=11.3609 | reasons=strong_vs_etf;strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_leading_cluster_rank
- 002896.SZ | 中大力德 | 金属制品 | action_score=5.64 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=5.4926 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 002001.SZ | 新和成 | 原料药 | action_score=-17.95 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=1.0202 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 603516.SH | 淳中科技 | 其他计算机设备 | action_score=-20.24 | filter_score=-10.00 | rs_vs_etf_pct=None | rs_vs_index_pct=-0.507 | reasons=- | risk=weak_vs_index;non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank

## 8. 潜在误杀检查

- 未发现明显核心票被 drop；若存在降级，更接近 coverage 缺失导致的保守处理

## 9. regime 命中检查

- replay 实际 regime: `hostile`
- config 命中: `True`
- 证据: `trend_filter_config.json -> regime_rules`

## 10. 结论

1. trend 主列表未明显收敛。
2. 本次更重要的结论是：`20260608` 的 relative strength 结论是否可信，取决于 confirmation coverage，而不是单看 keep/observe 数量。
3. 当前 status=`active`，因此本次结果应被解释为 `active` 模式下的过滤行为。
4. broad_strong_repair / rotational_strong_repair 的拆分可以继续，但前提是先有更多 `active` 状态样本。

## 附加审计

- `trend_observation` 保留状态: `True`
- 证据: AuctionAnalyzer._apply_intraday_confirmation uses shortlist.setdefault("trend_observation", []) and appends rejected trend candidates.
- drop 审计来源: Raw trend candidates remain in result["signals"]["trend"] with trend_filter_decision preserved.
- config 建议: 无
