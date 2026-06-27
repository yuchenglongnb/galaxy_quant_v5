# Intraday Confirmation Backfill 20260616

- execute: `True`
- dry_run: `False`
- force: `True`
- stage: `confirmation`
- begin_time: `930`
- end_time: `935`
- batch_size: `120`
- max_stocks: `0`
- only_codes: `[]`
- skip_existing: `False`
- isolated_query: `False`
- selection_priority: `leading_cluster`

## Before

- stock_trend_total: `101`
- current_confirmation_available: `True`
- missing_stock_intraday_count: `41`
- missing_benchmark_etf_intraday_count: `3`
- missing_benchmark_index_intraday_count: `3`
- board_index_codes_used: `['000001.SH', '000688.SH', '399001.SZ', '399006.SZ']`
- selected_stock_preview: `['300476.SZ', '601138.SH', '688256.SH', '688676.SH', '300638.SZ', '300870.SZ', '000630.SZ', '000506.SZ', '002335.SZ', '301377.SZ', '688766.SH', '688183.SH', '601611.SH', '601975.SH', '000426.SZ', '601872.SH', '002402.SZ', '600141.SH', '601899.SH', '300990.SZ']`

## Rebuild Result

- result: `{'rebuilt': True, 'skipped': False, 'date': 20260616, 'index_count': 0, 'etf_count': 0, 'stock_count': 0, 'confirmation_path': './AmazingData_Store\\20260616\\intraday\\stock_confirmation_latest.csv', 'confirmation_history_path': './AmazingData_Store\\20260616\\intraday\\stock_confirmation_history.csv', 'source': 'historical_min1_only', 'mode': 'minimal', 'data_kind': 'min1', 'progress_path': 'C:\\Users\\40857\\Desktop\\galaxy_quant_v5\\reports\\analysis\\evaluations\\intraday_backfill_progress.jsonl', 'stage': 'confirmation', 'bootstrap_mode': 'shared_client'}`
- written_files: `['AmazingData_Store\\20260616\\intraday\\stocks_1min.csv', 'AmazingData_Store\\20260616\\intraday\\indices_1min.csv', 'AmazingData_Store\\20260616\\intraday\\stock_confirmation_latest.csv']`

## After

- after_confirmation_available: `True`
- after_signal_enriched_count: `60`
- after_rs_vs_etf_coverage: `0.0`
- after_rs_vs_index_coverage: `0.5556`
- after_amount_1m_ratio_coverage: `0.5556`
- after_shadow_distribution: `{'observe': 77, 'drop': 30, 'main': 1}`

## Stage Isolation

- event_count: `1`
- slow_batches: `0`
- failed_batches: `0`