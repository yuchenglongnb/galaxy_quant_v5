# Rolling T+1 Validation 20260629 -> 20260701

- pair_count: `2`
- aggregate_join_quality: `{'total_candidate_count': 57, 'total_resolved_code_denominator': 54, 'total_manual_scope_excluded_count': 2, 'total_pending_blocked_count': 1, 'total_primary_code_join_count': 54, 'total_fallback_name_join_count': 0, 'total_unmatched_count': 0, 'all_pairs_code_keyed_complete': True}`

## Signal Type Aggregate Summary

{
  "CP风险": {
    "signal_count": 13,
    "resolved_count": 13,
    "avg_t1_close_return": 0.5467,
    "median_t1_close_return": null,
    "win_rate": 46.15,
    "positive_count": 6,
    "negative_count": 7,
    "pending_count": 0,
    "manual_scope_excluded_count": 0
  },
  "反核机会": {
    "signal_count": 22,
    "resolved_count": 22,
    "avg_t1_close_return": 1.0281,
    "median_t1_close_return": null,
    "win_rate": 63.64,
    "positive_count": 14,
    "negative_count": 8,
    "pending_count": 1,
    "manual_scope_excluded_count": 1
  },
  "趋势机会": {
    "signal_count": 19,
    "resolved_count": 19,
    "avg_t1_close_return": 1.5766,
    "median_t1_close_return": null,
    "win_rate": 68.42,
    "positive_count": 13,
    "negative_count": 6,
    "pending_count": 0,
    "manual_scope_excluded_count": 1
  }
}

## Observations

{
  "CP风险": {
    "sample_size": 13,
    "avg_t1_close_return": 0.5467,
    "win_rate": 46.15,
    "observation": "Resolved code-keyed sample=13, avg_t1_close=0.5467, win_rate=46.15; observation only.",
    "rule_change_supported": false
  },
  "反核机会": {
    "sample_size": 22,
    "avg_t1_close_return": 1.0281,
    "win_rate": 63.64,
    "observation": "Resolved code-keyed sample=22, avg_t1_close=1.0281, win_rate=63.64; observation only.",
    "rule_change_supported": false
  },
  "趋势机会": {
    "sample_size": 19,
    "avg_t1_close_return": 1.5766,
    "win_rate": 68.42,
    "observation": "Resolved code-keyed sample=19, avg_t1_close=1.5766, win_rate=68.42; observation only.",
    "rule_change_supported": false,
    "trend_active_supported": false
  }
}

## Conclusion

- rolling_t1_validation_completed
- code_keyed_join_used
- pending_ambiguity_preserved
- manual_scope_excluded_explicitly
- sample_size_insufficient_for_rule_change
- no_strategy_rule_change
- cp_evaluator_change_not_required
- trend_evaluator_change_not_required
- trend_active_kept_disabled
- lesson_pattern_not_written
- name_fallback_eliminated
- unmatched_eliminated
