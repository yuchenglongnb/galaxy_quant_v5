# AmazingData Query Mode Differential Probe

## 1. Scope

- date: `20260615`
- stock_code: `600519.SH`
- index_code: `000001.SH`
- login_modes: `implicit_query, explicit_login_continue, explicit_login_strict`

## 2. Per-Query Result

| login_mode | query_case | code | status | stage | login_returned | login_exception_type | row_count | elapsed_sec |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |
| implicit_query | stock_day | 600519.SH | query_timeout | query | None | - | 0 | 45.0477 |
| explicit_login_continue | stock_day | 600519.SH | query_timeout | query | None | - | 0 | 45.1344 |
| explicit_login_strict | stock_day | 600519.SH | login_failed | login | False | system_exit_during_login | 0 | 36.6648 |

## 3. Diagnosis

- diagnosis: `query_path_times_out_even_without_successful_explicit_login`

## 4. Recommended Next Step

- Strict explicit login fails, but implicit and continue modes both reach a long-running query path. This points away from index-only blame and toward a broader query-path or service-mode issue.