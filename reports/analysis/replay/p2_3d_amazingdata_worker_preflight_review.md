# P2.3D AmazingData Worker Preflight Review

## Scope

P2.3D adds a staged AmazingData 09:35 worker preflight probe for the temporal decision-feedback loop. The probe is diagnostic-only: it isolates worker process, project imports, login config loading, AmazingData import, login, MarketData initialization, query, normalization, and emit stages before any candidate-only 09:35 backfill retry.

This package does not change strategy logic, CP threshold, exemption, Trend active, signal/ranking/shortlist/evaluator behavior, config, registry, lesson memory, pattern memory, or trading behavior.

## Why Preflight Is Needed

P2.3C made the subprocess query path structured, but 20260703 snapshot and min1 retries still returned `structured_json_missing`. P2.3D moves one layer deeper: the worker now emits stage-level diagnostics so failures can be attributed to a concrete phase instead of being treated as a generic missing JSON marker.

## Probe Stages

The probe uses marker-delimited stage payloads:

```text
process_start
repo_sys_path
import_project_helpers
load_login_config
import_amazingdata
login
marketdata_init
query_snapshot / query_kline
normalize_rows
```

The final payload is emitted under `__AMAZING_PREFLIGHT_DONE__`. The runner captures and sanitizes stdout/stderr and writes JSON/Markdown reports without committing supplier logs.

## 20260703 Result

Candidate source:

```text
reports/validation/daily/20260703/signal_detail.csv
candidate_count = 52
probe_code_count = 1
```

Observed stages:

```text
process_start: ok
repo_sys_path: ok
import_project_helpers: ok
load_login_config: ok, ready=true
import_amazingdata: ok
login: failed
```

First failing stage:

```text
login
```

Structured failure:

```text
error_type = SystemExit
sanitized_error = 0
```

Because login failed, P2.3D did not run snapshot/min1 query stages and did not attempt the 52-candidate backfill.

## Snapshot / Min1 Probe Result

Snapshot and min1 query probes were intentionally not executed after `login-only` failed. This avoids repeated vendor calls after the first blocking stage is known.

## Generated Artifact

Generated diagnostic reports:

```text
reports/analysis/evaluations/amazing_0935_preflight_20260703.json
reports/analysis/evaluations/amazing_0935_preflight_20260703.md
```

No `stock_confirmation_0935.csv` was generated.

## 20260706 Status

20260706 still lacks the candidate source:

```text
reports/validation/daily/20260706/signal_detail.csv
```

No full-market query was attempted.

## What This Does Not Support

This review does not support trading instructions, CP threshold changes, exemption expansion, Trend active enablement, signal/ranking/evaluator changes, strategy/config/registry changes, or market-structure execution. The probe output is an operational diagnostic for the feedback data pipeline only.

## Next Action

The next step should address the AmazingData login stage before retrying historical snapshot/min1 backfill. Candidate generation for 20260706 remains a separate prerequisite.
