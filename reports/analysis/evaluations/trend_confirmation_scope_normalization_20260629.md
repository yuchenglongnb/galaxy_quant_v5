# Trend Confirmation Scope Normalization 20260629

- raw_candidate_count: `13`
- normalized_scope_counts: `{'stock': 11, 'etf': 1, 'index': 0, 'industry_without_code': 1, 'unknown': 0}`
- excluded_from_stock_denominator: `{'etf_candidates': [{'code': '159206.SZ', 'name': '卫星', 'target_type': 'ETF', 'primary_blocker': 'relative_strength_unverified'}], 'industry_without_code': [{'code': '', 'name': '数字芯片设计', 'target_type': 'industry', 'primary_blocker': 'relative_strength_unverified'}], 'unknown': []}`

## Before

{
  "coverage_count": 11,
  "rs_vs_index_coverage": 0.8462,
  "amount_1m_ratio_coverage": 0.8462,
  "rs_vs_etf_coverage": 0.3846,
  "shadow_distribution": {
    "main": 0,
    "observe": 9,
    "drop": 4
  }
}

## After

{
  "stock_denominator": 11,
  "stock_coverage_count": 11,
  "stock_rs_vs_index_coverage": 1.0,
  "stock_amount_1m_ratio_coverage": 1.0,
  "stock_rs_vs_etf_coverage": 0.4545,
  "stock_shadow_distribution": {
    "main": 0,
    "observe": 7,
    "drop": 4
  }
}

- benchmark_map_missing_groups: `['专业工程', '其他专用设备', '其他电源设备', '其他计算机设备', '军工电子', '磷肥及磷化工']`
- trend_active_allowed: `False`
- evaluator_change_required: `False`
- benchmark_map_change_required: `False`

## Conclusion

- keep_trend_active_disabled
- no_strategy_rule_change
- read_only_scope_audit
- evaluator_change_not_required
- benchmark_map_not_modified
- non_stock_candidate_excluded_from_stock_denominator
- industry_item_without_code_excluded
- benchmark_map_manual_review_required
