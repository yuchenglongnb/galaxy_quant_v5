# Intraday Confirmation Backfill 20260616

- execute: `False`
- dry_run: `True`
- force: `False`
- stage: `index`
- begin_time: `930`
- end_time: `935`
- batch_size: `1`
- max_stocks: `0`
- only_codes: `[]`
- skip_existing: `False`

## Before

- stock_trend_total: `101`
- current_confirmation_available: `False`
- missing_stock_intraday_count: `101`
- missing_benchmark_etf_intraday_count: `3`
- missing_benchmark_index_intraday_count: `4`
- board_index_codes_used: `['000001.SH', '000688.SH', '399001.SZ', '399006.SZ']`

## Rebuild Result

- result: `{'rebuilt': False, 'skipped': True, 'reason': 'dry_run'}`
- written_files: `[]`

## After

- after_confirmation_available: `False`
- after_signal_enriched_count: `0`
- after_rs_vs_etf_coverage: `0.0`
- after_rs_vs_index_coverage: `0.0`
- after_amount_1m_ratio_coverage: `0.0`
- after_shadow_distribution: `{}`

## Stage Isolation

- event_count: `0`
- slow_batches: `0`
- failed_batches: `0`