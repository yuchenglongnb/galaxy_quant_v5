# P2.4 State Transition Data Flywheel Review

## Scope

P2.4 adds an observation-only close-to-next-close feedback loop. It fixes correctness and replay side effects first, then derives prior-day outcome features, predicts a shadow state, and validates it against the next available evidence level.

## Correctness Fixes

- `SignalShortlistAnalyzer._build_trend_coverage_context()` now returns the `TrendCandidateFilter` coverage dictionary instead of falling through to `None`.
- The misplaced coverage return was removed from `_apply_prior_day_context_shadow()`.
- `PriorDayReadthroughBuilder` no longer compares missing category rates with numbers.
- Historical replay supports `--no-runtime-memory-write`; reports and validations remain writable while lessons and pattern progress are not mutated.
- Provider-aware synchronization verifies files, row counts, session state, and cache completeness. Function completion alone is never treated as successful synchronization.
- P2.4R1 requires at least three positive cluster samples before concentration can support a rotational-repair label and separates AmazingData candidate blockers from iFinD evidence attribution.
- P2.4R2 separates the incoming prior transition from the current close shadow, so a daily report no longer combines a D-day baseline with D-1 close features.
- A valid transition pair now requires verified `candidate_close` evidence and usable features on both the decision and feedback dates.

## Outcome Features

The new builder derives Trend count/rate/body distribution, path-risk numerators and denominators, deduplicated positive-cluster concentration, confidence, and sector price-turnover labels. Existing prior-day context fields remain compatible.

20260706 high-confidence features:

- Trend: 27 samples, 40.74% success, -0.9802% average body.
- broad path risk: 20/34, 58.82%.
- one-way selloff: 7/34, 20.59%.
- cluster top-1/top-3 shares: 18.18% / 36.36%, dispersed.

20260707 high-confidence features:

- Trend: 29 samples, 13.79% success, -2.2832% average body.
- broad path risk: 38/57, 66.67%.
- one-way selloff: 16/57, 28.07%.
- cluster top-1/top-3 shares: 16.67% / 33.33%, dispersed.

## Baseline Versus Shadow

The active 20260706 baseline remained `continuation / trend_enabled`. The shadow output was `weak_continuation`. The next-day candidate feedback was `broad_continuation_failed`, with Trend success falling to 13.79% and average body to -2.2832%.

The 20260706 -> 20260707 record preserves `next_day_regime=hostile`. It is the only valid candidate pair in this package. The following 20260707 -> 20260708 record is `sector_range_context`, because iFinD returned a period arithmetic mean rather than a daily sector return; it is not counted as a T+1 candidate transition or daily price confirmation.

This is a meaningful contradiction for the feedback loop, but only one candidate-level transition pair. The active environment gate, Trend active, thresholds, ranking, and strategy logic remain unchanged.

## Data Continuation

Latest fully closed date at execution was 20260716.

- candidate-level verified: 20260706, 20260707.
- sector range context: 20260708, 20260709, 20260710, 20260713, 20260714, 20260715, 20260716.
- candidate-level missing: every sector-only date above.
- AmazingData online path: blocked by prior login control-flow evidence; no retry was attempted.
- iFinD MCP: sector evidence only in this package; no candidate-level data was created.

## iFinD Findings

The exact exposed iFinD MCP schemas were inspected before use. `sector_data({query})` provided partial historical sector evidence. `get_stock_performance({query})` supports historical A-share daily OHLCV, but candidate-level requests were not made because a valid candidate universe was unavailable for the missing dates. Current-day high-frequency tools do not support historical dates.

For 20260708-20260716, semiconductor equipment was `price_without_turnover_confirmation`; robot was `weak_or_cooling`. Innovation drug, optical communication/fiber, and securities returned no usable table in the attempted sector queries and remain explicit gaps.

## Prediction Error Analysis

The largest verified error was the active 20260706 continuation interpretation. Auction-time breadth looked supportive, but close evidence already showed negative Trend body and broad risky paths. The likely missing causal layer is not a single threshold; it is the joint state of close validation quality, path breadth, and cluster concentration.

The cluster evidence also disagreed with the qualitative local-repair narrative: row-level positive clusters appeared dispersed, while semiconductor/STAR repair was visible in review text. Likely contributors are inconsistent cluster taxonomy, duplicate semantic clusters, and historical label readability. This should be normalized before using concentration beyond shadow analysis.

## Safety Boundary

All new thresholds are marked `analysis_only_shadow_threshold` and `not_active_strategy_rule`. No trading instruction, threshold change, exemption expansion, Trend activation, ranking change, registry write, runtime-memory write, or candidate fabrication is included.

## Next Action

Continue collecting close-to-T+1 pairs until at least 10 candidate-level transitions across at least three regimes exist. Before that point, use the shadow output only to surface contradictions and data-collection priorities.
