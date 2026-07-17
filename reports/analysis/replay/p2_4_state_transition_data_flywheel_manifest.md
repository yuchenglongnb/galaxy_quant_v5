# P2.4 State Transition Data Flywheel Manifest

## Included Code

- Trend coverage context correctness fix.
- None-safe prior-day readthrough.
- Historical replay `--no-runtime-memory-write` support.
- Provider-aware synchronization manifest.
- Prior-day outcome feature builder.
- Observation-only state-transition shadow.
- Close-to-T+1 feedback builder.
- iFinD sector evidence normalizer.

## Included Evidence

- Data availability: 20260706-20260716.
- Candidate outcome features: 20260706 and 20260707.
- Close-to-T+1 transitions: one candidate-verified pair and subsequent range-level sector context records.
- iFinD sector evidence: 20260708-20260716, partial coverage.
- Weekly state-transition replay V2.

## Evidence Levels

| Level | Dates | Meaning |
|---|---|---|
| candidate-level verified | 20260706, 20260707 | Candidate daily OHLCV and close validation exist. |
| sector range context | 20260708-20260710, 20260713-20260716 | iFinD period-level sector evidence may support broad context but is not daily price confirmation. |
| missing candidate feedback | 20260708-20260716 | No candidate-level temporal validation is asserted. |

## Provider Notes

- Provider key: `ifind_mcp`.
- User-visible name: iFinD MCP.
- Historical placeholder `ths_mcp` is renamed in new documentation only; no credential or adapter call is invented.
- Candidate-level iFinD data generated: no.
- AmazingData online query attempted: no.

## Runtime Memory Isolation

The original worktree retained its local `auction_lessons.jsonl` and `pattern_progress.json` modifications. P2.4 was developed in `C:\Users\40857\Desktop\galaxy_quant_v5_p2_4`; those files are neither staged nor modified by this package.

## Deferred

- Midday candidate feedback.
- Candidate-level data after 20260707.
- Daily sector price returns where iFinD returned no table.
- Cluster taxonomy/readability normalization.
- Active environment-gate review until 10 valid transition pairs across three regimes exist.

## How To Use

Read the availability report first, then the outcome-feature report, then the transition report. Treat `candidate_close` as verified only when detail, metrics, final review, and availability all agree. Treat `sector_range_context` as period context that does not count as daily confirmation or a valid candidate pair. Use contradictions to decide what to collect next, not to issue trading instructions.
