# AmazingData Login Differential Trace

## 1. Scope

Only compare AmazingData login behavior. No market-data query is executed here.

## 2. test_api Trace

| metric | value |
| --- | --- |
| login_style | keyword-int-port |
| port_type | int |
| login_returned | False |
| system_exit_during_login | True |
| system_exit_code | - |
| after_login_marker_reached | False |

## 3. Shared Helper Trace

| login_style | status | login_returned | system_exit | system_exit_code | elapsed_sec | error_type |
| --- | --- | --- | --- | --- | ---: | --- |
| positional-str-port | login_failed | False | False | None | 3.6153 | login_failed |
| positional-int-port | login_failed | False | True | 0 | 37.1286 | system_exit_during_login |
| keyword-str-port | login_failed | False | False | None | 37.131 | login_failed |
| keyword-int-port | login_failed | False | True | 0 | 70.3777 | system_exit_during_login |

## 4. Diagnosis

- diagnosis: `both_system_exit_0`

## 5. Recommended Next Step

- direct test_api and helper both hit SystemExit(0); treat this as an SDK login control-flow issue first.