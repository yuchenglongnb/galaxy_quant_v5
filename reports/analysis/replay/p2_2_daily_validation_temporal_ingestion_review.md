# P2.2 Daily Validation Temporal Ingestion Review

## Scope

P2.2 extends `reports/temporal_feedback_matrix.py` so daily validation outputs can be converted into temporal decision-feedback records.

Input files:

- `reports/validation/daily/20260703/signal_detail.csv`
- `reports/validation/daily/20260703/signal_metrics.csv`

Output files:

- `reports/analysis/evaluations/temporal_feedback_matrix_daily_validation_seed.json`
- `reports/analysis/evaluations/temporal_feedback_matrix_daily_validation_seed.md`

This is analysis-only. It does not change strategy logic, signal ranking, evaluator behavior, thresholds, exemptions, registries, lessons, patterns, or trading behavior.

## Why Daily Validation Ingestion Matters

P2.0 defined the temporal decision-feedback loop, but the first seed matrix only covered prior-day context summaries. P2.1 added real 20260703 feedback artifacts and noted that daily validation outputs were not yet parsed into temporal records.

P2.2 closes that gap for same-day close feedback:

```text
auction decision
-> signal_detail.csv / signal_metrics.csv
-> same_day_close feedback record
-> feedback label
-> path contradiction labels
-> aggregate matrix summary
```

This makes daily validation artifacts directly usable by the loop, while keeping 09:35, midday, T+1, and forward-horizon feedback as explicit missing capabilities.

## Parsed Fields

The daily validation parser reads available fields from `signal_detail.csv` and handles missing optional fields safely.

Core fields:

- `date`
- `signal_category`
- `signal_family`
- `target_type`
- `code`
- `name`
- `body_pct`
- `validation_success`
- `signal_path_type`
- `open_to_high_pct`
- `open_to_low_pct`
- `mfe_pct`
- `mae_pct`
- `close_to_high_drawdown_pct`
- `intraday_range_pct`
- `t1_open_return`
- `t1_close_return`
- `t1_close_positive_rate`
- `market_regime`
- `theme_cluster`
- `validation_scope`
- `data_session_state`

Environment-specific runtime provenance such as `log_path` is not promoted into temporal matrix records.

## Record Schema

Each daily validation row becomes one record with:

- `decision_id = auction:<date>:<signal_category>:<code_or_name>`
- `decision_timepoint = auction`
- `feedback_timepoint = same_day_close`
- `review_status = analysis_only_daily_validation`
- `feedback_metric_set` containing close/body/path metrics
- `contradiction_labels` derived from path and close feedback

The parser does not infer missing metrics. Missing values remain null or produce `missing_feedback`.

## Feedback Labels

Initial close-feedback labels:

- `confirmed_close`
- `failed_close`
- `mixed_close`
- `missing_feedback`

These labels are posterior validation labels. They are not trading instructions and do not imply rule changes.

## Contradiction Labels

Initial path / close contradiction labels:

- `path_risk_after_auction`
- `close_success_but_intraday_fade_risk`
- `close_failed_but_path_repaired`
- `auction_strength_failed_close`
- `auction_feedback_confirmed_close`

These labels mark review candidates for future temporal attribution. They are not strategy triggers.

## 20260703 Summary

Daily validation records:

- total daily records: `52`
- by signal category:
  - `trap`: `8`
  - `reversal`: `16`
  - `trend`: `28`

Feedback label distribution:

- `confirmed_close`: `26`
- `failed_close`: `18`
- `mixed_close`: `8`

Path type distribution:

- `range_chop`: `20`
- `close_near_high`: `10`
- `one_way_selloff`: `6`
- `high_open_trap`: `5`
- `rush_up_fade`: `4`
- `close_near_low`: `3`
- `low_open_rebound_failed`: `2`
- `unknown`: `2`

Contradiction label distribution:

- `auction_feedback_confirmed_close`: `25`
- `path_risk_after_auction`: `15`
- `auction_strength_failed_close`: `11`
- `close_failed_but_path_repaired`: `5`
- `close_success_but_intraday_fade_risk`: `4`

Signal-family aggregates:

- `trap`: success rate `37.5%`, avg body `0.6280`, path-risk count `2`
- `reversal`: success rate `75.0%`, avg body `0.9663`, path-risk count `3`
- `trend`: success rate `50.0%`, avg body `-0.1851`, path-risk count `10`

The full matrix has `79` records because it retains the existing prior-day-context seed records and adds `52` daily validation records.

## Missing Capabilities

Still missing:

- `auction -> same_day_0935`
- `auction -> same_day_midday`
- `0935 -> same_day_midday`
- `close -> t1_auction`
- `close -> t5_close`
- `close -> t10_close`
- `close -> t20_close`

P2.2 intentionally does not fill these gaps. It only ingests same-day close validation from daily validation outputs.

## What This Does Not Support

P2.2 does not support:

- CP threshold changes
- CP exemption expansion
- Trend active enablement
- reversal trigger changes
- signal/ranking/shortlist/evaluator changes
- strategy/config/registry changes
- lesson / pattern writes
- trading advice

## Next Expansion

Recommended next steps:

1. `P2.3 Auction -> 09:35 Feedback Ingestion`
2. `P2.4 Midday Feedback Ingestion`
3. `P2.5 T+1 Auction / Close Feedback Ingestion`
4. `P2.6 Forward 5D/10D/20D Feedback Expansion`
