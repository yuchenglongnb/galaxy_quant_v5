# P2.3E AmazingData Login Path Probe Manifest

## Included Files

```text
scripts/amazing_login_path_probe.py
scripts/run_amazing_login_path_probe.py
tests/test_amazing_login_path_probe.py
scripts/amazing_0935_preflight_probe.py
scripts/run_0935_preflight_probe.py
scripts/amazing_0935_query_worker.py
scripts/collect_0935_feedback.py
tests/test_amazing_0935_preflight_probe.py
tests/test_amazing_0935_query_worker.py
tests/test_collect_0935_feedback.py
reports/analysis/evaluations/amazing_login_path_probe.json
reports/analysis/evaluations/amazing_login_path_probe.md
reports/analysis/replay/p2_3e_amazingdata_login_path_inventory.md
reports/analysis/replay/p2_3e_amazingdata_login_path_probe_review.md
reports/analysis/replay/p2_3e_amazingdata_login_path_probe_manifest.md
reports/analysis/replay/p2_3e_0935_backfill_gap_20260703.md
reports/analysis/replay/p2_3e_0935_backfill_gap_20260706.md
```

## Login Styles Tested

```text
style_a_build_login_invocation_keyword_int_port
style_b_build_login_invocation_positional_int_port
style_c_direct_keyword_args
style_d_positional_args
style_e_existing_project_helper_exact
```

## Result

```text
successful_styles = []
system_exit_styles = all tested styles
diagnosis = all_available_styles_system_exit_0_or_failed
```

## Backfill Decision

No 09:35 backfill was attempted because login-only did not produce a successful login style.

## Sensitive Content Boundary

This package does not commit passwords, tokens, secrets, username values, host values, port values, supplier logs, or full-market raw snapshots. Reports include config readiness booleans only.

## How ChatGPT Should Use This

Use this result to avoid further blind query retries. The next blocker is the AmazingData SDK login control flow, not candidate matching, 09:35 artifact format, temporal matrix parsing, or snapshot/min1 row normalization.
