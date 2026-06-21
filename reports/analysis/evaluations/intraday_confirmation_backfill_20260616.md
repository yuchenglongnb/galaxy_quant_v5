# Intraday Confirmation Backfill Diagnosis 20260616

## Core Status

- trend_total: `108`
- stock_trend_total: `101`
- intraday_dir_exists: `False`
- current_confirmation_available: `False`
- board_index_fallback_attached_count: `80`
- board_index_fallback_coverage: `0.7921`
- board_index_codes_used: `['000001.SH', '000688.SH', '399001.SZ', '399006.SZ']`

## Existing Files

| file | exists |
| --- | --- |
| stocks_1min.csv | False |
| etf_1min.csv | False |
| indices_1min.csv | False |
| stock_confirmation_latest.csv | False |

## Universe Summary

- needed_stock_codes: `101`
- needed_benchmark_etf_codes: `3`
- needed_benchmark_index_codes: `4`
- expected_confirmation_rows: `101`

## Missing Cache Counts

- missing_stock_intraday_count: `101`
- missing_benchmark_etf_intraday_count: `3`
- missing_benchmark_index_intraday_count: `4`