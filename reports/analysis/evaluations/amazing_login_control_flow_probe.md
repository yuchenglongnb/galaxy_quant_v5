# P2.3F AmazingData Login Control-Flow Probe

This report is diagnostic-only. It does not contain credential values, supplier logs, market data, trading instructions, or strategy changes.

## Summary

- safe_to_query: `False`
- AmazingData online path: `blocked`
- permission hypothesis: `plausible_not_proven`
- fallback decision: `prepare_ths_mcp_fallback`

## Strategy Results

| strategy | status | system_exit_code | safe_to_query | permission_hypothesis | notes |
| --- | --- | --- | --- | --- | --- |
| `catch_system_exit_continue` | `system_exit` | `0` | `False` | `possible` | `system_exit_0_is_not_safe_to_query_by_default` |
| `catch_system_exit_then_logout` | `system_exit` | `0` | `False` | `possible` | `system_exit_0_is_not_safe_to_query_by_default` |
| `subprocess_exit_code_only` | `system_exit` | `0` | `False` | `possible` | `process_exited_without_framed_payload` |
| `existing_success_script_parity` | `inconclusive` | `None` | `False` | `possible` | `existing scripts show direct and helper login paths, but current P2.3E result has no successful login style, no market data query executed` |
| `vendor_permission_hypothesis` | `inconclusive` | `None` | `False` | `plausible_not_proven` | `manual_requires_login_before_api_calls, manual_indicates_sdk_credentials_ip_port_require_official_permission, config_ready_only_means_values_exist_not_permission_granted` |

## Interpretation

AmazingData online 09:35 backfill remains gated unless a strategy produces `safe_to_query=true`. Current fallback design should preserve the existing `stock_confirmation_0935.csv` artifact contract.
