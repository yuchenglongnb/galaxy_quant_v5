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
| 000001.SH | bootstrap_failed | 0.0000 | 0 | bootstrap_failed |
| 000688.SH | bootstrap_failed | 0.0010 | 0 | bootstrap_failed |
| 399006.SZ | bootstrap_failed | 0.0000 | 0 | bootstrap_failed |

## 3. Subprocess Result

| code | status | worker_bootstrap_status | elapsed_sec | row_count | error_type |
| ---- | ------ | ----------------------- | ----------: | --------: | ---------- |
| 000001.SH | bootstrap_failed | config_missing | 3.9151 | 0 | bootstrap_failed |
| 000688.SH | bootstrap_failed | config_missing | 3.6445 | 0 | bootstrap_failed |
| 399006.SZ | bootstrap_failed | config_missing | 3.7520 | 0 | bootstrap_failed |

## 4. Diagnosis Matrix

- same-process diagnosis: `all_failed_bootstrap`
- subprocess diagnosis: `all_failed_bootstrap`
- matrix diagnosis: `global_login_config_issue`

## 5. Recommended Next Step

- Both the current process and subprocess workers are missing usable AmazingData login config; restore environment injection first.
- Until credentials are injected, do not attribute the probe failure to the index min1 API itself.