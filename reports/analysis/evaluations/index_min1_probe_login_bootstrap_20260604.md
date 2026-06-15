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

## 3. Subprocess Result

| code | status | worker_bootstrap_status | stage | elapsed_sec | row_count | error_type |
| ---- | ------ | ----------------------- | ----- | ----------: | --------: | ---------- |
| 000001.SH | bootstrap_failed | bootstrap_failed | login | 8.0811 | 0 | bootstrap_failed |
| 000688.SH | bootstrap_failed | bootstrap_failed | login | 6.1824 | 0 | bootstrap_failed |
| 399006.SZ | bootstrap_failed | bootstrap_failed | login | 6.6185 | 0 | bootstrap_failed |

## 4. Diagnosis Matrix

- same-process diagnosis: `mixed_failure`
- subprocess diagnosis: `all_failed_bootstrap`
- matrix diagnosis: `needs_more_bootstrap_diagnosis`

## 5. Recommended Next Step

- Results are still mixed; compare same-process and subprocess initialization before deciding on query fallback.