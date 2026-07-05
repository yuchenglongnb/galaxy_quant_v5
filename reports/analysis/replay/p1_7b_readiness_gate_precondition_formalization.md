# P1.7B Readiness Gate Precondition Formalization

## Scope

This package formalizes CP evidence backfill readiness as an analysis-only gate precondition tool.

Readiness answers a narrow evidence-quality question: whether current CP evidence is complete, traceable, and reproducible enough to enter broader-window, contradiction, and gate review. It does not decide CP threshold changes, exemption expansion, signal activation, or CP rule updates.

## Why Readiness Is a Gate Precondition

Readiness labels describe evidence gaps. They are not execution instructions and do not authorize any rebuild, sync, or market-structure backfill.

The tool is intended to sit before future CP evidence review:

1. Check local evidence completeness.
2. Label missing snapshot, alias, breadth, or builder attachment issues.
3. Preserve denominator and coverage context.
4. Keep any later rule proposal blocked until broader evidence and contradiction review are complete.

## Files Changed

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`

## CLI Contract

The script supports:

- `--dates`
- `--start-date`
- `--end-date`
- `--output-dir`
- `--dry-run`

`--dry-run` builds the payload and prints a compact summary without writing report files.

When not using `--dry-run`, output is written only to the explicit `--output-dir` or the existing default evaluation report directory. The script does not write lesson, pattern, registry, evaluator, config, strategy, or benchmark-map files.

## Output Contract

The output uses `readiness_labels` and includes:

```text
Readiness labels are gate precondition labels, not execution instructions.
```

The previous action-style wording has been replaced with label-oriented wording so the output cannot be read as permission to run remediation work.

## Mojibake and Readability Handling

The unit tests now use neutral fixture labels such as:

- `sample_theme_a`
- `unknown_theme`

The older generated readiness JSON/Markdown reports remain excluded from this package because they still contain readability issues. They can be cleaned or archived in a later review, but they are not required for this gate precondition tool.

## Tests

The formalized tests cover:

- snapshot missing classification
- alias or group unmatched classification
- sector breadth field missing classification
- builder attachment missing classification
- prior-day context missing classification
- summary conclusion tags
- explicit output directory writes
- `--dry-run` no-write behavior
- repo-relative snapshot paths
- label semantics that are not execution actions
- no lesson, pattern, registry, evaluator, config, or strategy output paths

## Safety Scan

Expected safety properties:

- Analysis-only.
- Read-only inputs.
- No CP threshold changes.
- No CP exemption expansion.
- No Trend active enablement.
- No signal, ranking, shortlist, evaluator, strategy, config, or registry mutation.
- No lesson, pattern, or registry writes.
- No sync, snapshot rebuild, P1.2J, CP audit rerun, or market-structure backfill execution.
- No trading advice.

## Excluded Assets

This package excludes:

- old readiness JSON/Markdown reports
- market-structure backfill scripts, tests, and reports
- ETF / benchmark research assets
- prior-day context research assets
- trend / confirmation coverage assets
- intraday confirmation runtime reports
- all other untracked research assets

## Commit and PR Readiness

The intended core commit includes only:

- `scripts/evaluate_cp_evidence_backfill_readiness.py`
- `tests/test_cp_evidence_backfill_readiness.py`
- `reports/analysis/replay/p1_7b_readiness_gate_precondition_formalization.md`

The P1.7B triage report can remain untracked because this formalization report summarizes the relevant pre-commit decision.

## Next Step

If targeted tests and safety scans pass, package this as:

```text
P1.7B: formalize readiness gate precondition tool
```

The next review should be:

```text
P1.7B-PR: Readiness Gate Precondition PR Review
```
