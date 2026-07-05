# P1.7A2 Read-only CP Audit Tools Formalization

## Scope

本轮只 formalize 两个 read-only CP audit 工具：

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`

以及对应测试：

- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`

本轮不处理 readiness 资产，不处理 market-structure backfill，不处理 ETF / prior-day / trend / runtime artifacts。

## Files Reviewed

### Formalized scripts

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`

### Formalized tests

- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`

### Explicit hold-out files

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- `scripts/evaluate_cp_market_structure_backfill.py`
- `tests/test_cp_market_structure_backfill.py`

## Changes Made

### Structural repair audit

- Expanded the module docstring to state analysis-only behavior and safety boundaries.
- Moved heavy auction/data dependencies into lazy imports inside `cp_candidate_rows`.
- Added explicit `--output-dir` support.
- Added explicit `--dry-run` support.
- Kept default output under `reports/analysis/evaluations`.
- Preserved existing statistics and bucket semantics.

### Exemption evidence coverage audit

- Expanded the module docstring to state analysis-only behavior and safety boundaries.
- Added explicit `--output-dir` support.
- Added explicit `--dry-run` support.
- Kept default output under `reports/analysis/evaluations`.
- Preserved existing evidence bucket semantics.

### Tests

- Added tests that verify report writing is limited to an explicit `tmp_path`.
- Added tests that verify `--dry-run` returns payloads without writing report files.
- Kept tests fixture-based and independent of live data, sync, snapshot rebuild, or local absolute paths.

## Read-only Safety Review

The two formalized tools are analysis/reporting helpers.

They do not:

- change CP thresholds
- expand CP exemptions
- enable Trend active
- change reversal triggers
- mutate signal/ranking/shortlist/evaluator logic
- write lesson records
- write pattern records
- write registry files
- call sync
- call snapshot rebuild
- call live API

The scripts still write analysis reports when not in dry-run mode, but outputs are confined to either:

- explicit `--output-dir`
- default `reports/analysis/evaluations`

## CLI / Input-output Contract

Both scripts support:

- `--dates`
- `--start-date`
- `--end-date`
- `--output-dir`
- `--dry-run`

Expected usage:

```bash
python -m scripts.evaluate_cp_structural_repair_audit --dates 20260622,20260623 --dry-run
python -m scripts.evaluate_cp_exemption_evidence_coverage --start-date 20260622 --end-date 20260626 --output-dir reports/analysis/evaluations
```

`--dry-run` builds and prints a compact payload summary without writing reports.

## Tests

Commands run:

```bash
python -m pytest tests/test_cp_structural_repair_audit.py tests/test_cp_exemption_evidence_coverage.py -q
python -m pytest tests/test_intraday_excursion_features.py tests/test_intraday_path_replay.py tests/test_path_stability_gate.py -q
python -m py_compile scripts/evaluate_cp_structural_repair_audit.py scripts/evaluate_cp_exemption_evidence_coverage.py
```

Results:

- CP audit tests: `17 passed`
- P1.5 validation stack tests: `31 passed`
- py_compile: passed

Environment note:

- The default `python` environment has a pandas/numpy ABI mismatch, so P1.5 pandas-dependent tests fail during import there.
- The project conda environment `amazing` passes the targeted suite. Use the repo's configured project Python environment for these tests.

## Safety Scan Result

Unsafe affirmative wording scan: pass.

Local path / secret-like scan: pass.

Safe negated boundary wording remains present in module docstrings:

- no lesson/pattern/registry writes
- no strategy mutation

## Remaining Hold-out Assets

Readiness remains conditional:

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- readiness reports

Reason:

- readiness reports still need readability cleanup and output path policy review.

Market-structure backfill remains hold-out:

- `scripts/evaluate_cp_market_structure_backfill.py`
- `tests/test_cp_market_structure_backfill.py`

Reason:

- contains `--execute`
- can write market-structure snapshot outputs
- requires separate safety review

## Relationship to P1.5D Gate

The formalized read-only CP audit tools can support P1.5D gate extension by providing:

- CP phase-sensitivity evidence
- false-positive attribution buckets
- exemption evidence coverage checks
- contradiction examples for `rule_change_allowed=false`

They do not propose or implement rule changes.

## Commit Readiness

This read-only CP audit subset is ready for packaging review.

Recommended package contents:

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`
- `reports/analysis/replay/p1_7a2_readonly_cp_audit_tools_formalization.md`

Do not include readiness or market-structure backfill assets in the same package.

## Next Step

Recommended next step:

`P1.7A3: Package Read-only CP Audit Tools`
