# P2.3F AmazingData Login Control-Flow Review

## Scope

P2.3F isolates AmazingData login control flow after P2.3E found that all tested login styles return `SystemExit(0)`. This review does not query market data and does not attempt 09:35 backfill.

## Why Control-Flow Isolation Is Needed

P2.3E proved that call-style variation alone is not enough:

```text
5 login styles tested
0 successful login_returned styles
all styles SystemExit(0)
```

P2.3F checks whether catching `SystemExit(0)`, attempting logout, or allowing subprocess exit provides enough evidence to mark the session as usable.

## Strategies Tested

```text
catch_system_exit_continue
catch_system_exit_then_logout
subprocess_exit_code_only
existing_success_script_parity
vendor_permission_hypothesis
```

## Results

```text
safe_to_query = false
safe_strategies = []
system_exit_strategies = catch_system_exit_continue, catch_system_exit_then_logout, subprocess_exit_code_only
permission_hypothesis = plausible_not_proven
AmazingData online path = blocked
provider fallback decision = prepare_ths_mcp_fallback
```

## SystemExit(0) Interpretation

`SystemExit(0)` remains ambiguous SDK control flow. It is not accepted as a successful login because the login call does not return normally and no observable session state proves that market data queries are safe.

## Logout Observation

`catch_system_exit_then_logout` shows that `logout` is callable and can return after `SystemExit(0)`, but this is not enough to set `safe_to_query=true`.

## Permission Hypothesis

Permission issue is plausible but not proven. Config readiness only proves that local credential fields exist. It does not prove SDK login permission, historical snapshot permission, historical K-line permission, A-share permission, IP allowlist, machine binding, or correct vendor endpoint.

## Provider Fallback Decision

AmazingData online 09:35 backfill should remain blocked until login/session behavior is clarified. The recommended engineering path is to prepare a provider-neutral 09:35 adapter contract so THS MCP can be added without rewriting the temporal matrix.

## 20260703 Status

20260703 still has:

```text
reports/validation/daily/20260703/signal_detail.csv
candidate_count = 52
```

No `stock_confirmation_0935.csv` was generated in P2.3F.

## 20260706 Status

20260706 still lacks:

```text
reports/validation/daily/20260706/signal_detail.csv
```

No full-market query was attempted.

## What This Does Not Support

This review does not support trading instructions, CP threshold changes, exemption expansion, Trend active enablement, signal/ranking/evaluator changes, strategy/config/registry changes, lesson/pattern writes, market-structure execution, or deterministic rule updates.
