# P1.8 Real Evidence Inventory

## Scope

This inventory records the remaining untracked research assets after PR #4. It treats reports as first-class loop artifacts while keeping true credentials, execute-style backfill, and large raw/runtime dumps out of this commit.

## Inventory Summary

| Group | Count | Submit now | Notes |
| --- | ---: | ---: | --- |
| A. CP structural / exemption / readiness residual | 6 | 6 | High loop value; real CP evidence reports. One readiness JSON has readability issue but is useful as raw evidence. |
| B. market-structure backfill | 2 | 0 | Hold for P1.9 because it has write/execute semantics. |
| C. ETF / benchmark | 22 | 0 | Valuable but belongs to a separate ETF/benchmark loop. |
| D. prior-day context | 22 | 0 | Valuable but too broad for this P1.8 seed pack. |
| E. trend / confirmation coverage | 4 | 0 | Hold for trend confirmation expansion. |
| F. intraday confirmation runtime reports | 0 | 0 | Covered under ETF/runtime-style outputs in current file naming. |
| G. auction replay / triage reports | 4 | 2 | Submit P1.7A1 and P1.7B reports; hold broader process reports for later cleanup/indexing. |
| I. unknown | 0 | 0 | No unknown files found. |

## Submit Now Evidence Pack

| Path | Group | Type | Size | Date range | Real cases | Real codes | Readability | Loop value | Reason |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `reports/analysis/evaluations/cp_structural_repair_audit_20260622_20260626.json` | CP | json | 121790 | 20260622-20260626 | yes | yes | good | high | Machine-readable CP structural repair audit evidence. |
| `reports/analysis/evaluations/cp_structural_repair_audit_20260622_20260626.md` | CP | md | 13553 | 20260622-20260626 | yes | yes | good | high | Human-readable CP structural repair summary. |
| `reports/analysis/evaluations/cp_exemption_evidence_coverage_20260622_20260626.json` | CP | json | 125645 | 20260622-20260626 | yes | yes | good | high | Machine-readable exemption evidence coverage context. |
| `reports/analysis/evaluations/cp_exemption_evidence_coverage_20260622_20260626.md` | CP | md | 10941 | 20260622-20260626 | yes | yes | good | high | Human-readable exemption evidence review. |
| `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.json` | CP readiness | json | 97598 | 20260622-20260626 | yes | yes | mojibake | medium | Useful raw readiness evidence; readability issue is preserved and disclosed. |
| `reports/analysis/evaluations/cp_evidence_backfill_readiness_20260622_20260626.md` | CP readiness | md | 5874 | 20260622-20260626 | yes | yes | good | high | Compact readiness summary for loop review. |
| `reports/analysis/replay/p1_7a1_cp_research_path_cleanup_archive_plan.md` | triage | md | 7214 | 20260622-20260626 | yes | no | good | high | CP path cleanup and archive plan. |
| `reports/analysis/replay/p1_7b_readiness_assets_review.md` | triage | md | 7548 | 20260622-20260626 | yes | no | good | high | Readiness review that motivated the gate-precondition tool. |
| `reports/analysis/replay/p1_8_loop_foundation_design.md` | loop foundation | md | new | n/a | no | no | good | high | Defines the evidence loop model. |
| `reports/analysis/replay/p1_8_real_evidence_inventory.md` | loop foundation | md | new | mixed | yes | yes | good | high | Index for submitted and held evidence. |

## Held Assets

### A. CP residual held from this commit

| Path | Reason |
| --- | --- |
| `reports/analysis/replay/p1_7a_cp_research_assets_triage.md` | Useful but includes environment-specific path examples; P1.7A1 summarizes the actionable cleanup plan. |
| `reports/analysis/replay/p1_7_early_research_assets_triage.md` | Useful baseline inventory, but it includes broad safety keyword lists; hold for a later cleaned evidence-index pack. |

### B. Market-structure backfill

| Path | Reason |
| --- | --- |
| `scripts/evaluate_cp_market_structure_backfill.py` | Write/execute style asset; needs P1.9 safety refactor. |
| `tests/test_cp_market_structure_backfill.py` | Coupled to market-structure backfill behavior; hold with script. |

### C. ETF / benchmark

| Path | Reason |
| --- | --- |
| `reports/analysis/evaluations/etf_benchmark_manual_review_20260622_20260626.json` | Separate ETF/benchmark loop. |
| `reports/analysis/evaluations/etf_benchmark_manual_review_20260622_20260626.md` | Separate ETF/benchmark loop. |
| `reports/analysis/evaluations/etf_relative_strength_attribution_20260622_20260626.json` | Separate ETF/benchmark loop. |
| `reports/analysis/evaluations/etf_relative_strength_attribution_20260622_20260626.md` | Separate ETF/benchmark loop. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260622_etf_execute.json` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260622_etf_execute.md` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260623_etf_execute.json` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260623_etf_execute.md` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260624_etf_execute.json` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260624_etf_execute.md` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260625_etf_execute.json` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260625_etf_execute.md` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260626_etf_execute.json` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/intraday_confirmation_backfill_20260626_etf_execute.md` | Runtime/execute-style ETF output. |
| `reports/analysis/evaluations/recent_etf_confirmation_repair_20260622_20260626.json` | Separate ETF confirmation loop. |
| `reports/analysis/evaluations/recent_etf_confirmation_repair_20260622_20260626.md` | Separate ETF confirmation loop. |
| `reports/analysis/evaluations/semiconductor_etf_benchmark_granularity_20260622_20260626.json` | Separate benchmark granularity loop. |
| `reports/analysis/evaluations/semiconductor_etf_benchmark_granularity_20260622_20260626.md` | Separate benchmark granularity loop. |
| `scripts/evaluate_etf_benchmark_manual_review.py` | Tool formalization needed later. |
| `scripts/evaluate_etf_relative_strength_attribution.py` | Tool formalization needed later. |
| `scripts/evaluate_semiconductor_etf_benchmark_granularity.py` | Tool formalization needed later. |
| `tests/test_etf_benchmark_manual_review.py` | Hold with related tool. |
| `tests/test_etf_relative_strength_attribution.py` | Hold with related tool. |
| `tests/test_semiconductor_etf_benchmark_granularity.py` | Hold with related tool. |

### D. Prior-day context

| Path | Reason |
| --- | --- |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260608.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260608.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260609.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260609.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260616.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260616.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260618.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260618.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260622.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260622.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260623.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260623.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260624.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260624.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260625.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260625.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260626.json` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_20260626.md` | Hold for P1.10. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_summary.json` | Hold for P1.10 summary pack. |
| `reports/analysis/evaluations/prior_day_context_stock_effect_summary.md` | Hold for P1.10 summary pack. |
| `scripts/evaluate_prior_day_context_stock_effect.py` | Tool formalization needed later. |
| `tests/test_prior_day_context_stock_effect.py` | Hold with related tool. |

### E. Trend / confirmation coverage

| Path | Reason |
| --- | --- |
| `reports/analysis/evaluations/recent_0935_confirmation_backfill_20260622_20260626.json` | Hold for P1.11. |
| `reports/analysis/evaluations/recent_0935_confirmation_backfill_20260622_20260626.md` | Hold for P1.11. |
| `scripts/evaluate_recent_trend_confirmation_coverage.py` | Tool formalization needed later. |
| `tests/test_recent_trend_confirmation_coverage.py` | Hold with related tool. |

## Security / Environment Notes

- No credential-like secret is intentionally submitted.
- Some held files may contain environment-specific paths or execute-style wording and should be reviewed in their own branches.
- Real dates, codes, groups, and failure samples are retained when included because they are needed for the feedback loop.
- This pack does not run or authorize market-structure backfill.

## Next Loop Candidates

- P1.9: Market-structure Backfill Execution Gate Refactor
- P1.10: Prior-day Context Evidence Loop
- P1.11: Trend Confirmation Coverage Expansion
- P1.12: Auction Replay Evidence Pack Expansion
