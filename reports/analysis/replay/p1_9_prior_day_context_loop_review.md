# P1.9 Prior-day Context Loop Review

## Scope

This review covers the prior-day context stock-effect evidence loop.

Included evidence spans:

```text
20260608, 20260609, 20260616, 20260618, 20260622, 20260623, 20260624, 20260625, 20260626
```

The goal is to preserve real prior-day context feedback as a first-class report pack and formalize the evaluator script as an analysis-only loop tool. This does not modify CP threshold, exemption, Trend active, signal ranking, shortlist generation, evaluator logic, strategy code, config, registry, lesson, or pattern files.

## Why Prior-day Context Matters

Prior-day context is an explanatory evidence layer. It helps answer whether the previous trading day's path, strength, and risk context explains next-day auction candidate behavior.

It is useful for:

- identifying where context bonuses changed candidate rank
- separating stock candidates from ETF/index/industry candidates
- comparing positive, negative, and zero context bonus groups
- checking whether context helped reversal, trend, or trap interpretation
- preserving failure and contradiction samples for later gate review

It is not a trading instruction and does not directly authorize buy/sell action, threshold changes, exemption expansion, or rule updates.

## Relationship to CP / Reversal / Trend

Prior-day context can support later interpretation of:

- CP false positives where the prior-day repair or weakness explains why a risk label did or did not work
- reversal candidates where previous-day context may separate real reversal from continuation weakness
- trend candidates where prior-day context may help explain gap, fade, or continuation paths

In the current report pack, prior-day context is evaluated only as stock-only explanatory evidence. It remains separate from rule changes.

## Current Report Coverage

The report pack includes:

- 9 daily JSON reports
- 9 daily Markdown reports
- 1 summary JSON report
- 1 summary Markdown report

The summary reports:

- `total_stock_candidates = 376`
- `stock_true_bonus_count = 150`
- `positive_bonus_count = 16`
- `negative_bonus_count = 134`
- `zero_bonus_count = 226`
- `overall_rank_changed_count = 57`
- `overall_bucket_changed_count = 0`
- `conclusion = need_more_dates`

## What The Reports Show

The current window shows that prior-day context affected ranking but did not change signal buckets:

- top5 and top10 remained unchanged across all evaluated dates
- top20 changed on one evaluated date
- rank changes clustered on `20260618`, `20260622`, `20260623`, and `20260626`
- context was unavailable for one evaluated date

Bonus-group performance is mixed:

- positive bonus group: average body `0.7997`, success rate `53.4722`
- negative bonus group: average body `1.9297`, success rate `60.0803`
- zero bonus group: average body `1.6041`, success rate `30.2887`

This is useful feedback because it prevents treating positive context bonus as automatically superior in the current sample.

## Failure Modes

Current loop failure modes:

- sample window remains short
- one date has unavailable context
- positive bonus sample count is small
- negative bonus group is much larger than positive bonus group
- category-level evidence is uneven
- trend positive bonus appears weak in this sample
- top rank changes exist, but bucket changes are zero

These are analysis inputs, not rule-change triggers.

## Tool Formalization Decision

`scripts/evaluate_prior_day_context_stock_effect.py` was formalized as an analysis-only loop tool because the structure is simple and risk is manageable.

Changes:

- added explicit analysis-only module boundary
- added `--dry-run`
- added `--output-dir`
- split day and summary output writers
- kept report writes constrained to the default evaluation directory or an explicit output directory
- preserved existing statistics and bucket semantics

The related test now covers:

- fixture-based stock-only behavior
- explicit output directory writes
- dry-run no-write behavior
- no lesson/pattern/registry path references in generated output

## What Is Not Supported Yet

The current evidence does not support:

- CP threshold changes
- CP exemption expansion
- Trend active enablement
- reversal trigger changes
- signal ranking rule changes
- strategy implementation changes
- deterministic interpretation of prior-day context bonus

The current conclusion remains sample-limited: `need_more_dates`.

## Next Expansion Plan

Recommended next steps:

1. Extend prior-day context evidence to a broader date window.
2. Join prior-day context with P1.5 intraday path features.
3. Compare prior-day context buckets by market phase.
4. Track contradiction examples where context bonus direction disagrees with outcome.
5. Add gate criteria before any future rule proposal discussion.

Suggested follow-up:

```text
P1.9B: Prior-day Context Path Join and Contradiction Review
```
