# P2.3B AmazingData 09:35 Query Mode Design

## Scope

P2.3B extends the 09:35 feedback collection hook with explicitly authorized historical query modes. The purpose is to backfill row-level `auction -> same_day_0935` feedback from AmazingData historical data when local confirmation files are unavailable.

This is a data collection and evidence backfill tool. It does not change strategy logic, thresholds, exemptions, Trend active state, runtime memory, registries, or trading behavior.

## Source Preference Separation

Temporal matrix parser preference:

```text
1. stock_confirmation_0935.csv
2. stock_confirmation_latest.csv
```

Collection source preference:

```text
1. explicit --source-confirmation-file
2. stock_confirmation_latest.csv
3. historical_snapshot_query
4. historical_min1_kline
5. gap_only
```

The collector does not read `stock_confirmation_0935.csv` by default. This avoids self-read / self-rewrite behavior when a standardized artifact already exists.

## Online Query Gate

Historical query modes require:

```text
--allow-online-query
```

Without this flag, `historical-snapshot-query` and `historical-min1-kline` return `online_query_not_allowed` and do not write artifacts.

## Login And Config

AmazingData credential values must be loaded outside committed files.

Supported sources inherit the project login helper:

```text
environment variables
Windows persistent environment
local uncommitted .env
optional --amazing-local-config path
```

No credential values, connection endpoints, or supplier log content should be committed.

## Historical Snapshot Query

Mode:

```text
historical-snapshot-query
```

Target window:

```text
begin_time = 93500000
end_time = 93559999
```

Output semantics:

```text
data_source = amazingdata_query_snapshot
collection_mode = historical-snapshot-query
timepoint_policy = strict_0935_snapshot
strict_point_snapshot = true
```

The hook selects one row per candidate code inside the requested window and standardizes it to the P2.3A artifact contract.

## Historical Min1 Fallback

Mode:

```text
historical-min1-kline
```

Output semantics:

```text
data_source = amazingdata_query_kline_min1
collection_mode = historical-min1-kline
timepoint_policy = min1_0935_bar
strict_point_snapshot = false
```

The 1-minute 09:35 bar is treated as minute-level confirmation, not as a strict point snapshot.

## 5-minute K-line Boundary

A 09:35 five-minute K-line can cover 09:35:00 through 09:39:59.999. P2.3B therefore does not use a five-minute K-line as strict 09:35 point feedback.

## Output Contract

Generated artifacts, when real source data is available:

```text
AmazingData_Store/<date>/intraday/stock_confirmation_0935.csv
AmazingData_Store/<date>/intraday/stock_confirmation_0935_meta.json
```

The hook only queries the candidate universe from:

```text
reports/validation/daily/<date>/signal_detail.csv
```

It does not query or commit full-market raw snapshot dumps.
