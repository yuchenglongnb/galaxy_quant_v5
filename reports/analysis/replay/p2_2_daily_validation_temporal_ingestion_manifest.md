# P2.2 Daily Validation Temporal Ingestion Manifest

## Included Outputs

| Path | Role |
| --- | --- |
| `reports/analysis/evaluations/temporal_feedback_matrix_daily_validation_seed.json` | Machine-readable temporal matrix seed with daily validation records |
| `reports/analysis/evaluations/temporal_feedback_matrix_daily_validation_seed.md` | Human-readable summary of the same seed |
| `reports/analysis/replay/p2_2_daily_validation_temporal_ingestion_review.md` | Review of parser behavior, labels, 20260703 summary, and limitations |
| `reports/analysis/replay/p2_2_daily_validation_temporal_ingestion_manifest.md` | This manifest |

## Input Data

| Path | Status | Use |
| --- | --- | --- |
| `reports/validation/daily/20260703/signal_detail.csv` | included in PR #8 | Per-candidate same-day close feedback |
| `reports/validation/daily/20260703/signal_metrics.csv` | included in PR #8 | Signal-family aggregate reference |

No raw `AmazingData_Store` files are included in this package.

## Date Coverage

Current real daily validation coverage in this seed:

- `20260703`

Prior-day context records from earlier P2.0/P1.9 reports are also retained by the matrix builder, so total record count is larger than the daily validation record count.

## Field Availability

Available for 20260703:

- same-day close body feedback
- validation success flag
- path type
- open/high/low/close-derived excursion fields
- MFE / MAE
- close-to-high drawdown
- intraday range
- market regime
- theme cluster
- target type

Not yet available in this ingestion path:

- 09:35 feedback
- midday feedback
- close-to-next-auction feedback
- T+1 09:35 / midday / close feedback
- forward 5D / 10D / 20D feedback

## Known Limitations

1. Daily validation records are posterior same-day close feedback, not pre-open decision instructions.
2. The initial feedback-label rule is intentionally simple and should be reviewed as more feedback horizons are added.
3. Some signal families, especially CP risk, use direction-specific validation logic. P2.2 preserves the existing `validation_success` flag and also records raw `body_pct`; downstream analysis should interpret the pair together.
4. `log_path` from runtime provenance is intentionally not copied into matrix records.
5. P2.2 does not parse auction review Markdown or runtime-memory lesson/pattern files.

## How ChatGPT Should Use This

Use the seed matrix to ask:

- Which signal families have same-day close confirmation?
- Which path types concentrate in failed or mixed feedback?
- Which candidates show path risk even when close feedback is positive?
- Which feedback horizons are still missing?
- Which labels should be expanded once 09:35, midday, and T+1 data arrive?

Do not use this matrix as a buy/sell instruction source.

## Next Loop Questions

1. Which 20260703 candidates were confirmed or invalidated by 09:35 on 20260706?
2. Which same-day close successes had intraday fade risk?
3. Which failed close outcomes had repaired path structure?
4. Does path-risk concentration persist across more daily validation dates?
5. How should CP risk directionality be represented in horizon-aware labels?
