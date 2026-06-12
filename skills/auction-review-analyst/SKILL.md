---
name: auction-review-analyst
description: Analyze GalaxyQuant auction reports, intraday/post-close validation CSVs, and daily signal feedback loops. Use when reviewing auction strategy output, explaining CP/reversal/trend signal success or failure, writing data-status-aware market conclusions, or updating the methodology after user feedback.
---

# Auction Review Analyst

This repository copy is the editable source of truth for the GalaxyQuant auction-review workflow. To make Codex auto-discover it across sessions, sync this folder to `C:\Users\40857\.codex\skills\auction-review-analyst`.

## Core Workflow

Use this structure for every GalaxyQuant auction review unless the user asks for a narrower answer:

1. Data status
2. Market environment
3. Index signals
4. ETF signals
5. Stock-pool signals
6. Industry/top-k signals
7. Validation result
8. Analyst judgment
9. Follow-up observation points
10. Methodology update when needed

Always separate numeric facts from interpretation.

## Intraday And Post-Close Loop

When the user gives intraday data and wants a same-day judgment:

1. State clearly whether the cache is `intraday` or `closed`.
2. Mark every close/body conclusion as provisional when the session is still intraday.
3. Produce two layers of output:
   - `current reading`: what the market looks like right now
   - `testable hypothesis`: what must remain true by close to validate the reading
4. After the close, compare the intraday reading against:
   - `signal_metrics.csv`
   - `signal_detail.csv`
   - daily `auction_review.md`
5. Save the mismatch or confirmation as:
   - lesson first
   - pattern only after repetition

Preferred intraday framing:

- `broad_strong_repair`: broad risk-on repair, trend can open wider
- `rotational_strong_repair`: index repair exists, but leadership rotates to a few new clusters
- `weak_repair`: rebound attempt without broad confirmation
- `weak_continuation`: weak market extends, do not over-read low opens as reversal

When the tape looks like `rotational_strong_repair`, do not translate it into “trend everywhere”.
Use this language instead:

- do new strong clusters
- avoid chasing old crowded leaders
- allow selective low-open absorption
- do not treat high-open GEM / STAR as automatic tech continuation

## Required Local Artifacts

Prefer these project files when available:

- `logs/reports/YYYY/MM/DD/*_AuctionRunner.log`
- `reports/validation/daily/YYYYMMDD/signal_detail.csv`
- `reports/validation/daily/YYYYMMDD/signal_metrics.csv`
- `reports/validation/daily/YYYYMMDD/factor_snapshot_index.csv`
- `reports/validation/daily/YYYYMMDD/factor_snapshot_etf.csv`
- `reports/validation/daily/YYYYMMDD/factor_snapshot_stock.csv`
- `reports/validation/daily/YYYYMMDD/factor_snapshot_industry_topk.csv`
- `reports/analysis/daily/YYYYMMDD/auction_review.md`
- `reports/analysis/daily/YYYYMMDD/auction_review.json`
- `reports/analysis/lessons/auction_lessons.jsonl`
- `reports/analysis/methodology/AUCTION_RESEARCH_METHOD.md`
- `reports/analysis/patterns/market_pattern_registry.json`

If a same-day cache is `intraday`, state clearly that close/body/validation values are temporary intraday readings and must be revalidated after the market closes.

## Data Status Checks

Before judging a report, check cache metadata when possible:

- `AmazingData_Store/YYYYMMDD/stocks.meta.json`
- `AmazingData_Store/YYYYMMDD/indices.meta.json`

Use:

- `session_state=closed`: post-close validation is allowed.
- `session_state=intraday`: only intraday decisions or provisional validation are allowed.
- missing or empty files: do not trust T-1/T-2 or validation.

If prior trading day data is missing, explain that T-1/T-2 conclusions may be invalid.

## Signal Validation Rules

Use the project convention:

- `CP risk`: successful when `body_pct < 0`.
- `Reversal opportunity`: successful when `body_pct > 0`.
- `Trend opportunity`: successful when `body_pct > 0`.

Do not call CP a high-open trap unless the facts show a high open. If CP is triggered after prior strength but current auction is weak or flat, describe it as profit-taking risk.

## Analysis Principles

Base conclusions on numeric facts:

- `auction_pct`: auction gap or open relative to prior close.
- `close_pct`: current or close return relative to prior close.
- `body_pct`: close minus auction/open; core validation field.
- `CP`: crowding or profit-taking risk.
- `SA`: reversal absorption opportunity.
- `oar` or `market_oar`: volume environment.
- `vol_ratio`, `pos_5d`, `rank`, and `signal_category` when present.

Use concise labels:

- shrinking volume plus broad negative body: risk-off / stock-capital selling pressure.
- high open plus negative body: high-open trap.
- prior strong plus weak/flat auction plus negative body: profit-taking risk.
- low open plus positive body: reversal absorption.
- positive body with stable volume and moderate CP: trend continuation.
- strong repair plus cluster rotation: structural rotation day.
- old high leader gap-up then negative body while new clusters strengthen: old-leader profit-taking vs new-cluster acceleration.

For CP interpretation, distinguish these subtypes whenever facts allow:

- `high_open_trap`: true high-open crowding and fade
- `profit_taking_risk`: prior strength followed by weak/flat open and negative body
- `rotation_exempt_cp`: CP triggered numerically, but the target belongs to the strongest new cluster of the day

## Output Style

Use a compact Chinese report in the final answer. Lead with whether the report is usable.

Recommended shape:

```text
Data status:
- Date:
- Cache state:
- Post-close validation allowed:

Core conclusion:
- ...

Signal validation:
- CP risk: x/y, key success/failure samples...
- Reversal opportunity: x/y...
- Trend opportunity: x/y...

Analyst judgment:
- ...

Follow-up observations:
- ...
```

## Methodology Evolution

When the user gives a correction or a signal fails in a meaningful way:

1. Identify the failed assumption.
2. Save a compact lesson to `reports/analysis/lessons/auction_lessons.jsonl` if editing is in scope.
3. Check whether the case matches an existing pattern in `reports/analysis/patterns/market_pattern_registry.json`.
4. If it does not match, add a new observed pattern or extend the methodology file.
5. Prefer changing deterministic labels or thresholds only after repeated evidence.
6. Keep AI text generation bounded by computed facts.

Use this escalation ladder:

```text
single-day fact
-> lesson
-> repeated lesson cluster
-> pattern
-> rule/config or ranking feature
```

Default posture:

- skill stores workflow
- methodology stores reusable analytical principles
- pattern registry stores recurring market structures
- lesson file stores daily evidence

When a day shows “index repair + cluster rotation + old leader profit-taking”, prefer this upgrade path:

```text
single-day observation
-> strong_repair_with_rotation lesson
-> repeated cross-month evidence
-> CP exemption / trend filter rule
```

Lesson JSONL fields:

```json
{
  "date": "YYYYMMDD",
  "source": "auction_review",
  "signal_type": "CP risk|reversal opportunity|trend opportunity|market_env|other",
  "case": "...",
  "facts": {},
  "lesson": "...",
  "suggested_change": "...",
  "status": "observed|implemented|rejected"
}
```

## Guardrails

- Do not invent market facts not present in logs or CSVs.
- Do not treat intraday snapshot validation as final.
- Do not use an external model/API unless the user explicitly asks or project settings require it.
- Preserve the distinction between index, ETF, stock, and industry universes.
