# P2.3A 09:35 Collection Hook Manifest

## Included Files

```text
scripts/collect_0935_feedback.py
tests/test_collect_0935_feedback.py
reports/temporal_feedback_matrix.py
tests/test_temporal_feedback_matrix.py
reports/analysis/replay/p2_3a_0935_collection_hook_design.md
reports/analysis/replay/p2_3a_0935_collection_hook_review.md
reports/analysis/replay/p2_3a_0935_collection_hook_manifest.md
reports/analysis/replay/p2_3a_0935_collection_gap_20260703.md
reports/analysis/replay/p2_3a_0935_collection_gap_20260706.md
```

## Generated Outputs

No real 20260703 or 20260706 `stock_confirmation_0935.csv` artifact is included in this PR.

Reason:

```text
20260703: candidate source exists, but local row-level 09:35 confirmation is missing.
20260706: candidate source and local row-level 09:35 confirmation are both missing.
```

## Deferred Outputs

```text
AmazingData_Store/20260703/intraday/stock_confirmation_0935.csv
AmazingData_Store/20260703/intraday/stock_confirmation_0935_meta.json
AmazingData_Store/20260706/intraday/stock_confirmation_0935.csv
AmazingData_Store/20260706/intraday/stock_confirmation_0935_meta.json
```

These should only be generated from a real row-level snapshot, 1-minute confirmation, or local confirmation source.

## How ChatGPT Should Use This

Use the design and gap reports to understand exactly what data is required before filling `auction -> same_day_0935` records for 20260703 and 20260706.

Use the hook as the standard offline transformation step once local confirmation files exist:

```bash
python scripts/collect_0935_feedback.py --date <YYYYMMDD> --dry-run
python scripts/collect_0935_feedback.py --date <YYYYMMDD>
```

Use `stock_confirmation_0935.csv` as the preferred temporal matrix input and treat `stock_confirmation_latest.csv` only as compatibility fallback.

## Next Loop Questions

1. Which data acquisition mode should fill 20260703 and 20260706 first?
2. Should strict 09:35 use snapshot, nearest snapshot, or 1-minute confirmation?
3. Which benchmark should define `rs_vs_index_pct` and `rs_vs_etf_pct` for each signal family?
4. Should future live collection write `latest` as a separate compatibility copy, or only write timepoint-specific artifacts?

## Safety Boundary

This package is analysis-only. It does not change strategy logic, thresholds, exemptions, Trend active state, evaluator behavior, configs, registries, lessons, patterns, runtime memory, or trading behavior.
