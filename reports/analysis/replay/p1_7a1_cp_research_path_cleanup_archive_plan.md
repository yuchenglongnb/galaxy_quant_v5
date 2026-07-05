# P1.7A1 CP Research Path Cleanup and Archive Plan

## Scope

本报告只覆盖 P1.7A 中识别出的 CP structural repair research 资产。

本轮目标是入库前卫生处理和归档计划，不是策略规则修改。本轮不支持 CP threshold change，不支持 exemption expansion，不支持 rule update，不写 lesson/pattern，不修改 strategy/evaluator/config/registry。

## Files Reviewed

### CP reports

- `reports/analysis/evaluations/cp_structural_repair_audit_20260622_20260626.json`
- `reports/analysis/evaluations/cp_structural_repair_audit_20260622_20260626.md`
- `reports/analysis/evaluations/cp_exemption_evidence_coverage_20260622_20260626.json`
- `reports/analysis/evaluations/cp_exemption_evidence_coverage_20260622_20260626.md`
- `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.json`
- `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.md`

### CP scripts

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `scripts/evaluate_cp_market_structure_backfill.py`

### CP tests

- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- `tests/test_cp_market_structure_backfill.py`

## Path Leakage Cleanup

`cp_evidence_backfill_readiness_20260622_20260626.json` contained local absolute workspace paths in snapshot availability fields.

Cleanup performed:

- Replaced local workspace-root prefixes with repo-relative paths.
- Preserved field semantics and report statistics.
- Did not change conclusions or add rule interpretation.
- Repaired JSON structure damaged by mojibake-related missing string delimiters so the file can be parsed by standard JSON tooling.

Post-cleanup checks:

- Local absolute path scan: pass.
- Secret-like scan: pass.
- JSON validity for `cp_evidence_backfill_readiness_20260622_20260626.json`: pass.

## Mojibake and Readability Check

The CP reports remain usable for numeric/statistical audit, but several labels are not archive-ready from a reader perspective.

- `cp_structural_repair_audit_20260622_20260626.*`: contains mojibake in some Chinese labels; conclusions remain interpretable but should be readability-cleaned before formal archive.
- `cp_exemption_evidence_coverage_20260622_20260626.*`: contains mojibake in some Chinese labels; conclusions remain interpretable but should be readability-cleaned before formal archive.
- `cp_evidence_backfill_readiness_20260622_20260626.json`: path-clean and JSON-valid after this step, but many display fields such as name/group/theme_cluster remain mojibake. This should be treated as `needs_readability_cleanup` before formal archive.
- `cp_evidence_backfill_readiness_20260622_20260626.md`: should be reviewed together with the JSON before archive.

## Script and Test Risk Review

### Read-only / report-output candidates

- `scripts/evaluate_cp_structural_repair_audit.py`
  - Reads local validation artifacts and writes evaluation reports.
  - Suitable for formalization as an analysis-only tool.
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
  - Reads local evidence coverage inputs and writes evaluation reports.
  - Suitable for formalization as an analysis-only tool.
- `scripts/evaluate_cp_evidence_backfill_readiness.py`
  - Reads local snapshot availability and writes readiness reports.
  - Suitable after output path sanitization and readability cleanup are standardized.

### Hold-out / safety-review candidate

- `scripts/evaluate_cp_market_structure_backfill.py`
  - Includes `--execute`.
  - Imports market-structure output writing flow.
  - Can rebuild or write market-structure snapshots when executed with write mode.
  - Must not be mixed with read-only CP audit formalization.

### Test candidates

- `tests/test_cp_structural_repair_audit.py`: formalization candidate.
- `tests/test_cp_exemption_evidence_coverage.py`: formalization candidate.
- `tests/test_cp_evidence_backfill_readiness.py`: formalization candidate after readiness output cleanup policy is stable.
- `tests/test_cp_market_structure_backfill.py`: hold-out with the market-structure backfill script.

## Archive Candidates

Can be archived after readability cleanup:

- `cp_structural_repair_audit_20260622_20260626.json`
- `cp_structural_repair_audit_20260622_20260626.md`
- `cp_exemption_evidence_coverage_20260622_20260626.json`
- `cp_exemption_evidence_coverage_20260622_20260626.md`

Can be archived after readability cleanup and a second JSON/path check:

- `cp_evidence_backfill_readiness_20260622_20260626.json`
- `cp_evidence_backfill_readiness_20260622_20260626.md`

## Formalization Candidates

Recommended for a future read-only CP audit tool branch:

- `scripts/evaluate_cp_structural_repair_audit.py`
- `tests/test_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
- `tests/test_cp_exemption_evidence_coverage.py`

Recommended after path/readability policy is explicit:

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`

## Hold-out / Safety-review Candidates

Do not include in the read-only CP audit package:

- `scripts/evaluate_cp_market_structure_backfill.py`
- `tests/test_cp_market_structure_backfill.py`

Reason:

- The script has an explicit write mode.
- It can touch market-structure snapshot outputs.
- It needs a separate safety review before any formalization.

## Relationship to P1.5D Gate

These CP assets are best treated as evidence, contradiction, and coverage-review material for the path stability gate.

They can support future gate extensions by documenting:

- CP repair-phase sensitivity.
- Missing or stale market-structure evidence.
- Cases where CP observations should remain `rule_change_allowed=false`.
- Contradictions that block broad CP threshold or exemption proposals.

They should not be interpreted as direct rule-proposal material.

## Recommended Next Branches

- `p1-7a1-cp-report-archive`: clean readability and archive CP reports.
- `p1-7a2-cp-analysis-tool-formalization`: formalize read-only CP audit tools.
- `p1-7a3-cp-gate-fixtures`: convert suitable examples into gate contradiction or coverage fixtures.
- `p1-7a-market-structure-backfill-safety-review`: isolate `--execute` backfill tooling for separate safety review.

## Blockers

Immediate blocker:

- None for continuing triage.

Commit-before-archive blockers:

- Mojibake/readability cleanup remains required for CP reports.
- `cp_evidence_backfill_readiness_20260622_20260626.json` should receive a second review because this step repaired path leakage and JSON structure, but did not translate corrupted labels.
- `evaluate_cp_market_structure_backfill.py` must remain hold-out until write-mode safety is reviewed.

## Next Step

Recommended next step:

`P1.7A2: Formalize Read-only CP Audit Tools`

Precondition:

- Keep market-structure backfill tooling out of scope.
- Treat structural repair and exemption evidence tools as read-only analysis candidates.
- Keep readiness tooling gated on path/readability output policy.
