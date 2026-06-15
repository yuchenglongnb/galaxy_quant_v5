# Index Min1 Probe Login Bootstrap 20260604

## 1. Probe Scope

- timeout_sec: `20`
- query_window.start: `20260604 09:30:00`
- query_window.end: `20260604 10:00:00`
- query_window.period: `min1`
- query_window_effective: `full_day_query_kline_call_in_current_implementation`

## 2. Same-Process Result

| code | status | elapsed_sec | row_count | error_type |
| ---- | ------ | ----------: | --------: | ---------- |

## 3. Subprocess Result

| code | status | worker_bootstrap_status | elapsed_sec | row_count | error_type |
| ---- | ------ | ----------------------- | ----------: | --------: | ---------- |
| 000001.SH | unknown_failed | bootstrap_failed | 6.5690 | 0 | unknown_failed |
| 000688.SH | unknown_failed | bootstrap_failed | 6.3048 | 0 | unknown_failed |
| 399006.SZ | unknown_failed | bootstrap_failed | 6.9676 | 0 | unknown_failed |

## 4. Diagnosis Matrix

- same-process diagnosis: `mixed_failure`
- subprocess diagnosis: `mixed_failure`
- matrix diagnosis: `needs_more_bootstrap_diagnosis`

## 5. Recommended Next Step

- Results are still mixed; compare same-process and subprocess initialization before deciding on query fallback.