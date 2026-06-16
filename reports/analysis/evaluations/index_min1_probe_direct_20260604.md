# Index Min1 Probe Login Bootstrap 20260604

## 1. Probe Scope

- timeout_sec: `120`
- query_window.start: `20260604 09:30:00`
- query_window.end: `20260604 10:00:00`
- query_window.period: `min1`
- query_window_effective: `full_day_query_kline_call_in_current_implementation`

## 2. Same-Process Result

| code | execution_model | status | stage | elapsed_sec | row_count | error_type |
| ---- | --------------- | ------ | ----- | ----------: | --------: | ---------- |
| 000001.SH | direct_process | login_failed | login | 36.7627 | 0 | system_exit_during_login |

## 3. Subprocess Result

| code | execution_model | status | worker_bootstrap_status | stage | elapsed_sec | row_count | error_type |
| ---- | --------------- | ------ | ----------------------- | ----- | ----------: | --------: | ---------- |

## 4. Diagnosis Matrix

- same-process diagnosis: `all_failed_login_bootstrap`
- subprocess diagnosis: `mixed_failure`
- matrix diagnosis: `needs_more_bootstrap_diagnosis`

## 5. Recommended Next Step

- Results are still mixed; compare same-process and subprocess initialization before deciding on query fallback.