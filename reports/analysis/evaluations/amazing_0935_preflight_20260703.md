# P2.3D AmazingData 09:35 Preflight Probe

This report is diagnostic-only. It does not contain credentials, supplier logs, full-market dumps, trading instructions, or strategy changes.

## Summary

- date: `20260703`
- mode: `login-only`
- status: `failed`
- candidate source: `reports/validation/daily/20260703/signal_detail.csv`
- candidate rows: `52`
- probed codes: `1`
- first failing stage: `login`
- row count: `0`

## Stage Results

| stage | status | notes |
| --- | --- | --- |
| `process_start` | `ok` | `` |
| `repo_sys_path` | `ok` | `` |
| `import_project_helpers` | `ok` | `` |
| `load_login_config` | `ok` | `True` |
| `import_amazingdata` | `ok` | `` |
| `login` | `failed` | `0` |

## Safety Boundary

- Candidate-only diagnostic probe.
- No full-market query.
- No lesson, pattern, registry, evaluator, config, strategy, or trading-execution writes.
- Probe labels are posterior data-availability diagnostics, not trading advice.
