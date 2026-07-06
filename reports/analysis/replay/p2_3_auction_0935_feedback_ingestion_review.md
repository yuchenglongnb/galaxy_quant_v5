# P2.3 Auction -> 09:35 Feedback Ingestion Review

## Scope

P2.3 adds `auction -> same_day_0935` ingestion to the temporal feedback matrix.

The implementation reads:

- daily validation decision rows from `reports/validation/daily/<date>/signal_detail.csv`
- row-level 09:35 confirmation from `AmazingData_Store/<date>/intraday/stock_confirmation_latest.csv`

It does not run sync, min1 backfill, market-structure execute, or any trading command.

## Why 09:35 Feedback Matters

09:35 is the first practical post-auction feedback point. It helps separate:

- auction strength that continues immediately
- auction strength that fails early
- weak auction states that repair quickly
- candidates only confirmed later at close
- candidates confirmed early but vulnerable to midday or close fade

P2.3 converts this first feedback layer into temporal matrix records.

## Available Sources

P2.3 found usable row-level 09:35 data for 20260629:

- `reports/validation/daily/20260629/signal_detail.csv`
- `AmazingData_Store/20260629/intraday/stock_confirmation_latest.csv`

The confirmation file contains:

- `open`
- `last`
- `pct`
- `price_vs_open_pct`
- `amount_1m_ratio`
- `rs_vs_index_pct`
- `volume_price_state`

## Missing Sources

No usable row-level 09:35 confirmation source was found for 20260703 or 20260706 in the current workspace.

Therefore:

- P2.3 implements the parser with a real 20260629 seed.
- 20260703 / 20260706 remain explicit missing capabilities.
- Future work should add a 09:35 data collection hook.

## Matrix Parser Extension

New CLI options:

- `--include-0935-feedback`
- `--feedback-0935-root`

P2.3 keeps P2.0 and P2.2 behavior compatible:

- prior-day seed still works
- daily validation ingestion still works
- 09:35 ingestion is opt-in

## Real Seed Summary

Generated outputs:

- `reports/analysis/evaluations/temporal_feedback_matrix_0935_seed.json`
- `reports/analysis/evaluations/temporal_feedback_matrix_0935_seed.md`

Seed date:

- `20260629`

Summary:

- total matrix records: `54`
- 09:35 feedback records: `27`
- missing 09:35 feedback: `16`
- confirmed by 09:35: `7`
- failed by 09:35: `4`

By signal category:

- `trap`: `5`
- `reversal`: `9`
- `trend`: `13`

Feedback labels:

- `missing_0935_feedback`: `16`
- `auction_confirmed_by_0935`: `7`
- `auction_failed_by_0935`: `4`

Contradiction labels:

- `trend_confirmed_early`: `7`
- `trend_failed_early`: `4`
- `auction_high_open_failed_by_0935`: `3`
- `confirmed_0935_but_weak_vs_index`: `3`
- `auction_weak_but_recovered_by_0935`: `1`

## Relationship To 20260706 Watch Plan

P2.3 defines the exact record and label structure needed by the 20260706 watch plan. Once 20260706 09:35 confirmation data exists, it can be ingested through the same parser.

## What This Does Not Support

P2.3 does not support:

- CP threshold changes
- CP exemption expansion
- Trend active enablement
- signal/ranking/shortlist/evaluator changes
- strategy/config/registry changes
- lesson / pattern / registry writes
- trading advice

## Next Step

Recommended next step:

`P2.3A 09:35 Data Collection Hook`

This should collect row-level 09:35 confirmation for 20260703 / 20260706 and future dates without mixing in strategy rule changes.
