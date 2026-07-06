# P2.3E AmazingData Login Path Probe Review

## Scope

P2.3E diagnoses AmazingData login invocation behavior before any 09:35 historical query or backfill retry. It is a login-path diagnostic package only.

This work does not change CP threshold, exemption, Trend active, signal/ranking/shortlist/evaluator logic, strategy/config/registry files, `market_pattern_registry.json`, lesson memory, pattern memory, or trading behavior.

## Why Login Path Probe Is Needed

P2.3D showed that the 20260703 09:35 worker reaches:

```text
process_start
repo_sys_path
import_project_helpers
load_login_config
import_amazingdata
```

and then fails at:

```text
login
```

The error is `SystemExit(0)`. P2.3E therefore compares login invocation styles instead of continuing blind snapshot/min1 query retries.

## Existing Login Inventory

See:

```text
reports/analysis/replay/p2_3e_amazingdata_login_path_inventory.md
```

The repository already has shared helper, isolated login check, differential query probe, and direct debug-style login paths. P2.3E only records call shapes and does not expose credential values.

## Login Styles Tested

```text
style_a_build_login_invocation_keyword_int_port
style_b_build_login_invocation_positional_int_port
style_c_direct_keyword_args
style_d_positional_args
style_e_existing_project_helper_exact
```

## SystemExit(0) Classification

`SystemExit(0)` is classified as:

```text
status = system_exit
ambiguous_success = true
login_returned = false
```

It is not treated as a successful login because control flow does not return past `ad.login(...)`.

## Probe Result

All tested styles returned `SystemExit(0)`:

```text
successful_styles = []
system_exit_styles = all 5 tested styles
diagnosis = all_available_styles_system_exit_0_or_failed
```

No style produced `status=ok`.

## Whether Preflight Continued

Because no login style succeeded, P2.3E did not run:

```text
snapshot-preflight
min1-preflight
52-candidate dry-run
artifact write
temporal matrix backfill
```

## 20260703 Status

20260703 still has a valid candidate source:

```text
reports/validation/daily/20260703/signal_detail.csv
candidate_count = 52
```

But no `stock_confirmation_0935.csv` is generated in P2.3E.

## 20260706 Status

20260706 still lacks:

```text
reports/validation/daily/20260706/signal_detail.csv
```

No full-market query was attempted.

## What This Does Not Support

This review does not support trading instructions, deterministic rule changes, CP threshold changes, exemption expansion, Trend active enablement, ranking/signal/evaluator changes, registry writes, runtime memory writes, or market-structure execution.

## Next Action

The next step should investigate the SDK login control flow itself: why `ad.login(...)` raises `SystemExit(0)` across helper-built, direct keyword, direct positional, and existing helper paths.
