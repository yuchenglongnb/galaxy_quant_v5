# Intraday Confirmation Availability 20260629

## Core Status

- intraday_confirmation_available: `True`
- coverage_count: `11`
- candidate_count: `13`
- root_cause: `other`
- trend_active_allowed: `False`
- conclusion: `['keep_trend_active_disabled', 'no_strategy_rule_change', 'read_only_audit']`

## Minute Data

- stock intraday dir exists: `True`
- stocks_1min: `True` rows=`66`
- stock_confirmation_latest: `True` rows=`11`
- indices_1min: `True` rows=`18`
- etf_1min: `True` rows=`18`
- root indices_noon: `True` rows=`28`
- root stocks_noon: `False` rows=`0`

## Candidate Matching

- trend_candidate_count: `13`
- code_matched_count: `12`
- code_unmatched_count: `1`
- intraday_intersection_count: `11`
- code_match_possible: `True`

## Missing Reasons

- stock_noon_missing: `1`

## Recommended Next Actions

- keep_trend_active_disabled_until_confirmation_coverage_recovers

## Warnings

- auction_and_close_exist_but_do_not_imply_0935_confirmation
- index_noon_exists_but_stock_noon_missing
