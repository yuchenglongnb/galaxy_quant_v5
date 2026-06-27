# Intraday Confirmation Backfill 20260616

- execute: `True`
- dry_run: `False`
- force: `True`
- stage: `index`
- begin_time: `930`
- end_time: `935`
- batch_size: `1`
- max_stocks: `0`
- only_codes: `['000001.SH']`
- skip_existing: `False`
- isolated_query: `True`

## Before

- stock_trend_total: `101`
- current_confirmation_available: `False`
- missing_stock_intraday_count: `101`
- missing_benchmark_etf_intraday_count: `3`
- missing_benchmark_index_intraday_count: `4`
- board_index_codes_used: `['000001.SH', '000688.SH', '399001.SZ', '399006.SZ']`

## Rebuild Result

- result: `{'rebuilt': True, 'skipped': False, 'date': 20260616, 'index_count': 6, 'etf_count': 0, 'stock_count': 0, 'confirmation_path': './AmazingData_Store\\20260616\\intraday\\stock_confirmation_latest.csv', 'confirmation_history_path': './AmazingData_Store\\20260616\\intraday\\stock_confirmation_history.csv', 'source': 'historical_min1_only', 'mode': 'minimal', 'data_kind': 'min1', 'progress_path': 'C:\\Users\\40857\\Desktop\\galaxy_quant_v5\\reports\\analysis\\evaluations\\intraday_backfill_progress.jsonl', 'stage': 'index', 'bootstrap_mode': 'isolated_query'}`
- written_files: `['AmazingData_Store\\20260616\\intraday\\indices_1min.csv']`

## After

- after_confirmation_available: `False`
- after_signal_enriched_count: `0`
- after_rs_vs_etf_coverage: `0.0`
- after_rs_vs_index_coverage: `0.0`
- after_amount_1m_ratio_coverage: `0.0`
- after_shadow_distribution: `{'observe': 107, 'drop': 1}`

## Stage Isolation

- event_count: `8`
- slow_batches: `0`
- failed_batches: `0`