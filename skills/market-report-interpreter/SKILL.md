---
name: market-report-interpreter
description: Interpret GalaxyQuant auction, ETF, index, and sector report signals from structured market facts. Use when generating or reviewing AI report text, replacing hard-coded commentary, validating signal explanations, or folding user corrections into methodology.
---

# Market Report Interpreter

## Workflow

Use structured facts as the only source of market data. Do not invent OHLCV, CP, SA, ranking, volume ratio, or position values.

1. Read the input facts and hard-rule trigger.
2. Detect conflicts between the old label/template and the numeric facts.
3. Select a scenario label from `references/label_taxonomy.md`.
4. Write evidence that cites input fields directly.
5. Add watch points and invalidation conditions.
6. Validate the text with the guardrails in `references/auction_signal_rules.md`.
7. If the user corrects the output, append a compact case to `references/corrections.md`.

## Boundaries

Keep deterministic calculations outside AI:

- `auction_pct`, `close_pct`, `body_pct`, `vol_ratio`, `pos_5d`
- `CP`, `SA`
- rank, trigger, score, validation statistics

AI may write:

- semantic scenario labels
- evidence summaries
- report text
- watch points
- invalidation conditions

## Required Output

Return JSON-shaped content with:

```json
{
  "scenario_label": "...",
  "direction": "risk|opportunity|trend|observe",
  "confidence": 0.0,
  "evidence": ["..."],
  "watch_points": ["..."],
  "invalid_if": ["..."],
  "report_text": "..."
}
```

Keep confidence between `0` and `1`. Use low confidence when facts are mixed.

## References

- Use `references/label_taxonomy.md` for allowed scenario labels.
- Use `references/auction_signal_rules.md` for hard guardrails.
- Use `references/corrections.md` to learn from prior user corrections.
