# Intraday Cache Backfill Plan

## 1. Scope

- start: `20260604`
- end: `20260604`
- days_scanned: `1`

## 2. Backfill Candidate Summary

| date | has_daily | has_auction | raw_trend | intraday_dir | stock_intraday | etf_intraday | index_intraday | current_coverage | missing_type | recommended_action |
| ---- | --------- | ----------- | --------: | ------------ | -------------- | ------------ | -------------- | ---------------: | ------------ | ------------------ |
| 20260604 | True | True | 25 | True | False | False | False | 0.0000 | partial_intraday_missing | backfill_all_intraday |

## 3. Missing Type Distribution

| missing_type | count |
| ------------ | ----: |
| partial_intraday_missing | 1 |

## 4. Recommended Backfill Batch

- `20260604` | priority=84 | raw_trend=25 | missing_type=partial_intraday_missing | action=backfill_all_intraday

## 5. Expected Validation

- 回补后重新运行 `scripts/diagnose_confirmation_coverage.py`，确认 confirmation_coverage_ratio 是否提升。
- 回补后重新运行 `scripts/diagnose_benchmark_mapping.py`，确认 benchmark ETF / index 映射在 active 日期中是否被实际消费。
- 回补后重新运行 `scripts/evaluate_trend_filter.py`，确认 keep / observe / drop 是否从 data-missing-driven 转向 rule-driven。