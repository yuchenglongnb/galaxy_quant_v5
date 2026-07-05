# P2.0 Regime Answer Framework

## Purpose

The "regime answer" is not a trading instruction. It is an evidence-ranking framework:

```text
regime_state x signal_family x feedback_horizon x path_type x performance
```

The purpose is to identify which signal families and path types appear more stable under a specific market environment, then decide what additional data is needed before any future rule proposal can be drafted.

## Framework Steps

1. Define regime features.
2. Define signal family.
3. Define feedback horizon.
4. Define path quality metrics.
5. Calculate stability by regime and horizon.
6. Track contradiction and counterexample rates.
7. Output evidence ranking only.

## Regime Features

Initial feature buckets:

```text
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

## Signal Families

```text
CP
reversal
trend
ETF
prior_day_context
market_structure
```

## Feedback Horizons

```text
same_day_0935
same_day_midday
same_day_close
t1_auction
t1_close
t5_close
t10_close
t20_close
```

## Path Quality Metrics

```text
body_pct
open_to_high_pct
open_to_low_pct
mfe_pct
mae_pct
close_to_high_drawdown_pct
intraday_range_pct
t1_close_return
max_forward_return_5d
max_drawdown_5d
```

## Initial Matrix

| Regime state | Signal family | Feedback horizon | Path type | Current performance evidence | Status |
| --- | --- | --- | --- | --- | --- |
| unknown / unjoined | prior_day_context | same_day_close | same_day_body_proxy | Seed matrix can compare positive/negative/zero context groups. | seed_only |
| retreat / mixed from P1.5 | CP | same_day_close / t1_close | low_open_rebound_failed / rush_up_fade | Existing reports suggest phase sensitivity and insufficient sample. | needs_broader_window |
| retreat / mixed from P1.5 | trend | same_day_close / t1_close | rush_up_fade / high_open_trap | Existing reports preserve weakness observations. | needs_path_join |

## Observation-only Example Wording

Allowed:

```text
In the current sample, this combination appears more stable.
Current evidence remains sample-limited.
Broader-window validation is required before any rule proposal.
```

Not allowed:

```text
affirmative trading instructions
active-mode enablement
threshold adjustment
exemption expansion
deterministic rule claims
```

## Next Requirements

Before a version-answer candidate can be reviewed:

- at least one broader-window sample
- stable denominator definitions
- contradiction rate
- out-of-sample confirmation
- regime snapshot join
- no reliance on one date or one phase
