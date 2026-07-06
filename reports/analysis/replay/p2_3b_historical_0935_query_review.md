# P2.3B Historical 09:35 Query Review

## Scope

P2.3B adds explicitly gated historical query modes to `scripts/collect_0935_feedback.py` and separates collection-source preference from parser-source preference.

## Why Historical Query Mode Is Needed

P2.3A defined the target 09:35 artifact but did not fetch missing row-level feedback. P2.3B provides the hook needed to fill that artifact from AmazingData historical snapshot or 1-minute K-line data when candidate rows exist.

## Parser Preference vs Collection Preference

Parser preference remains:

```text
stock_confirmation_0935.csv -> stock_confirmation_latest.csv
```

Collection preference is now:

```text
explicit --source-confirmation-file
-> stock_confirmation_latest.csv
-> historical-snapshot-query with --allow-online-query
-> historical-min1-kline with --allow-online-query
-> gap-only
```

The collector does not default to reading `stock_confirmation_0935.csv`, which prevents accidental self-read / self-rewrite.

## Snapshot Mode Design

`historical-snapshot-query` is intended to query candidate codes in the 09:35 window:

```text
begin_time = 93500000
end_time = 93559999
```

The resulting rows are standardized as strict 09:35 snapshot feedback.

## Min1 Fallback Design

`historical-min1-kline` is available as an explicit fallback. It uses 1-minute confirmation and records:

```text
strict_point_snapshot = false
timepoint_policy = min1_0935_bar
```

It does not use five-minute bars as strict 09:35 point values.

## 20260703 Query Result

Candidate source:

```text
reports/validation/daily/20260703/signal_detail.csv
```

Candidate count:

```text
52
```

Historical snapshot dry-run was attempted in the amazing environment with `--allow-online-query`. The first attempt exposed a script entry-path issue (`core` import path), which was fixed by adding the repository root to `sys.path`. The follow-up attempt did not return a structured JSON result from the SDK process, so no artifact was written and no supplier log was committed.

P2.3B therefore records 20260703 as still pending real historical 09:35 backfill.

## 20260706 Query Result

Candidate source:

```text
reports/validation/daily/20260706/signal_detail.csv
```

Status:

```text
missing
```

P2.3B does not query full-market 09:35 data without a candidate universe.

## Generated Artifacts

No real `stock_confirmation_0935.csv` artifact is included in this PR.

## Matrix Update Result

No 20260703 backfill matrix is generated because no real 20260703 09:35 artifact was produced.

## Remaining Gaps

1. 20260703 still needs a successful historical snapshot or min1 query result for the 52 candidates.
2. 20260706 first needs a daily validation candidate source.
3. Future hardening should isolate AmazingData SDK subprocess behavior so query failures always return structured JSON.

## What This Does Not Support

P2.3B does not support trading instructions, deterministic rule changes, threshold changes, exemption expansion, Trend active enablement, strategy changes, registry writes, runtime memory writes, or market-structure execute paths.
