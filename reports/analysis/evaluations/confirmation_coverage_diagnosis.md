# Confirmation Coverage Diagnosis

## 1. Diagnosis Scope

- start: `20260506`
- end: `20260612`
- days_scanned: `28`

## 2. Coverage Summary

| date | raw_trend | stock_data_codes | etf_data_codes | index_data_codes | code_intersection | etf_mapping | index_mapping | rs_vs_etf | rs_vs_index | amount_ratio | coverage_ratio | main_failure |
| ---- | --------: | ---------------: | -------------: | ---------------: | ----------------: | ----------: | ------------: | --------: | ----------: | -----------: | -------------: | ------------ |
| 20260506 | 52 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260507 | 97 | 0 | 0 | 0 | 0 | 12 | 12 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260508 | 84 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260511 | 69 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260512 | 47 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260513 | 22 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260514 | 34 | 0 | 0 | 0 | 0 | 11 | 11 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260515 | 11 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260518 | 3 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260519 | 23 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260520 | 45 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260521 | 942 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260522 | 169 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260525 | 288 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260526 | 64 | 0 | 0 | 0 | 0 | 15 | 15 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260527 | 41 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260528 | 11 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260529 | 20 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260601 | 13 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260602 | 16 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | stock_intraday_missing |
| 20260603 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | stock_intraday_missing |
| 20260604 | 25 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | 0 | 0.0000 | stock_intraday_missing |
| 20260605 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | stock_intraday_missing |
| 20260608 | 4 | 199 | 27 | 4 | 4 | 0 | 4 | 0 | 4 | 4 | 1.0000 | coverage_available |
| 20260609 | 14 | 199 | 27 | 4 | 13 | 0 | 13 | 0 | 13 | 13 | 0.9286 | coverage_available |
| 20260610 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260611 | 40 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |
| 20260612 | 30 | 0 | 0 | 0 | 0 | 2 | 2 | 0 | 0 | 0 | 0.0000 | intraday_cache_missing |

## 3. Failure Reason Distribution

| failure_reason | count |
| ------------------------------- | ----: |
| intraday_cache_missing | 22 |
| stock_intraday_missing | 4 |
| coverage_available | 2 |

## 4. 20260612 Deep Dive

- raw trend signals: `30`
- stock trend signals: `27`
- intraday dir exists: `False`
- confirmation file exists: `False`
- confirmation coverage ratio: `0.0000`
- trend filter status: `degraded_global_missing`
- failure flags: `intraday_cache_missing`
- main failure: `intraday_cache_missing`

结论：20260612 的 coverage=0 不是规则过严，而是 replay 当天本地没有 intraday confirmation 输入，属于数据缺失场景。

## 5. Recommended Minimal Fix

- 优先补齐 monitor / snapshot-backfill 的 intraday 落盘，避免 replay 时完全没有 confirmation 输入。