# Residual Signal Detail Code Mapping Review 20260629 -> 20260701

- unique_problem_row_count: `10`
- raw_problem_counts: `{'unfilled': 7, 'ambiguous': 3, 'name_fallback': 2, 'unmatched': 1, 'ambiguous_blocked': 1}`
- confidence_distribution: `{'high': 0, 'medium': 0, 'low': 0, 'none': 10}`
- auto_patch_allowed: `False`

## Rows

- 20260629 #11 创业板: ambiguous,ambiguous_blocked,unmatched; candidates=['159915.SZ', '399006.SZ']; confidence=none
- 20260629 #26 数字芯片设计: name_fallback,unfilled; candidates=[]; confidence=none
- 20260630 #22 数字芯片设计: name_fallback,unfilled; candidates=[]; confidence=none
- 20260701 #8 印制电路板: unfilled; candidates=[]; confidence=none
- 20260701 #9 消费电子零部件及组装: unfilled; candidates=[]; confidence=none
- 20260701 #17 数字芯片设计: unfilled; candidates=[]; confidence=none
- 20260701 #19 创业板: ambiguous; candidates=['159915.SZ', '399006.SZ']; confidence=none
- 20260701 #22 创业板: ambiguous; candidates=['159915.SZ', '399006.SZ']; confidence=none
- 20260701 #83 IT服务: unfilled; candidates=[]; confidence=none
- 20260701 #84 军工电子: unfilled; candidates=[]; confidence=none

## Conclusion

- residual_code_mapping_manual_review_required
- original_signal_detail_not_modified
- derived_signal_detail_not_modified
- auto_patch_disabled
- ambiguous_name_not_silently_matched
- name_fallback_explicitly_counted
- no_strategy_rule_change
- cp_evaluator_change_not_required
- trend_evaluator_change_not_required
- lesson_pattern_not_written
