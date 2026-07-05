# P2.1 Temporal Matrix Gap Note 20260703

## Summary

`reports/temporal_feedback_matrix.py --dry-run` was executed after generating the 20260703 daily feedback artifacts.

Current result:

```text
record_count = 27
measurable_pairs = prior_day_context -> same_day_close / rank_change / body_pct / validation_success
missing_sources = []
```

The seed builder remains aligned with P2.0, but it does not yet ingest `reports/validation/daily/YYYYMMDD/signal_detail.csv` or `signal_metrics.csv`.

## Decision

Do not force a broad tool rewrite in P2.1.

P2.1 submits the 20260703 feedback artifacts and documents the ingestion gap. The parser extension should be handled by a focused follow-up.

## Required Follow-up

Recommended follow-up:

```text
P2.2: Auction Feedback Matrix Daily Validation Ingestion
```

Expected P2.2 scope:

- read `reports/validation/daily/YYYYMMDD/signal_detail.csv`
- emit one temporal record per signal and feedback horizon
- map same-day close validation into `feedback_timepoint=same_day_close`
- preserve path fields such as `signal_path_type`, `mfe_pct`, `mae_pct`, and `close_to_high_drawdown_pct`
- add explicit missing rows for 09:35 and midday when intraday confirmation is unavailable

## Safety Boundary

The gap note is analysis-only. It does not change strategy logic, evaluator behavior, rankings, thresholds, exemptions, Trend active state, lesson records, pattern records, or registry files.
