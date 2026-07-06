# P2.3 Auction -> 09:35 Feedback Schema

## Purpose

This schema defines how auction decisions are connected to same-day 09:35 feedback.

The labels are posterior validation evidence only. They are not trading instructions, rule changes, threshold changes, exemption changes, or Trend active enablement.

## Record Fields

| Field | Meaning |
| --- | --- |
| `decision_id` | Stable id such as `auction:<date>:<signal_category>:<code_or_name>:0935` |
| `trade_date` | Decision date |
| `target_code` | Stock / ETF / index code if available |
| `target_name` | Candidate name |
| `target_type` | Candidate type from daily validation |
| `decision_timepoint` | Always `auction` for P2.3 |
| `feedback_timepoint` | Always `same_day_0935` for P2.3 |
| `auction_open_price` | Open price from 09:35 confirmation source |
| `auction_pct` | Auction pct from daily validation source when available |
| `price_0935` | 09:35 last price |
| `return_0935_from_open` | 09:35 return from open, from `price_vs_open_pct` |
| `return_0935_from_prev_close` | 09:35 return from previous close, from `pct` |
| `relative_strength_0935` | Relative strength versus index, from `rs_vs_index_pct` |
| `benchmark_return_0935` | Reserved for benchmark return when available |
| `volume_ratio_0935` | 09:35 amount ratio, from `amount_1m_ratio` |
| `feedback_label` | Posterior 09:35 confirmation label |
| `contradiction_labels` | Posterior attribution labels |
| `data_available` | Whether a row-level 09:35 confirmation row was matched |
| `missing_reason` | Why 09:35 feedback is unavailable |
| `review_status` | `analysis_only_0935_feedback` |

## Join Keys

Preferred join:

```text
trade_date + code
```

Fallback join:

```text
trade_date + name
```

The fallback is needed for older daily validation files where candidate rows may not include a `code` column.

## Feedback Labels

Initial feedback labels:

- `auction_confirmed_by_0935`
- `auction_failed_by_0935`
- `auction_mixed_by_0935`
- `missing_0935_feedback`

For `trap` / CP-risk candidates, early weakness confirms the CP warning. For reversal and trend candidates, early strength confirms the auction decision.

## Contradiction Labels

Initial contradiction labels:

- `auction_high_open_failed_by_0935`
- `auction_weak_but_recovered_by_0935`
- `cp_warning_confirmed_early`
- `cp_warning_failed_early`
- `reversal_confirmed_early`
- `reversal_failed_early`
- `trend_confirmed_early`
- `trend_failed_early`
- `confirmed_0935_but_weak_vs_index`

These labels identify follow-up review candidates. They are not strategy triggers.

## Safety Boundary

P2.3 does not write lesson, pattern, registry, evaluator, config, strategy, or trading execution files.

P2.3 does not run min1 backfill or market-structure execute.
