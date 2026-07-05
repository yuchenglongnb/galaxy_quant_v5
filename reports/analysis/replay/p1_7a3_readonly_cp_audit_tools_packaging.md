# P1.7A3 Read-only CP Audit Tools Packaging

## Scope

This is a packaging dry-run for the read-only CP audit tools formalized in P1.7A2.

The package is analysis-only. It does not support CP threshold changes, CP exemption expansion, Trend active enablement, reversal trigger changes, rule updates, lesson writes, pattern writes, registry writes, sync, snapshot rebuild, P1.2J, or market-structure backfill.

## Package File List

Core package:

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`
- `reports/analysis/replay/p1_7a2_readonly_cp_audit_tools_formalization.md`
- `reports/analysis/replay/p1_7a3_readonly_cp_audit_tools_packaging.md`

## Excluded Assets

Continue excluding:

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- readiness reports
- `scripts/evaluate_cp_market_structure_backfill.py`
- `tests/test_cp_market_structure_backfill.py`
- market-structure backfill reports
- ETF / benchmark research assets
- prior-day context research assets
- trend / confirmation coverage research assets
- intraday confirmation runtime reports

## Branch Recommendation

Recommended branch:

`p1-7a-cp-readonly-audit-tools`

Rationale:

- PR #2 has already merged P1.4R-P1.6 into `main`.
- This CP read-only audit package is logically separate from the merged P1.4R-P1.6 validation stack.
- A new branch from `origin/main` keeps the package review small and avoids extending the old merged branch.

Remote base check:

- `origin/main` contains PR #2 merge commit `cd4d50c`.
- The core package paths do not exist on `origin/main`, so a new branch from `origin/main` should not collide with tracked files.

## Safety Scan

Core package scan result:

- Local absolute path: pass.
- Secret-like content: pass.
- Unsafe affirmative rule wording: pass.
- Lesson / pattern / registry writes: pass.
- Sync / rebuild / live API calls: pass.
- Strategy / evaluator / config mutation: pass.

Safe boundary wording remains intentionally present:

- analysis-only
- no lesson/pattern/registry writes
- no strategy mutation

## Test Results

Commands run:

```bash
python -m pytest tests/test_cp_structural_repair_audit.py tests/test_cp_exemption_evidence_coverage.py -q
python -m py_compile scripts/evaluate_cp_structural_repair_audit.py scripts/evaluate_cp_exemption_evidence_coverage.py
python -m pytest tests/test_intraday_excursion_features.py tests/test_intraday_path_replay.py tests/test_path_stability_gate.py -q
```

Results:

- Default Python CP tests: `17 passed`.
- Default Python py_compile: passed.
- Project `amazing` environment CP tests: `17 passed`.
- Project `amazing` environment py_compile: passed.
- Project `amazing` environment P1.5 path/gate regression: `31 passed`.

## Optional Document Inclusion Decision

Do not include these process-triage reports in the core commit:

- `reports/analysis/replay/p1_7_early_research_assets_triage.md`
- `reports/analysis/replay/p1_7a_cp_research_assets_triage.md`
- `reports/analysis/replay/p1_7a1_cp_research_path_cleanup_archive_plan.md`

Reason:

- They are process-oriented triage artifacts.
- Some contain explicit sensitive-word scan lists.
- Some document old environment-leakage findings from assets that remain outside this package.
- The P1.7A2 and P1.7A3 reports are sufficient for reviewing this read-only CP audit package.

If needed later, those reports should be reviewed as a separate documentation/archive commit.

## Commit Plan

Recommended commit title:

`P1.7A: formalize read-only CP audit tools`

Recommended files:

- `scripts/evaluate_cp_structural_repair_audit.py`
- `scripts/evaluate_cp_exemption_evidence_coverage.py`
- `tests/test_cp_structural_repair_audit.py`
- `tests/test_cp_exemption_evidence_coverage.py`
- `reports/analysis/replay/p1_7a2_readonly_cp_audit_tools_formalization.md`
- `reports/analysis/replay/p1_7a3_readonly_cp_audit_tools_packaging.md`

Suggested commit body:

```text
Add analysis-only CP structural repair and exemption evidence audit tools with fixture-based tests. The tools are read-only, support dry-run/output-dir flows, and do not write lesson, pattern, registry, evaluator, config, or strategy files.
```

## Blockers

No blocker for packaging the core read-only CP audit package.

Pre-commit reminders:

- Do not include readiness assets.
- Do not include market-structure backfill assets.
- Do not include ETF / prior-day / trend / runtime research assets.
- Do not use broad `git add`.

## Next Step

Wait for explicit authorization:

`CREATE_BRANCH_AND_COMMIT_CP_READONLY`
