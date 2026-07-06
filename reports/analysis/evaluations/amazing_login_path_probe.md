# P2.3E AmazingData Login Path Probe

This report is diagnostic-only. It does not contain credential values, supplier logs, market data, trading instructions, or strategy changes.

## Summary

- diagnosis: `all_available_styles_system_exit_0_or_failed`
- successful_styles: `-`
- system_exit_styles: `style_a_build_login_invocation_keyword_int_port, style_b_build_login_invocation_positional_int_port, style_c_direct_keyword_args, style_d_positional_args, style_e_existing_project_helper_exact`
- failed_styles: `-`

## Style Results

| style | status | system_exit_code | ambiguous_success | login_returned | logout_attempted | error_type | sanitized_error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `style_a_build_login_invocation_keyword_int_port` | `system_exit` | `0` | `True` | `False` | `False` | `SystemExit` | `0` |
| `style_b_build_login_invocation_positional_int_port` | `system_exit` | `0` | `True` | `False` | `False` | `SystemExit` | `0` |
| `style_c_direct_keyword_args` | `system_exit` | `0` | `True` | `False` | `False` | `SystemExit` | `0` |
| `style_d_positional_args` | `system_exit` | `0` | `True` | `False` | `False` | `SystemExit` | `0` |
| `style_e_existing_project_helper_exact` | `system_exit` | `0` | `True` | `False` | `False` | `system_exit_during_login` | `system_exit_during_login:0` |

## Interpretation

`SystemExit(0)` is classified as ambiguous login control flow, not as a successful login. Query/backfill is gated behind a style with `status=ok`.
