# Index Min1 Probe Login Bootstrap 20260604

## 1. Probe Scope

- timeout_sec: `20`
- query_window.start: `20260604 09:30:00`
- query_window.end: `20260604 10:00:00`
- query_window.period: `min1`
- query_window_effective: `full_day_query_kline_call_in_current_implementation`

## 2. Same-Process Result

| code | status | stage | elapsed_sec | row_count | error_type |
| ---- | ------ | ----- | ----------: | --------: | ---------- |
| 000001.SH | query_timeout | query | 20.1662 | 0 | query_timeout |

## 3. Subprocess Result

| code | status | worker_bootstrap_status | stage | elapsed_sec | row_count | error_type |
| ---- | ------ | ----------------------- | ----- | ----------: | --------: | ---------- |

## 4. Diagnosis Matrix

- same-process diagnosis: `all_timeout`
- subprocess diagnosis: `mixed_failure`
- matrix diagnosis: `needs_more_bootstrap_diagnosis`

## 5. Recommended Next Step

- Results are still mixed; compare same-process and subprocess initialization before deciding on query fallback.