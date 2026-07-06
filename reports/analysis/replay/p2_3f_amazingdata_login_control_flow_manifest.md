# P2.3F AmazingData Login Control-Flow Manifest

## Included Files

```text
scripts/amazing_login_control_flow_probe.py
scripts/run_amazing_login_control_flow_probe.py
tests/test_amazing_login_control_flow_probe.py
reports/analysis/evaluations/amazing_login_control_flow_probe.json
reports/analysis/evaluations/amazing_login_control_flow_probe.md
reports/analysis/replay/p2_3f_amazingdata_permission_checklist.md
reports/analysis/replay/p2_3f_market_data_provider_fallback_design.md
reports/analysis/replay/p2_3f_amazingdata_login_control_flow_review.md
reports/analysis/replay/p2_3f_amazingdata_login_control_flow_manifest.md
```

## Probe Summary

```text
safe_to_query = false
AmazingData online path = blocked
permission_hypothesis = plausible_not_proven
provider_fallback_decision = prepare_ths_mcp_fallback
```

## Generated Artifacts

```text
reports/analysis/evaluations/amazing_login_control_flow_probe.json
reports/analysis/evaluations/amazing_login_control_flow_probe.md
```

## Sensitive Content Boundary

This package does not commit:

```text
AmazingData username/password/host/port
THS MCP token/key/cookie/account
supplier logs
full-market raw snapshot dump
runtime memory writes
strategy/config/registry changes
```

## How ChatGPT Should Use This

Use this result to stop blind AmazingData query retries. The next path is either vendor permission clarification or a THS MCP provider adapter that writes the existing `stock_confirmation_0935.csv/meta` contract.
