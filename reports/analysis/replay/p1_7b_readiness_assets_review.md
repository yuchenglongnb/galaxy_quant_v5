# P1.7B Readiness Assets Review

## Scope

This review covers only CP evidence backfill readiness assets:

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.json`
- `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.md`

This is an analysis-only triage. Readiness assets do not support CP threshold change, CP exemption expansion, or rule update. They can only support evidence completeness and gate precondition review.

Market-structure backfill, ETF/benchmark, prior-day, trend/confirmation, and runtime assets remain out of scope.

## Readiness Asset Inventory

| Path | Type | Size | Current role | Recommended action |
| --- | --- | ---: | --- | --- |
| `scripts/evaluate_cp_evidence_backfill_readiness.py` | script | 16,277 B | Readiness classifier and report generator | cleanup first, then formalize as gate precondition candidate |
| `tests/test_cp_evidence_backfill_readiness.py` | test | 5,685 B | Fixture-style readiness classification tests | cleanup first, then formalize |
| `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.json` | report-json | 97,598 B | Generated readiness report | archive only after readability cleanup |
| `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.md` | report-md | 5,874 B | Generated readiness summary | archive only after readability cleanup |

## Script Review

`scripts/evaluate_cp_evidence_backfill_readiness.py` is mostly read-only from an input perspective:

- reads existing daily validation outputs
- reads local iFind snapshot availability
- reads leading-cluster config
- classifies evidence missing reasons
- writes JSON/Markdown reports under `reports/analysis/evaluations`

Important observations:

- It does not write lesson, pattern, or registry files.
- It does not modify strategy, evaluator, config, or `market_pattern_registry.json`.
- It does not call sync, live API, P1.2J, or market-structure backfill.
- It does write reports by default and currently lacks `--dry-run` / `--output-dir`.
- It imports the already formalized CP structural repair and exemption evidence tools.
- It contains readiness actions such as `rebuild_market_structure_snapshot`, which should be treated as evidence-completeness labels, not as permission to execute rebuilds.

Recommendation:

- Do not submit as-is.
- First add analysis-only wording, `--dry-run`, and `--output-dir`.
- Reword action labels or report text so they cannot be read as an execution instruction.
- Keep it as a gate precondition tool, not a rule proposal tool.

## Test Review

`tests/test_cp_evidence_backfill_readiness.py` is already close to fixture-based:

- uses `tmp_path`
- uses monkeypatching for local root replacement
- does not require real runtime reports for its current unit coverage
- tests missing snapshot, alias unmatched, sector breadth field missing, builder attachment missing, prior-day missing, and summary conclusion tags

Remaining cleanup needs:

- fixture labels still contain mojibake strings
- tests should explicitly cover no lesson/pattern/registry write paths
- tests should cover dry-run/no-output behavior after the script adds `--dry-run`
- tests should align with the P1.7A read-only testing style

Recommendation:

- Formalize only after script output behavior is constrained.
- Keep tests out of the current package until readability and dry-run behavior are added.

## Report Review

### JSON

`cp_evidence_backfill_readiness_20260622_20260626.json`:

- JSON validity: pass
- local absolute path scan: pass
- secret-like scan: pass
- unsafe rule wording scan: pass
- readability: not archive-ready because many group/name labels remain mojibake

### Markdown

`cp_evidence_backfill_readiness_20260622_20260626.md`:

- has a clear high-level summary
- contains conservative conclusions:
  - `keep_cp_threshold`
  - `repair_evidence_first`
  - `no_rule_change_yet`
  - `not_ready_for_exemption_expansion`
  - `ready_for_evidence_backfill`
- still contains mojibake group labels
- should not be archived until readability cleanup is complete

## Safety Scan

Readiness group scan result:

- Local absolute paths: pass.
- Secret-like content: pass.
- Unsafe affirmative rule wording: pass.
- Trading advice: pass.

Safe conservative tags are present:

- `keep_cp_threshold`
- `repair_evidence_first`
- `no_rule_change_yet`
- `not_ready_for_exemption_expansion`

These are acceptable as no-rule-change framing.

## Environment Leakage and Mojibake Review

Environment leakage:

- The prior absolute path issue in the readiness JSON has been cleaned.
- No new local path or secret-like content was found in the readiness group.

Mojibake:

- JSON and Markdown reports still contain widespread mojibake in `group`, `name`, `analysis_group`, and `theme_cluster` display fields.
- Tests also use mojibake labels in fixtures.
- Mojibake should be cleaned or replaced with stable ASCII fixture labels before formalization.

## Relationship to P1.5D Gate and P1.7A Tools

Readiness assets are best treated as:

1. Evidence completeness precondition.
2. Gate coverage/integrity input.
3. Research archive after cleanup.

They should not be treated as:

- CP threshold proposal evidence.
- CP exemption expansion evidence by themselves.
- Rule update material.
- Permission to run market-structure rebuild.

Potential P1.5D gate extension:

- Add a precondition gate for snapshot availability.
- Track alias/group unmatched ratios.
- Track sector breadth field availability.
- Track leading-cluster attachment completeness.
- Block rule proposal eligibility when readiness evidence is incomplete.

## Recommended Actions

### Cleanup first

- Add analysis-only docstring and CLI boundary wording.
- Add `--dry-run`.
- Add `--output-dir`.
- Make output paths explicit.
- Keep default reports under analysis output only.
- Reword `recommended_backfill_actions` as readiness labels or clearly document that they are not execution commands.
- Fix or replace mojibake labels in fixtures and generated reports before archive.

### Formalize later

Formalize only after cleanup as:

`P1.7B1: Readiness Path / Readability Cleanup`

Then:

`P1.7B2: Formalize Readiness Gate Precondition Tool`

### Archive later

Archive reports only after:

- JSON validity remains pass.
- Markdown is readable.
- no local paths remain.
- no unsafe rule language appears.

## Formalization Readiness

Current formalization readiness:

- Script: not ready, cleanup needed.
- Test: promising, but needs readability and dry-run coverage.
- Reports: not ready for archive because of mojibake.

Recommended disposition:

- `cleanup_first`
- `formalize_as_gate_precondition_candidate`
- `archive_after_readability_cleanup`

## Blockers

Immediate blocker:

- None for continuing review.

Commit-before-formalization blockers:

- Missing `--dry-run` and `--output-dir`.
- Default report writing behavior needs a clearer boundary.
- Mojibake in reports and tests.
- `recommended_backfill_actions` labels may be misread as execution instructions unless documented or renamed.

## Next Step

Recommended next step:

`P1.7B1: Readiness Path / Readability Cleanup`

Scope for that step should stay narrow:

- Clean readiness path/output boundaries.
- Add dry-run and output-dir.
- Improve readability or fixture labels.
- Do not run market-structure backfill.
- Do not change CP threshold, exemption, or rule logic.
