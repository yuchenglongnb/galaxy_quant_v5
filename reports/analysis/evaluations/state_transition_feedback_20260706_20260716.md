# State Transition Feedback

Candidate-level and sector-only evidence are kept separate.

| decision | feedback | baseline | shadow | decision level | feedback level | valid pair | feedback label | contradictions |
|---|---|---|---|---|---|---|---|---|
| 20260706 | 20260707 | trend_enabled | weak_continuation | candidate_close | candidate_close | True | broad_continuation_failed | baseline_trend_enabled_but_broad_trend_failed, continuation_but_negative_trend_body |
| 20260707 | 20260708 | block_broad_longs | broad_trend_failure_risk | candidate_close | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260708 | 20260709 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260709 | 20260710 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260710 | 20260713 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260713 | 20260714 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260714 | 20260715 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
| 20260715 | 20260716 | - | data_insufficient | sector_range_context | sector_range_context | False | sector_context_only_no_daily_price_confirmation | candidate_feedback_missing |
