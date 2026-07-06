# P2.3 09:35 Feedback Source Inventory

## Scope

This inventory reviews available sources for `auction -> same_day_0935` feedback ingestion.

The scan focused on:

- `reports/analysis/evaluations/`
- `reports/analysis/replay/`
- `reports/analysis/daily/`
- `reports/validation/daily/`
- `AmazingData_Store/`
- `scripts/`
- `tests/`

## Source Inventory

| Path | Type | Date Range | 09:35 Price | 09:35 Return | Open Price | Signal Code | Signal Name | Signal Category | Usable Now | Missing Fields | Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `AmazingData_Store/20260629/intraday/stock_confirmation_latest.csv` | confirmation csv | 20260629 | yes: `last` | yes: `pct`, `price_vs_open_pct` | yes: `open` | yes | yes | no | yes | decision rows must be joined from daily validation | use for P2.3 real seed |
| `AmazingData_Store/20260622-20260626/intraday/stock_confirmation_latest.csv` | confirmation csv | 20260622-20260626 | yes | yes | yes | yes | yes | no | yes | requires matching daily validation rows | candidate for broader 09:35 expansion |
| `AmazingData_Store/20260608/20260609/20260616/intraday/stock_confirmation_latest.csv` | confirmation csv | 20260608, 20260609, 20260616 | yes | yes | yes | yes | yes | no | maybe | older schema / coverage should be reviewed | archive / future expansion |
| `reports/validation/daily/20260629/signal_detail.csv` | decision csv | 20260629 | no | no | no | partial / older schema mostly name-based | yes | yes | yes | requires 09:35 confirmation join by code or name | use with 20260629 confirmation |
| `reports/validation/daily/20260703/signal_detail.csv` | decision csv | 20260703 | no | no | no | yes | yes | yes | no for 09:35 | no `AmazingData_Store/20260703/intraday/stock_confirmation_latest.csv` found | keep as missing capability |
| `reports/analysis/evaluations/recent_0935_confirmation_backfill_20260622_20260626.json` | backfill summary | 20260622-20260626 | summary only | summary only | summary only | aggregated | no row-level decision join | no | partial | not a direct parser input | use as provenance |
| `reports/analysis/evaluations/intraday_min1_backfill_20260629.json` | backfill summary | 20260629 | summary only | summary only | summary only | generated file list | no row-level decision join | no | partial | not a direct parser input | use as provenance |
| `scripts/backfill_intraday_min1_confirmation.py` | script | configurable | can generate | can generate | can generate | yes | yes | no | not run in P2.3 | execute path writes intraday cache | hold out; do not execute |
| `scripts/backfill_intraday_confirmation.py` | script | configurable | can generate | can generate | can generate | yes | yes | no | not run in P2.3 | execute path writes intraday cache | hold out; do not execute |

## 20260703 / 20260706 Status

No usable row-level `stock_confirmation_latest.csv` was found for 20260703. Therefore P2.3 uses 20260629 as a real historical parser seed and keeps 20260703 / 20260706 09:35 feedback as a missing capability.

## Conclusion

P2.3 can safely implement parser support using existing 20260629 row-level confirmation data. It should not run min1 backfill or any execute path. The next loop step should add a dedicated 09:35 data collection hook for 20260703/20260706 and future dates.
