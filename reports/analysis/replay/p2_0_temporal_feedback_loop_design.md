# P2.0 Temporal Decision Feedback Loop Design

## Core Goal

P2.0 upgrades the project from single-point validation to temporal decision-feedback validation.

The system should track:

```text
decision timepoint
-> visible information at decision time
-> staged feedback
-> path confirmation / failure
-> delayed feedback
-> attribution labels
-> market regime snapshot
-> next loop recommendation
```

This is an analysis-only loop. It does not modify thresholds, exemptions, Trend active status, strategy logic, evaluator logic, configs, registry files, lesson records, or pattern records.

## Decision Timepoints

| Timepoint | Meaning |
| --- | --- |
| `auction` | Pre-open / auction decision context. |
| `0935` | Early confirmation decision context. |
| `midday` | Midday reassessment context. |
| `close` | End-of-day analysis context. |
| `next_day_plan` | Tomorrow-plan context generated after close. |

## Feedback Timepoints

| Timepoint | Meaning |
| --- | --- |
| `same_day_0935` | First early-market feedback after auction. |
| `same_day_midday` | Midday path feedback. |
| `same_day_close` | Same-day close validation. |
| `t1_auction` | Next trading day auction feedback. |
| `t1_0935` | Next trading day 09:35 feedback. |
| `t1_midday` | Next trading day midday feedback. |
| `t1_close` | Next trading day close feedback. |
| `t5_close` | Five-trading-day delayed feedback. |
| `t10_close` | Ten-trading-day delayed feedback. |
| `t20_close` | Twenty-trading-day delayed feedback. |

## Decision-feedback Pairs

Initial target pairs:

```text
auction -> same_day_0935
auction -> same_day_midday
auction -> same_day_close
auction -> t1_auction
auction -> t1_close

0935 -> same_day_midday
0935 -> same_day_close
0935 -> t1_close

midday -> same_day_close
midday -> t1_close

close / next_day_plan -> t1_auction
close / next_day_plan -> t1_0935
close / next_day_plan -> t1_midday
close / next_day_plan -> t1_close
close / next_day_plan -> t5_close
close / next_day_plan -> t10_close
close / next_day_plan -> t20_close
```

## Feedback Metrics

Core metrics:

```text
open_to_high_pct
open_to_low_pct
mfe_pct
mae_pct
close_to_high_drawdown_pct
intraday_range_pct
body_pct
t1_open_return
t1_close_return
t1_close_positive_rate
max_forward_return_5d
max_drawdown_5d
return_5d
return_10d
return_20d
```

## Feedback Labels

```text
confirmed_early
failed_early
confirmed_midday
failed_midday
confirmed_close
failed_close
t1_confirmed
t1_failed
delayed_success
delayed_failure
fade_after_confirm
recover_after_fail
short_horizon_success_long_horizon_fail
short_horizon_fail_long_horizon_success
```

## Contradiction Labels

```text
high_score_but_failed_0935
high_score_but_failed_close
rank_up_but_path_weak
rank_down_but_path_strong
positive_context_but_weak_path
negative_context_but_strong_path
auction_strong_but_t1_failed
close_strong_but_next_auction_failed
environment_mismatch
```

## Environment / Regime Fields

```text
market_date
index_trend_state
market_breadth_state
theme_concentration_state
limitup_continuation_state
risk_appetite_state
volume_liquidity_state
semiconductor_or_mainline_state
etf_relative_strength_state
cp_risk_regime
trend_regime
reversal_regime
```

## Version-answer Definition

The current environment version answer is not trading advice. It is a staged statistical adaptation conclusion:

```text
Under the current regime, which signal family, feedback horizon, path type, rank bucket, and context group appears more stable in validation evidence.
```

Any version-answer candidate must remain evidence-ranked and sample-limited until broader-window, contradiction, and out-of-sample checks pass.

## Seed Implementation

P2.0 adds a seed matrix using currently available evidence:

- prior-day context stock-effect reports
- P1.5 intraday path distribution summary
- P1.5D path stability gate summary

The seed only covers a subset:

```text
prior_day_context -> same_day_close
prior_day_context -> rank_change
prior_day_context -> body_pct
prior_day_context -> validation_success
```

Missing horizons are explicitly tracked instead of being inferred.
