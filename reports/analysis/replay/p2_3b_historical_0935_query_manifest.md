# P2.3B Historical 09:35 Query Manifest

## Included Files

```text
scripts/collect_0935_feedback.py
tests/test_collect_0935_feedback.py
reports/analysis/replay/p2_3b_amazingdata_0935_query_mode_design.md
reports/analysis/replay/p2_3b_historical_0935_query_review.md
reports/analysis/replay/p2_3b_historical_0935_query_manifest.md
reports/analysis/replay/p2_3b_0935_backfill_gap_20260703.md
reports/analysis/replay/p2_3b_0935_backfill_gap_20260706.md
```

## Generated Artifacts

No real 09:35 artifact is generated in this package.

## Query Modes Added

```text
historical-snapshot-query
historical-min1-kline
```

Both require:

```text
--allow-online-query
```

## Date Coverage

20260703:

```text
candidate_count = 52
artifact_generated = no
reason = historical snapshot dry-run did not return structured result
```

20260706:

```text
candidate_count = 0
artifact_generated = no
reason = missing daily validation candidate source
```

## Data Source

Potential data source when query succeeds:

```text
AmazingData historical snapshot
AmazingData historical min1 kline
```

No supplier credentials, raw full-market dump, or supplier logs are included.

## Timepoint Policy

Snapshot mode:

```text
strict_0935_snapshot
```

Min1 fallback:

```text
min1_0935_bar
```

## Tests

P2.3B adds or updates tests for:

- Collector does not self-read `stock_confirmation_0935.csv` by default.
- Explicit source confirmation file works.
- Online query modes require `--allow-online-query`.
- Historical snapshot query path can be mocked.
- Historical min1 query path can be mocked.
- Meta records collection mode and timepoint policy.
- Parser source preference remains unchanged.

## How ChatGPT Should Use This Result

Treat P2.3B as a query-mode foundation, not as a completed 20260703 backfill. The next loop should either fix AmazingData historical query execution or run the min1 fallback in a controlled subprocess, then regenerate `stock_confirmation_0935.csv` and the temporal matrix backfill.
