# Intraday Min1 Backfill 20260629

- scope: `trend-candidates`
- target_time: `09:35`
- query_window: `09:30-09:35`
- candidate_count: `13`
- queryable_candidate_count: `12`
- industry_item_without_code: `['数字芯片设计']`

## Before / After

- before coverage_count: `0`
- after coverage_count: `11`
- root_cause_after: `other`
- trend_active_allowed: `False`

## Backfill

- attempted: `True`
- success_count: `11`
- failed_count: `1`
- partial_success: `True`
- generated_files: `['AmazingData_Store\\20260629\\intraday\\stocks_1min.csv', 'AmazingData_Store\\20260629\\intraday\\etf_1min.csv', 'AmazingData_Store\\20260629\\intraday\\indices_1min.csv', 'AmazingData_Store\\20260629\\intraday\\stock_confirmation_latest.csv']`
- failed_codes: `['159206.SZ']`
- warnings: `[]`

## Conclusion

- read_only_rule_state
- keep_trend_active_disabled
- no_strategy_rule_change
- do_not_fabricate_intraday_confirmation
- stock_intraday_minute_backfilled
- intraday_confirmation_coverage_recovered

## Recommended Next Actions

- rerun_trend_confirmation_coverage_audit
- keep_trend_active_disabled_until_multi_day_coverage_validation
