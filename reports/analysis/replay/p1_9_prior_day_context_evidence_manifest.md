# P1.9 Prior-day Context Evidence Manifest

## Included Reports

| Path | Type | Date | Size note | Readability | Loop use |
| --- | --- | --- | --- | --- | --- |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260608.json` | json | 20260608 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260608.md` | md | 20260608 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260609.json` | json | 20260609 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260609.md` | md | 20260609 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260616.json` | json | 20260616 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260616.md` | md | 20260616 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260618.json` | json | 20260618 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260618.md` | md | 20260618 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260622.json` | json | 20260622 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260622.md` | md | 20260622 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260623.json` | json | 20260623 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260623.md` | md | 20260623 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260624.json` | json | 20260624 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260624.md` | md | 20260624 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260625.json` | json | 20260625 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260625.md` | md | 20260625 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260626.json` | json | 20260626 | small | good | daily machine-readable evidence |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260626.md` | md | 20260626 | small | good | daily human-readable review |
| `reports/analysis/evaluations/prior_day_context_stock_effect_summary.json` | json | 20260608-20260626 | small | good | machine-readable summary |
| `reports/analysis/evaluations/prior_day_context_stock_effect_summary.md` | md | 20260608-20260626 | small | good | human-readable summary |

## Deferred Reports

No prior-day context reports are deferred in this P1.9 pack. Other research groups remain deferred:

- market-structure backfill assets
- ETF / benchmark assets
- trend / confirmation coverage assets
- intraday confirmation runtime reports

## Date Coverage

Included dates:

```text
20260608
20260609
20260616
20260618
20260622
20260623
20260624
20260625
20260626
```

Context available dates:

```text
20260608
20260609
20260618
20260622
20260623
20260624
20260625
20260626
```

## Metric Definitions

- `stock_candidate_total`: stock-only candidate count after excluding ETF/index/industry/unknown targets.
- `stock_true_bonus_count`: stock candidates with non-zero prior-day context bonus.
- `positive_bonus_count`: stock candidates with positive prior-day context bonus.
- `negative_bonus_count`: stock candidates with negative prior-day context bonus.
- `zero_bonus_count`: stock candidates with zero prior-day context bonus.
- `rank_changed_count`: candidates whose rank changed after context scoring.
- `bucket_changed_count`: signal bucket changes caused by context scoring; currently zero.
- `body_pct`: open-to-close body performance used by the existing validation output.
- `success_rate`: share of available samples marked validation success.

## Known Limitations

- Sample size remains limited.
- Positive bonus sample count is small.
- One evaluated date lacks prior-day context.
- The current report is stock-only and excludes ETF/index/industry targets.
- The report does not yet join with P1.5 intraday path types.
- The report does not yet provide contradiction tracking by market phase.

## Readability / Environment Notes

- No mojibake was detected in the prior-day report pack during P1.9 packaging.
- No credential-like content was detected.
- No trading-advice wording was detected.
- Real dates, codes, names, metrics, and outcomes are intentionally retained for loop analysis.

## How ChatGPT Should Use These Reports

ChatGPT should use this pack to answer:

- whether prior-day context changes ranking enough to matter
- whether positive/negative context groups behave differently
- whether context helps CP, reversal, or trend interpretation
- where sample counts are too small
- which dates are outliers
- what should be joined with intraday path evidence next

ChatGPT should not use this pack to issue trading instructions or propose immediate rule changes.

## Next Loop Questions

1. Do prior-day context effects remain stable in a broader window?
2. Do positive/negative context groups map to specific intraday path types?
3. Are rank-change dates also path-deterioration dates?
4. Which contradiction examples should enter a future gate?
5. Should prior-day context become a gate input only after a minimum sample threshold?
