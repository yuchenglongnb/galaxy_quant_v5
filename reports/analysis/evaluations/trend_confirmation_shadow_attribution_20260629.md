# Trend Confirmation Shadow Attribution 20260629

## Core Status

- candidate_count: `13`
- queryable_candidate_count: `12`
- coverage_count: `11`
- shadow_distribution: `{'main': 0, 'observe': 9, 'drop': 4}`
- coverage: `{'rs_vs_index_coverage': 0.8462, 'amount_1m_ratio_coverage': 0.8462, 'rs_vs_etf_coverage': 0.3846}`
- root_cause_refined: `main_not_confirmed_after_data_recovery_etf_coverage_insufficient`
- trend_active_allowed: `False`
- evaluator_change_required: `False`

## Blocking Reasons

- relative_strength_unverified: `5`
- amount_not_confirmed: `3`
- weak_vs_index: `3`
- leading_cluster_missing: `1`
- weak_vs_etf: `1`

## Observe Candidates

- 159206.SZ 卫星: relative_strength_unverified
- 300136.SZ 信维通信: leading_cluster_missing
- 688012.SH 中微公司: amount_not_confirmed
- 688521.SH 芯原股份: amount_not_confirmed
- 300604.SZ 长川科技: amount_not_confirmed
- 001270.SZ 铖昌科技: relative_strength_unverified
- 603929.SH 亚翔集成: relative_strength_unverified
- 600520.SH 三佳科技: relative_strength_unverified
- - 数字芯片设计: relative_strength_unverified

## Drop Candidates

- 001309.SZ 德明利: weak_vs_etf
- 600141.SH 兴发集团: weak_vs_index
- 603019.SH 中科曙光: weak_vs_index
- 002335.SZ 科华数据: weak_vs_index

## ETF Benchmark Coverage

- {'covered_count': 5, 'missing_count': 6, 'coverage_ratio': 0.4545, 'missing_or_failed_codes': ['001270.SZ', '002335.SZ', '159206.SZ', '600141.SH', '600520.SH', '603019.SH', '603929.SH'], 'missing_groups': ['专业工程', '其他专用设备', '其他电源设备', '其他计算机设备', '军工电子', '磷肥及磷化工']}

## Failed Code Analysis

- {'159206.SZ': {'name': '卫星', 'reason': 'trend_etf_candidate_not_in_stock_confirmation_latest', 'is_stock': False, 'is_etf': True, 'recommended_action': 'audit_etf_candidate_confirmation_scope_or_exclude_non_stock_from_stock_confirmation'}}

## Conclusion

- keep_trend_active_disabled
- no_strategy_rule_change
- read_only_audit
- evaluator_change_not_required
- etf_benchmark_coverage_insufficient
- main_not_confirmed_after_data_recovery
- industry_item_without_code_excluded
