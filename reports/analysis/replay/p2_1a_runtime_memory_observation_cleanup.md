# P2.1A Runtime Memory Observation Cleanup

## Scope

This review covers the local runtime-memory updates produced by the 20260703 auction replay:

- `reports/analysis/lessons/auction_lessons.jsonl`
- `reports/analysis/patterns/pattern_progress.json`

The goal is to preserve the real 20260703 feedback while cleaning wording that could be misunderstood as a rule, threshold, ranking, or weight-change recommendation.

## Files Reviewed

| File | Role | Action |
| --- | --- | --- |
| `reports/analysis/lessons/auction_lessons.jsonl` | Runtime lesson memory | Preserved 10 appended 20260703 observations and changed rule-like wording to observation-only wording |
| `reports/analysis/patterns/pattern_progress.json` | Pattern progress memory | Preserved updated counts/date context and changed recommendation wording to gate-review observation wording |

## Why Cleanup Is Needed

The 20260703 replay produced useful feedback for the temporal loop, including failed trend samples, CP false-positive observations, and theme-cluster repair context. Some generated phrases could be read as implying that a threshold, weight, ranking, or deterministic rule should be changed.

P2.1A keeps the feedback, but rewrites the interpretation layer so the memory remains posterior and observation-only.

## Lesson Rows Preserved

The cleanup preserves all 10 newly appended 20260703 lesson rows:

- 8 failed validation observations across `趋势机会` and `CP风险`
- 2 market-pattern observations:
  - `cp_false_positive_in_theme_repair`
  - `theme_cluster_repair`

Preserved fields include:

- date
- source
- signal type
- case / pattern id
- CP / SA values
- auction, close, and body returns
- status

No failed sample was deleted, converted into a success, or reclassified as a trading rule.

## Pattern Progress Facts Preserved

The cleanup preserves the runtime progress facts:

- `date` advanced to `20260703`
- `cp_false_positive_in_theme_repair` occurrence count moved from 51 to 52
- `theme_cluster_repair` appears as a tracked runtime pattern with occurrence count 38
- tracked historical date lists are retained

Only the recommendation wording was changed.

## Wording Changed

The cleanup changed generated language in two ways:

1. Failed-signal lesson wording now says the behavior requires broader-sample observation and gate review before any rule discussion.
2. Pattern-progress recommendation wording now uses `evidence_candidate_pending_gate_review`.

The cleaned wording explicitly says:

- thresholds remain unchanged
- rules remain unchanged
- ranking and weight behavior remain unchanged
- broader evidence and gate review are required before any future rule proposal could be discussed

## Before / After Examples

| Area | Before semantics | After semantics |
| --- | --- | --- |
| Failed signal lesson | Repeated failures might imply a threshold or trigger review | Failed outcome is observation evidence only; broader samples and gate review are required before any rule discussion |
| Pattern recommendation | Pattern repetition could be treated as a rule or weight candidate | Pattern repetition is evidence for broader-sample gate review only |
| Pattern note | Pattern repetition could start an upgrade evaluation | Runtime memory does not support rule, weight, ranking, or threshold changes |

## What This Does Not Support

This cleanup does not support:

- CP threshold changes
- CP exemption expansion
- Trend active enablement
- reversal trigger changes
- signal ranking changes
- shortlist or evaluator changes
- strategy/config/registry changes
- trading instructions

## Relationship To P2 Temporal Loop

These runtime-memory files are useful as feedback context for the temporal decision-feedback loop. They provide posterior examples that can feed future contradiction review, path-stability review, and broader-window validation.

They are not sufficient for deterministic rule changes and should remain downstream evidence, not strategy logic.

## Next Action

After P2.1A, the next engineering step is:

`P2.2 Daily Validation -> Temporal Matrix Ingestion Tool`

That step should parse `signal_detail.csv` and `signal_metrics.csv` into temporal feedback records rather than relying on runtime-memory wording.
