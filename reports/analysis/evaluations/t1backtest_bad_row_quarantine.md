# T+1 Backtest Bad Row Quarantine

- input_file: `reports\validation\auction_signal_validation.csv`
- malformed_row_count: `1`
- clean_row_count: `10982`
- dry_run: `False`
- original_file_modified: `False`

## Bad Rows

- line 10907: expected 57, actual 113, cause `historical_aggregate_append_field_count_mismatch`

## Conclusion

- bad_csv_quarantine_required
- original_file_not_modified
- no_strategy_rule_change
- cp_evaluator_change_not_required
- trend_evaluator_change_not_required
- lesson_pattern_not_written
- clean_temp_copy_written
