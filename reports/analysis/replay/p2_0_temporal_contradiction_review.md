# P2.0 Temporal Contradiction Review

## Measurable Pairs

Currently measurable:

```text
prior_day_context -> same_day_close
prior_day_context -> rank_change
prior_day_context -> body_pct
prior_day_context -> validation_success
```

Partially measurable from existing P1.5 reports:

```text
auction/path candidates -> same_day_close
auction/path candidates -> t1_close
```

Not yet structured:

```text
auction -> same_day_0935
auction -> same_day_midday
0935 -> same_day_midday
close / next_day_plan -> t1_auction
close / next_day_plan -> t5_close
close / next_day_plan -> t10_close
close / next_day_plan -> t20_close
```

## Early Confirmation Examples

No structured 09:35 confirmation sample is included in the P2.0 seed. This remains a missing capability.

## Early Failure Examples

No structured 09:35 failure sample is included in the P2.0 seed. This remains a missing capability.

## Delayed Success / Failure

T+5/T+10/T+20 feedback is not yet available in structured form. P2.0 does not infer delayed labels.

## Prior-day Context Contradictions

The seed matrix can identify:

```text
positive_context_but_weak_path
negative_context_but_strong_path
rank_up_but_path_weak
rank_down_but_path_strong
```

These are not rule-change conclusions. They are candidates for:

- broader-window validation
- path-type joins
- regime snapshots
- contradiction tracking

## Rank-change Contradictions

The current prior-day reports show rank changes but no bucket changes.

This matters because rank movement can be visible without changing the final signal family or bucket. Future analysis should test whether rank movement improves path quality or only reshuffles candidates without actionable validation gain.

## Missing Data Limitations

- No midday feedback.
- No forward-horizon feedback.
- No per-record prior-day-to-path join.
- No regime snapshot join.
- No 09:35 structured parser in this seed.

## Next Expansion Plan

1. Build auction -> 09:35 / midday / close feedback records.
2. Join prior-day context records to P1.5 path metrics.
3. Add close / next-day plan -> T+1 auction feedback.
4. Add T+5/T+10/T+20 delayed feedback.
5. Build contradiction board by signal family and regime.
