# P2.3A 09:35 Collection Hook Review

## Scope

P2.3A adds a collection hook and artifact contract for `auction -> same_day_0935` feedback. It makes 09:35 a stable timepoint asset instead of relying only on a mutable `latest` confirmation file.

## Why A Timepoint-specific Artifact Is Needed

P2.3 proved that row-level 09:35 feedback can be ingested into the temporal matrix, but it used:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_latest.csv
```

That filename is useful as a compatibility source, but it is not stable enough for long-horizon temporal attribution. Later intraday checkpoints can overwrite the meaning of "latest". P2.3A therefore introduces:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_0935.csv
AmazingData_Store/<date>/intraday/stock_confirmation_0935_meta.json
```

## Artifact Contract

The 09:35 CSV stores candidate identity, source signal grouping, 09:35 price/relative-strength fields, benchmark fields, collection mode, and missing-data status.

The meta JSON records candidate source, matched count, missing count, data source, collection mode, query window, timepoint policy, and output paths.

## Collection Modes

Implemented offline-safe modes:

```text
local-existing-confirmation
gap-only
```

Reserved future modes:

```text
historical_snapshot_query
historical_min1_kline
live_snapshot_subscription
```

The hook does not log in to data vendors or run online acquisition by default.

## Data Source Inventory

20260703:

```text
candidate source: reports/validation/daily/20260703/signal_detail.csv
candidate_count: 52
local 09:35 confirmation: missing
artifact generated: no
```

20260706:

```text
candidate source: missing
local 09:35 confirmation: missing
artifact generated: no
```

## Parser Compatibility Update

`reports/temporal_feedback_matrix.py` now resolves 09:35 confirmation sources in this order:

```text
1. AmazingData_Store/<date>/intraday/stock_confirmation_0935.csv
2. AmazingData_Store/<date>/intraday/stock_confirmation_latest.csv
```

This preserves P2.3 compatibility while making future timepoint-specific artifacts the preferred source.

## Tests

P2.3A adds fixture-based tests for:

- Dry-run no-write behavior.
- Local existing confirmation standardization.
- Gap rows and meta output when confirmation is missing.
- Code join and name fallback join.
- No overwrite of `stock_confirmation_latest.csv` unless explicitly requested.
- Parser preference for `stock_confirmation_0935.csv` over `latest`.
- No lesson, pattern, registry, or credential-like output paths.

## Remaining Gaps

20260703 and 20260706 still need real row-level 09:35 confirmation sources before standardized artifacts can be generated.

Future work should add a deliberately authorized historical or live snapshot mode, then backfill those dates through the same artifact contract.

## What This Does Not Support

P2.3A does not support trading instructions, deterministic rule changes, threshold changes, exemption expansion, Trend active enablement, strategy changes, registry writes, or runtime memory updates.
