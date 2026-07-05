# Temporal Feedback Matrix Seed

This report is analysis-only. It is not trading advice and does not justify rule changes.

- schema_version: `p2.0_seed`
- record_count: `27`
- measurable_pairs: `['prior_day_context -> same_day_close', 'prior_day_context -> rank_change', 'prior_day_context -> body_pct', 'prior_day_context -> validation_success']`
- missing_capabilities: `['auction -> same_day_0935', 'auction -> same_day_midday', '0935 -> same_day_midday', 'close -> t1_auction', 'close -> t5_close', 'close -> t10_close', 'close -> t20_close']`
- aggregate: `{'record_count': 27, 'avg_success_rate': 46.292, 'contradiction_counts': {'negative_context_but_strong_path': 5, 'rank_down_but_path_strong': 2, 'positive_context_but_weak_path': 3, 'rank_up_but_path_weak': 3}}`

## Sources

- prior_day_context: `[{'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260608.json', 'status': 'loaded_daily', 'date': '20260608'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260609.json', 'status': 'loaded_daily', 'date': '20260609'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260616.json', 'status': 'loaded_daily', 'date': '20260616'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260618.json', 'status': 'loaded_daily', 'date': '20260618'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260622.json', 'status': 'loaded_daily', 'date': '20260622'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260623.json', 'status': 'loaded_daily', 'date': '20260623'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260624.json', 'status': 'loaded_daily', 'date': '20260624'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260625.json', 'status': 'loaded_daily', 'date': '20260625'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_20260626.json', 'status': 'loaded_daily', 'date': '20260626'}, {'path': 'reports/analysis/evaluations/prior_day_context_stock_effect_summary.json', 'status': 'loaded_summary', 'dates': ['20260608', '20260609', '20260616', '20260618', '20260622', '20260623', '20260624', '20260625', '20260626']}]`
- intraday_path_distribution: `{'path': 'reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json', 'status': 'loaded', 'date_range': {'start': '20260626', 'end': '20260702'}}`
- path_stability_gate: `{'path': 'reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json', 'status': 'loaded', 'overall_status': 'insufficient_sample'}`

## Contradiction Labels

- negative_context_but_strong_path: `5`
- positive_context_but_weak_path: `3`
- rank_down_but_path_strong: `2`
- rank_up_but_path_weak: `3`

## Seed Records

- prior_day_context:20260608:positive_bonus: feedback=confirmed_close, contradictions=[], metrics={'avg_body_pct': 1.3025, 'median_body_pct': 1.7841, 'success_rate': 87.5, 'candidate_count': 8}
- prior_day_context:20260608:negative_bonus: feedback=confirmed_close, contradictions=['negative_context_but_strong_path'], metrics={'avg_body_pct': 2.0058, 'median_body_pct': 1.9698, 'success_rate': 50.0, 'candidate_count': 4}
- prior_day_context:20260608:zero_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260609:positive_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260609:negative_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260609:zero_bonus: feedback=confirmed_close, contradictions=[], metrics={'avg_body_pct': 0.4949, 'median_body_pct': 0.4101, 'success_rate': 50.0, 'candidate_count': 14}
- prior_day_context:20260616:positive_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260616:negative_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260616:zero_bonus: feedback=confirmed_close, contradictions=[], metrics={'avg_body_pct': 1.4772, 'median_body_pct': 1.3926, 'success_rate': 66.9811, 'candidate_count': 106}
- prior_day_context:20260618:positive_bonus: feedback=confirmed_close, contradictions=[], metrics={'avg_body_pct': 0.2778, 'median_body_pct': 0.2778, 'success_rate': 100.0, 'candidate_count': 1}
- prior_day_context:20260618:negative_bonus: feedback=confirmed_close, contradictions=['negative_context_but_strong_path', 'rank_down_but_path_strong'], metrics={'avg_body_pct': 2.4354, 'median_body_pct': 2.3357, 'success_rate': 80.9524, 'candidate_count': 42}
- prior_day_context:20260618:zero_bonus: feedback=mixed_close, contradictions=[], metrics={'avg_body_pct': 5.4221, 'median_body_pct': 5.9738, 'success_rate': 16.6667, 'candidate_count': 6}
- prior_day_context:20260622:positive_bonus: feedback=failed_close, contradictions=['positive_context_but_weak_path', 'rank_up_but_path_weak'], metrics={'avg_body_pct': -1.7886, 'median_body_pct': -1.7886, 'success_rate': 0.0, 'candidate_count': 1}
- prior_day_context:20260622:negative_bonus: feedback=confirmed_close, contradictions=['negative_context_but_strong_path', 'rank_down_but_path_strong'], metrics={'avg_body_pct': 1.6074, 'median_body_pct': 0.8453, 'success_rate': 58.1395, 'candidate_count': 43}
- prior_day_context:20260622:zero_bonus: feedback=mixed_close, contradictions=[], metrics={'avg_body_pct': 4.4167, 'median_body_pct': 4.0049, 'success_rate': 0.0, 'candidate_count': 6}
- prior_day_context:20260623:positive_bonus: feedback=failed_close, contradictions=['positive_context_but_weak_path', 'rank_up_but_path_weak'], metrics={'avg_body_pct': -5.858, 'median_body_pct': -5.858, 'success_rate': 0.0, 'candidate_count': 2}
- prior_day_context:20260623:negative_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260623:zero_bonus: feedback=failed_close, contradictions=[], metrics={'avg_body_pct': -2.5325, 'median_body_pct': -2.7575, 'success_rate': 36.0656, 'candidate_count': 61}
- prior_day_context:20260624:positive_bonus: feedback=confirmed_close, contradictions=[], metrics={'avg_body_pct': 12.538, 'median_body_pct': 12.538, 'success_rate': 100.0, 'candidate_count': 1}
- prior_day_context:20260624:negative_bonus: feedback=confirmed_close, contradictions=['negative_context_but_strong_path'], metrics={'avg_body_pct': 2.3315, 'median_body_pct': 3.2941, 'success_rate': 57.1429, 'candidate_count': 21}
- prior_day_context:20260624:zero_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260625:positive_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260625:negative_bonus: feedback=confirmed_close, contradictions=['negative_context_but_strong_path'], metrics={'avg_body_pct': 1.2686, 'median_body_pct': 0.126, 'success_rate': 54.1667, 'candidate_count': 24}
- prior_day_context:20260625:zero_bonus: feedback=mixed_close, contradictions=[], metrics={'avg_body_pct': 3.2003, 'median_body_pct': 3.5912, 'success_rate': 0.0, 'candidate_count': 7}
- prior_day_context:20260626:positive_bonus: feedback=failed_close, contradictions=['positive_context_but_weak_path', 'rank_up_but_path_weak'], metrics={'avg_body_pct': -1.6734, 'median_body_pct': -3.182, 'success_rate': 33.3333, 'candidate_count': 3}
- prior_day_context:20260626:negative_bonus: feedback=missing_feedback, contradictions=[], metrics={'avg_body_pct': None, 'median_body_pct': None, 'success_rate': None, 'candidate_count': 0}
- prior_day_context:20260626:zero_bonus: feedback=failed_close, contradictions=[], metrics={'avg_body_pct': -1.2502, 'median_body_pct': -2.7087, 'success_rate': 42.3077, 'candidate_count': 26}
