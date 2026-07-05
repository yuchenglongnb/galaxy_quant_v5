# P2.0 Available Feedback Sources Inventory

## Scope

This inventory maps available reports into temporal feedback capabilities.

| Group | Path / pattern | Timepoint | Date range | Real codes | Path metrics | T+1 metrics | Forward metrics | Loop value | Usable now | Missing fields | Next action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A. auction decision reports | `reports/analysis/daily/*/auction_review.md` | auction | mixed | partial | no | no | no | high | partial | structured decision view | P2.1 structure decision records |
| B. 09:35 confirmation reports | `reports/analysis/evaluations/recent_0935_confirmation_backfill_20260622_20260626.*` | same_day_0935 | 20260622-20260626 | likely | partial | no | no | high | held | formalized parser | P2.1/P2.2 |
| C. midday reports | none identified | same_day_midday | n/a | no | no | no | no | high | missing | midday data source | add capability |
| D. close full analysis reports | daily validation / signal detail outputs | same_day_close | mixed | yes | body only | no | no | high | partial | unified schema | join to matrix |
| E. next-day analysis reports | not structured yet | next_day_plan | n/a | no | no | partial | no | medium | missing | next-day plan schema | add capability |
| F. T+1 validation reports | P1.5 T+1 outputs and path replay summaries | t1_close | 20260626-20260702 | yes | yes | yes | no | high | partial | denominator reconciliation | extend matrix |
| G. P1.5 intraday path reports | `reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json` | same_day_close / t1_close | 20260626-20260702 | yes | yes | yes | no | high | yes | per-record join | P2.1/P2.2 |
| H. P1.7 CP evidence reports | `reports/analysis/evaluations/cp_*_20260622_20260626.*` | evidence review | 20260622-20260626 | yes | no | no | no | high | yes | temporal horizon | gate join |
| I. P1.9 prior-day context reports | `reports/analysis/evaluations/prior_day_context_stock_effect*.json` | auction -> same_day_close proxy | 20260608-20260626 | yes | body proxy | no | no | high | yes | path and T+1 join | seed matrix |
| J. ETF / benchmark reports | ETF / benchmark untracked reports | benchmark context | 20260622-20260626 | likely | partial | no | no | medium | held | formalized index | P2.3/P2.4 |
| K. trend confirmation reports | recent confirmation untracked reports | same_day_0935 | 20260622-20260626 | likely | partial | no | no | high | held | parser and schema | P2.1 |
| L. market-structure reports | market-structure backfill assets | regime/snapshot | 20260622-20260626 | no | no | no | no | high | held | execute safety gate | P2.x safety refactor |

## Missing Capabilities

- Structured 09:35 feedback by decision id.
- Structured midday feedback.
- Structured close / next-day plan decision view.
- T+5 / T+10 / T+20 forward-horizon feedback.
- Regime snapshot join.
- Per-record join between prior-day context and intraday path type.

## Seed Coverage

P2.0 seed coverage is intentionally narrow:

```text
prior_day_context -> same_day_close
prior_day_context -> rank_change
prior_day_context -> body_pct
prior_day_context -> validation_success
```

This is enough to prove the matrix contract, not enough for rule proposals.
