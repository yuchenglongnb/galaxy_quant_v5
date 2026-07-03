# P1.4R-P1.5D Diff Packaging Review

This packaging review is analysis-only. It prepares commit grouping and review scope; it does not stage, commit, restore, clean, or change strategy logic.

## Scope

- Branch: `p1-raw-trend-t1-validation-stack`
- P1.4R files are existing observation-only wording diffs.
- P1.5A-D files are validation/reporting tools, tests, and generated analysis reports.
- No CP threshold, CP exemption, Trend active, reversal trigger, signal ranking, shortlist, evaluator, config, benchmark map, lesson writer, pattern registry, sync, snapshot rebuild, P1.2J, or CP audit change is included in the P1.5A-D package.

## File Inventory

### Group A: P1.4R Observation-only Wording Diff

Recommended commit title: `P1.4R: downgrade auction lessons to observation-only wording`

- `reports/analysis/lessons/auction_lessons.jsonl`
- `reports/analysis/patterns/pattern_progress.json`

Notes:

- Commit separately from P1.5 tooling.
- Commit body should state observation-only and no rule/weight/threshold/active change.

### Group B: P1.5A OHLC Excursion Validation Fields

Recommended commit title: `P1.5A: add intraday OHLC excursion validation fields`

- `reports/intraday_excursion.py`
- `tests/test_intraday_excursion_features.py`
- `runners/auction.py`
- `reports/t1_backtest.py`

Notes:

- Validation/reporting fields only.
- No candidate selection, ranking, evaluator, or strategy rule logic change.

### Group C: P1.5B-C Intraday Path Replay And Broader-window Distribution

Recommended commit title: `P1.5B-C: add intraday path replay and broader-window distribution reports`

- `reports/intraday_path_replay.py`
- `tests/test_intraday_path_replay.py`
- `reports/analysis/replay/20260701_20260702_intraday_path_replay.md`
- `reports/analysis/replay/20260701_20260702_intraday_path_summary.json`
- `reports/analysis/replay/20260626_20260702_intraday_path_distribution.md`
- `reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json`

Notes:

- Analysis-only replay tooling and generated reports.
- JSON outputs are moderate in size and reproducible from local cached inputs.

### Group D: P1.5D Rule-proposal Gate Governance

Recommended commit title: `P1.5D: add path stability gate for rule-proposal governance`

- `reports/path_stability_gate.py`
- `tests/test_path_stability_gate.py`
- `reports/analysis/replay/20260626_20260702_path_stability_gate_review.md`
- `reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json`

Notes:

- Current gate verdict is `rule_change_allowed=false`.
- This is governance/reporting only, not strategy implementation.

### Separate Review / Unknown Assets

The working tree also contains earlier untracked CP, ETF, prior-day, and trend coverage research assets under `scripts/`, `tests/`, and `reports/analysis/evaluations/`.

Recommended action:

- Do not mix these assets into the P1.4R/P1.5A-D commits.
- Review them in a separate phase package.

## Generated Artifact Audit

| file | size bytes | commit recommendation |
|---|---:|---|
| `reports/analysis/replay/20260701_20260702_intraday_path_replay.md` | 6541 | commit with Group C |
| `reports/analysis/replay/20260701_20260702_intraday_path_summary.json` | 97151 | commit with Group C |
| `reports/analysis/replay/20260626_20260702_intraday_path_distribution.md` | 14451 | commit with Group C |
| `reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json` | 271514 | commit with Group C |
| `reports/analysis/replay/20260626_20260702_path_stability_gate_review.md` | 4647 | commit with Group D |
| `reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json` | 9712 | commit with Group D |

All generated JSON files parse successfully.

Gate JSON includes:

- `analysis_only=true`
- `rule_change_allowed=false`

## Safety Scan Result

- Unsafe affirmative rule/trading wording: not found in P1.5B-D generated reports and modules.
- Safe negated wording is present in analysis-only disclaimers, such as `does not justify deterministic rule changes`.
- No local absolute path leakage was found in P1.5B-D reports, modules, or tests.
- No secret-like content was found in P1.5B-D reports, modules, or tests.

## Reproduction Commands

P1.5B two-day replay:

```bash
python -m reports.intraday_path_replay --dates 20260701 20260702 --output reports/analysis/replay/20260701_20260702_intraday_path_replay.md --json-output reports/analysis/replay/20260701_20260702_intraday_path_summary.json
```

P1.5C broader-window distribution:

```bash
python -m reports.intraday_path_replay --start-date 20260626 --end-date 20260702 --output-md reports/analysis/replay/20260626_20260702_intraday_path_distribution.md --output-json reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json
```

P1.5D gate review:

```bash
python -m reports.path_stability_gate --input-json reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json --output-md reports/analysis/replay/20260626_20260702_path_stability_gate_review.md --output-json reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json
```

## Test Results

```bash
python -m pytest tests/test_intraday_excursion_features.py tests/test_intraday_path_replay.py tests/test_path_stability_gate.py -q
```

Result: `31 passed`

```bash
python -m pytest tests/test_t1backtest_input_integrity.py tests/test_multiday_t1_validation.py -q
```

Result: `13 passed`

```bash
python -m py_compile reports/intraday_excursion.py reports/intraday_path_replay.py reports/path_stability_gate.py reports/t1_backtest.py runners/auction.py
```

Result: passed

## Recommended Commit Plan

1. `P1.4R: downgrade auction lessons to observation-only wording`
2. `P1.5A: add intraday OHLC excursion validation fields`
3. `P1.5B-C: add intraday path replay and broader-window distribution reports`
4. `P1.5D: add path stability gate for rule-proposal governance`

Default recommendation: use four commits for reviewability.

Alternative: keep P1.4R separate and combine P1.5A-D into one validation-tooling commit only if reviewer prefers fewer commits.

## Remaining Human-review Items

- Decide whether to commit P1.4R wording-only memory diff.
- Keep earlier untracked CP/ETF/prior-day/trend coverage research assets out of the P1.5 commit stack unless separately reviewed.
- Confirm generated JSON artifact sizes are acceptable for repository storage.

## P1.6 Documentation Addendum

P1.6 added long-horizon stabilization documentation for the auction validation stack:

- `reports/analysis/replay/auction_validation_stack_readme.md`
- `reports/analysis/replay/p1_6_long_horizon_stabilization_plan.md`
- `reports/analysis/replay/p1_6_pr_preparation_note.md`

No new strategy code was changed by the P1.6 documentation step.

The previous four-commit plan remains valid:

1. `P1.4R: downgrade auction lessons to observation-only wording`
2. `P1.5A: add intraday OHLC excursion validation fields`
3. `P1.5B-C: add intraday path replay and broader-window distribution reports`
4. `P1.5D: add path stability gate for rule-proposal governance`

P1.6 documentation can be handled in either of two ways:

- Add the P1.6 README, roadmap, PR note, and updated packaging note to a fifth documentation commit:
  `P1.6: document auction validation stack and PR plan`
- Or include the P1.6 documents in the P1.5D governance commit if the reviewer prefers fewer commits.

Default recommendation: keep P1.6 as a fifth documentation commit for cleaner review boundaries.
