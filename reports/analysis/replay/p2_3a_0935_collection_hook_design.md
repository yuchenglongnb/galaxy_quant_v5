# P2.3A 09:35 Collection Hook Design

## Scope

P2.3A defines a stable, timepoint-specific 09:35 feedback artifact for the temporal decision-feedback loop. The goal is to turn auction candidates into row-level 09:35 feedback evidence without changing strategy logic, thresholds, runtime memory, registries, or trading behavior.

This package is analysis-only. It standardizes local feedback artifacts and records missing capabilities when the required 09:35 source is unavailable.

## Target Artifacts

Primary 09:35 artifact:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_0935.csv
AmazingData_Store/<date>/intraday/stock_confirmation_0935_meta.json
```

Compatibility artifact:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_latest.csv
```

The temporal matrix should prefer `stock_confirmation_0935.csv` and only fall back to `stock_confirmation_latest.csv` when the timepoint-specific file is unavailable. This prevents later 10:00, midday, or close confirmation files from overwriting the semantic meaning of 09:35 feedback.

## CSV Contract

Minimum fields:

```text
date
code
name
target_type
source_signal_category
source_signal_family
timepoint
time_int
time_str
pre_close
open
last
pct
price_vs_open_pct
amount_1m_ratio
rs_vs_index_pct
rs_vs_etf_pct
volume_price_state
benchmark_code
benchmark_name
benchmark_source
data_source
collection_mode
data_available
missing_reason
```

Rows may be present even when 09:35 feedback is missing. In that case `data_available=False` and `missing_reason` records the gap.

## Meta Contract

Minimum JSON fields:

```text
date
target_timepoint
generated_at
candidate_source
candidate_count
matched_count
missing_count
data_source
collection_mode
query_window
timepoint_policy
notes
output_csv
output_meta
```

The meta file explains how the artifact was generated and whether it represents real matched 09:35 feedback or a gap-only record.

## Collection Modes

Supported or reserved collection modes:

```text
local_existing_confirmation
historical_snapshot_query
historical_min1_kline
live_snapshot_subscription
gap_only
```

P2.3A implements the offline-safe path first:

```text
local-existing-confirmation
gap-only
```

Online data acquisition modes are documented but intentionally not executed by default.

## Timepoint Policy

Supported policies:

```text
strict_0935_snapshot
nearest_before_or_equal_0935
first_minute_after_auction
min1_0935_bar
```

For strict 09:35 point feedback, future collection should prefer Level-1 snapshot or 1-minute confirmation. A 09:35 five-minute K-line can cover 09:35:00 through 09:39:59.999, so it should not be treated as a strict point-in-time 09:35 value.

## Candidate Universe

Default candidate source:

```text
reports/validation/daily/<date>/signal_detail.csv
```

The hook preserves candidate identity and signal grouping:

```text
code
name
target_type
signal_category
signal_family
```

Join policy:

```text
primary = code
fallback = name
```

## Safety Boundary

The hook does not:

- Run real trading.
- Produce buy/sell instructions.
- Change CP threshold, exemption, Trend active, ranking, evaluator, strategy, config, or registry behavior.
- Write lesson, pattern, or registry files.
- Run sync, rebuild, heavy audit, or market-structure execute paths.

All 09:35 labels remain posterior feedback evidence for the temporal loop.
