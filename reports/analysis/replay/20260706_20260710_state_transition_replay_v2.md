# 20260706-20260710 State Transition Replay V2

## Scope

This replay evaluates states in chronological order. Each close prediction uses only evidence available at that close, and the next available period is used as posterior feedback. It is observation-only and does not change the active environment gate, Trend active, ranking, or strategy behavior.

## Evidence Levels

| Date | Evidence level | Available evidence | Missing evidence |
|---|---|---|---|
| 20260706 | candidate-level verified | 198-stock daily OHLCV, 31 indices, auction review, close validation | midday candidate snapshot |
| 20260707 | candidate-level verified | 198-stock daily OHLCV, 31 indices, auction review, close validation | midday candidate snapshot |
| 20260708-20260710 | sector-level evidence only | partial iFinD sector range/turnover evidence | candidate universe, candidate close validation, midday feedback |

## Sequential Prediction And Validation

### 20260706 Close -> 20260707 Close

Baseline at 20260706 close:

- market regime: `continuation`
- active environment decision: `trend_enabled`

Shadow evidence available at 20260706 close:

- Trend sample count: 27
- Trend success rate: 40.74%
- Trend average body: -0.9802%
- Trend median body: -0.0952%
- broad path risk ratio: 58.82% (20/34)
- one-way selloff ratio: 20.59% (7/34)
- positive cluster top-1 share: 18.18%
- feature confidence: high

The shadow prediction was `weak_continuation`. It was intentionally weaker than the active `trend_enabled` decision because all four broad-risk observations were adverse while positive samples were dispersed rather than concentrated.

Actual 20260707 feedback:

- Trend success rate: 13.79% (4/29)
- Trend average body: -2.2832%
- broad path risk ratio: 66.67% (38/57)
- one-way selloff: 16
- close-near-low: 8
- low-open-rebound-failed: 7

Feedback label: `broad_continuation_failed`.

Contradictions:

- `baseline_trend_enabled_but_broad_trend_failed`
- `continuation_but_negative_trend_body`

The actual outcome was materially closer to `weak_continuation` than to unrestricted broad continuation. This is one verified transition pair, not enough evidence to modify the active gate.

### 20260707 Close -> 20260708 Close

The 20260707 candidate evidence produced `broad_trend_failure_risk`. The next date lacks candidate-level validation, so the posterior label is `sector_only_partial_confirmation`, with `candidate_feedback_missing` retained as a contradiction/data gap.

Sector evidence for 20260708-20260716 shows:

- Semiconductor equipment: range average return +5.5598%, amount change -9.7222%, classified as `price_without_turnover_confirmation`.
- Robot concept: range average return -5.9953%, amount change -10.8778%, classified as `weak_or_cooling`.
- Innovation drug, optical communication/fiber, and securities queries returned no usable structured table in this run.

This evidence is consistent with selective price resilience rather than verified broad Trend recovery, but it cannot validate candidate-level success, path quality, or cluster concentration.

## New Findings

1. Success rate alone was insufficient. On 20260706 CP reported 4/6 successes while average body was -1.41%; the direction metric and path outcome were not aligned.
2. The active regime used auction-time breadth evidence but did not consume close validation quality. The shadow layer captured this mismatch without modifying active logic.
3. Positive cluster concentration computed from row-level labels was dispersed, while the qualitative review described semiconductor/STAR local repair. This gap indicates that cluster naming quality and mojibake normalization need further work before concentration can be trusted as a decisive label.
4. After 20260707, provider availability became the limiting factor. Sector turnover can support a market-level hypothesis, but cannot substitute for candidate-level validation.

## Next State Hypothesis

For the next fully observed session after 20260716, the formal shadow state is `data_insufficient` because candidate-level feedback is missing. The observation hypothesis is `mixed_wait_confirmation`: semiconductor equipment retained positive range performance but lacked turnover confirmation, robot evidence cooled, and three requested sector families were unavailable.

Validation should check, in order:

1. whether a candidate universe and daily OHLCV are complete;
2. whether broad Trend success and average body recover together;
3. whether broad path risk falls below the observation threshold;
4. whether semiconductor strength gains amount confirmation or fades;
5. whether innovation drug, optical communication/fiber, securities, or another cluster supplies measurable rotation breadth.

This is a posterior validation plan, not a trading instruction.
