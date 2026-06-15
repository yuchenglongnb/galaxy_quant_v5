# Trend Filter Evaluation 20260609

## 1. 验证日期

`20260609`

## 2. 验证目的

说明本次验证是为了确认：`strong_repair 不等于 trend 全开`

## 3. before/after 数量对比

| 指标 | filter off | filter on | 变化 |
|---|---:|---:|---:|
| trend 主列表数量 | 1 | 1 | 0 |
| trend_observation 数量 | 0 | 1 | 1 |
| trend_dropped_debug 数量 | 0 | 0 | 0 |
| CP 数量 | 0 | 0 | 0 |
| reversal 数量 | 0 | 0 | 0 |

## Confirmation Coverage

| metric | value |
|---|---:|
| raw trend signals | 14 |
| confirmation coverage count | 13 |
| confirmation coverage ratio | 0.9286 |
| benchmark_etf_mapping_ratio | 0.3846 |
| benchmark_index_mapping_ratio | 1.0 |
| rs_vs_etf available | 5 |
| rs_vs_index available | 13 |
| rs_vs_etf_coverage_ratio | 0.3846 |
| rs_vs_index_coverage_ratio | 1.0 |
| amount_1m_ratio available | 13 |
| trend_filter_status | active |

## 4. keep / observe / drop 原因分布

| decision | count | top reasons |
|---|---:|---|
| keep | 1 | strong_vs_etf(1), strong_vs_index(1), amount_confirmed(1), non_leading_cluster_unverified(1), missing_leading_cluster_rank(1) |
| observe | 13 | non_leading_cluster_unverified(13), missing_leading_cluster_rank(13), missing_rs_vs_etf_pct(9), strong_repair_without_confirmation(8), relative_strength_required_for_keep(8) |
| drop | 0 | - |

## 5. trend 主列表变化

- 002670.SZ | 国盛证券 | 证券 | action_score=108.39 | filter_score=19.00 | rs_vs_etf_pct=1.5558 | rs_vs_index_pct=1.0093 | reasons=strong_vs_etf;strong_vs_index;amount_confirmed | risk=non_leading_cluster_unverified | missing=missing_leading_cluster_rank

## 6. observation 代表样本

- 001696.SZ | 宗申动力 | 其他通用设备 | action_score=77.15 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=8.4169 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 301236.SZ | 软通动力 | IT服务 | action_score=52.07 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=3.3989 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 300533.SZ | 冰川网络 | 游戏 | action_score=40.54 | filter_score=5.00 | rs_vs_etf_pct=1.0504 | rs_vs_index_pct=-0.2409 | reasons=strong_vs_etf;amount_confirmed | risk=weak_vs_index;non_leading_cluster_unverified | missing=missing_leading_cluster_rank
- 002657.SZ | 中科金财 | IT服务 | action_score=38.30 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=0.7437 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 899050.BJ | 北证50 | - | action_score=37.98 | filter_score=-14.00 | rs_vs_etf_pct=None | rs_vs_index_pct=None | reasons=- | risk=non_leading_cluster_unverified;strong_repair_without_confirmation | missing=missing_rs_vs_etf_pct;missing_rs_vs_index_pct;missing_leading_cluster_rank
- 300124.SZ | 汇川技术 | 工控设备 | action_score=35.31 | filter_score=4.00 | rs_vs_etf_pct=None | rs_vs_index_pct=0.9192 | reasons=strong_vs_index | risk=non_leading_cluster_unverified | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 002361.SZ | 神剑股份 | 合成树脂 | action_score=34.49 | filter_score=-30.00 | rs_vs_etf_pct=-2.3445 | rs_vs_index_pct=-1.8858 | reasons=- | risk=weak_vs_etf;weak_vs_index;non_leading_cluster_unverified;strong_repair_without_confirmation | missing=missing_leading_cluster_rank
- 002987.SZ | 京北方 | 垂直应用软件 | action_score=15.70 | filter_score=-20.00 | rs_vs_etf_pct=None | rs_vs_index_pct=-1.5694 | reasons=- | risk=weak_vs_index;non_leading_cluster_unverified;strong_repair_without_confirmation | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 301200.SZ | 大族数控 | 其他自动化设备 | action_score=9.95 | filter_score=-12.00 | rs_vs_etf_pct=None | rs_vs_index_pct=0.1439 | reasons=neutral_vs_index | risk=non_leading_cluster_unverified;strong_repair_without_confirmation | missing=missing_rs_vs_etf_pct;missing_leading_cluster_rank
- 002165.SZ | 红宝丽 | 聚氨酯 | action_score=9.10 | filter_score=-30.00 | rs_vs_etf_pct=-3.7553 | rs_vs_index_pct=-3.2966 | reasons=- | risk=weak_vs_etf;weak_vs_index;non_leading_cluster_unverified;strong_repair_without_confirmation | missing=missing_leading_cluster_rank

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
2. 本次更重要的结论是：`20260609` 的 relative strength 结论是否可信，取决于 confirmation coverage，而不是单看 keep/observe 数量。
3. 当前 status=`active`，因此本次结果应被解释为 `active` 模式下的过滤行为。
4. broad_strong_repair / rotational_strong_repair 的拆分可以继续，但前提是先有更多 `active` 状态样本。

## 附加审计

- `trend_observation` 保留状态: `True`
- 证据: AuctionAnalyzer._apply_intraday_confirmation uses shortlist.setdefault("trend_observation", []) and appends rejected trend candidates.
- drop 审计来源: Raw trend candidates remain in result["signals"]["trend"] with trend_filter_decision preserved.
- config 建议: 无
