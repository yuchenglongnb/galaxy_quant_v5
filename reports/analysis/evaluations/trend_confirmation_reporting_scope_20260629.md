# Trend Confirmation Reporting Scope 20260629

- raw_candidate_count: `13`
- reporting_scope_counts: `{'stock': 11, 'etf': 1, 'index': 0, 'industry_without_code': 1, 'unknown': 0}`
- stock_level_reporting: `{'denominator': 11, 'coverage_count': 11, 'rs_vs_index_coverage': 1.0, 'amount_1m_ratio_coverage': 1.0, 'rs_vs_etf_coverage': 0.4545, 'shadow_distribution': {'main': 0, 'observe': 7, 'drop': 4}}`
- excluded_from_stock_reporting: `{'etf_candidates': [{'code': '159206.SZ', 'name': '卫星', 'target_type': 'ETF', 'primary_blocker': 'relative_strength_unverified'}], 'industry_without_code': [{'code': '', 'name': '数字芯片设计', 'target_type': 'industry', 'primary_blocker': 'relative_strength_unverified'}], 'unknown': []}`
- remaining_reporting_blockers: `{'benchmark_map_missing_groups': ['专业工程', '其他专用设备', '其他电源设备', '其他计算机设备', '军工电子', '磷肥及磷化工']}`
- existing_group_benchmark_map_diff_detected: `True`
- benchmark_map_modified: `False`
- trend_active_allowed: `False`
- evaluator_change_required: `False`

## Conclusion

- reporting_scope_hardened
- stock_denominator_normalized
- non_stock_candidate_excluded_from_stock_reporting
- industry_item_without_code_excluded
- benchmark_map_not_modified
- keep_trend_active_disabled
- no_strategy_rule_change
- evaluator_change_not_required

## Warnings

- existing_group_benchmark_map_diff_requires_separate_review
- no_high_confidence_benchmark_from_review_pack
