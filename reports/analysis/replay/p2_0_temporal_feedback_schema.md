# P2.0 Temporal Feedback Schema

## Record Fields

Each temporal feedback record should follow this shape:

| Field | Meaning |
| --- | --- |
| `decision_id` | Stable identifier for the decision-feedback sample. |
| `trade_date` | Decision date. |
| `target_code` | Security code if available. |
| `target_name` | Security or group name. |
| `target_type` | stock / ETF / index / industry / group. |
| `decision_timepoint` | `auction`, `0935`, `midday`, `close`, or `next_day_plan`. |
| `signal_family` | CP / reversal / trend / ETF / prior_day_context / market_structure. |
| `signal_category` | Existing signal category or sub-bucket. |
| `decision_score` | Score available at decision time. |
| `decision_rank` | Rank available at decision time. |
| `decision_bucket` | Decision bucket at decision time. |
| `decision_view_fields` | Fields visible at decision time. |
| `prior_day_context_bonus` | Prior-day context bucket or numeric bonus if applicable. |
| `cp_risk_decision` | CP risk decision at decision time if available. |
| `trend_filter_decision` | Trend filter decision at decision time if available. |
| `path_type` | Same-day or later path type if available. |
| `feedback_timepoint` | Feedback horizon. |
| `feedback_date` | Feedback date. |
| `feedback_metric_set` | Metrics observed at feedback time. |
| `feedback_label` | Confirmation/failure label. |
| `contradiction_labels` | Contradiction labels. |
| `regime_snapshot` | Market regime fields. |
| `data_available` | Whether feedback data is available. |
| `missing_reason` | Missing-data reason. |
| `review_status` | analysis-only status. |

## Join Keys

Primary join key:

```text
trade_date + code
```

Fallback join key:

```text
trade_date + name + signal_category
```

Fallback joins must be counted separately because they can change denominator quality.

## Feedback Metric Set

At minimum:

```text
body_pct
validation_success
open_to_high_pct
open_to_low_pct
close_to_high_drawdown_pct
intraday_range_pct
mfe_pct
mae_pct
t1_open_return
t1_close_return
return_5d
return_10d
return_20d
```

Metric availability depends on the feedback horizon. Missing metrics should be stored as absent/null with a `missing_reason`, not inferred.

## Review Status

Allowed seed statuses:

```text
analysis_only_seed
partial_feedback_available
missing_feedback
needs_broader_window
needs_regime_join
blocked_missing_data
```

No status in this schema means a rule change is approved.
