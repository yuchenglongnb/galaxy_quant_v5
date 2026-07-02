# T+1 Backtest Input Integrity 20260630 -> 20260701

- official_blocked: `True`
- blocked_reason: `historical_aggregate_append_field_count_mismatch`
- signal_detail_has_code: `False`
- t1_join_analysis: `{'primary_code_join_count': 29, 'fallback_name_join_count': 1, 'unmatched_count': 0, 'join_quality': 'complete_with_name_fallback'}`

## Code-Keyed Summary

{
  "CP风险": {
    "count": 8,
    "matched": 8,
    "avg_t1_open_return": 0.3138,
    "t1_open_win_rate": 37.5,
    "avg_t1_close_return": -0.73,
    "t1_close_win_rate": 25.0
  },
  "反核机会": {
    "count": 15,
    "matched": 15,
    "avg_t1_open_return": -0.225,
    "t1_open_win_rate": 20.0,
    "avg_t1_close_return": 0.8328,
    "t1_close_win_rate": 66.67
  },
  "趋势机会": {
    "count": 7,
    "matched": 7,
    "avg_t1_open_return": -0.4161,
    "t1_open_win_rate": 14.29,
    "avg_t1_close_return": 0.7385,
    "t1_close_win_rate": 57.14
  }
}

## Name-Based Reference

{
  "CP风险": {
    "count": 8,
    "matched": 8,
    "avg_t1_open_return": 0.3138,
    "t1_open_win_rate": 37.5,
    "avg_t1_close_return": -0.73,
    "t1_close_win_rate": 25.0
  },
  "反核机会": {
    "count": 15,
    "matched": 14,
    "avg_t1_open_return": -0.2157,
    "t1_open_win_rate": 21.43,
    "avg_t1_close_return": 0.5751,
    "t1_close_win_rate": 64.29
  },
  "趋势机会": {
    "count": 7,
    "matched": 7,
    "avg_t1_open_return": -0.4161,
    "t1_open_win_rate": 14.29,
    "avg_t1_close_return": 0.7385,
    "t1_close_win_rate": 57.14
  }
}

## Conclusion

- t1backtest_input_integrity_issue
- code_keyed_join_required
- no_strategy_rule_change
- cp_evaluator_change_not_required
- trend_evaluator_change_not_required
- bad_csv_quarantine_required
- signal_detail_code_missing
