# P2.3C 09:35 Query Subprocess Hardening Review

## Scope

P2.3C hardens the AmazingData historical 09:35 query path by adding a subprocess worker with framed JSON output. The goal is to keep SDK noise out of the parent collector and make query failures structured enough for loop review.

## Why Subprocess Hardening Is Needed

P2.3B added historical query modes, but a 20260703 dry-run did not return structured JSON. Without a strict worker protocol, SDK stdout/stderr behavior can make the parent process unable to distinguish real data, logs, and early exits.

P2.3C adds:

```text
scripts/amazing_0935_query_worker.py
```

The worker writes no repo files and prints framed JSON only.

## Worker Request Schema

```json
{
  "date": "20260703",
  "codes": ["000001.SZ"],
  "mode": "historical-snapshot-query",
  "query_window_start": 93500000,
  "query_window_end": 93559999,
  "amazing_local_config": ""
}
```

## Worker Response Schema

```json
{
  "status": "ok",
  "date": "20260703",
  "mode": "historical-snapshot-query",
  "row_count": 1,
  "rows": [],
  "warnings": []
}
```

Errors are also structured:

```json
{
  "status": "query_failed",
  "error_type": "RuntimeError",
  "sanitized_error": "query_failed",
  "row_count": 0,
  "rows": []
}
```

## JSON Framing

The worker wraps the payload with:

```text
__AMAZING_0935_JSON_BEGIN__
{...}
__AMAZING_0935_JSON_END__
```

The parent collector only parses the framed content. If markers are missing, it returns:

```text
structured_json_missing
```

and does not write artifacts.

## Sanitization Boundary

The parent does not commit stderr or supplier logs. The worker does not echo credential/config values in its response.

## 20260703 Snapshot Retry Result

Command shape:

```text
<amazing-python> scripts/collect_0935_feedback.py --date 20260703 --mode historical-snapshot-query --allow-online-query --query-backend subprocess --worker-python <amazing-python> --query-window-start 93500000 --query-window-end 93559999 --dry-run
```

Result:

```text
status = query_failed
error = structured_json_missing
candidate_count = 52
artifact_written = false
```

## 20260703 Min1 Fallback Result

Command shape:

```text
<amazing-python> scripts/collect_0935_feedback.py --date 20260703 --mode historical-min1-kline --allow-online-query --query-backend subprocess --worker-python <amazing-python> --dry-run
```

Result:

```text
status = query_failed
error = structured_json_missing
candidate_count = 52
artifact_written = false
```

## Generated Artifact Or Gap

No real 20260703 `stock_confirmation_0935.csv` artifact is generated in this PR. The failure is now structured and reproducible.

## Matrix Backfill Result

No temporal matrix backfill is generated because no 20260703 09:35 artifact was written.

## 20260706 Status

20260706 still lacks:

```text
reports/validation/daily/20260706/signal_detail.csv
```

No full-market query was attempted.

## What This Does Not Support

This work does not support trading instructions, threshold changes, exemption expansion, Trend active enablement, strategy changes, registry writes, runtime memory writes, or market-structure execute paths.
