# P2.3C 09:35 Query Subprocess Hardening Manifest

## Included Files

```text
scripts/amazing_0935_query_worker.py
scripts/collect_0935_feedback.py
tests/test_amazing_0935_query_worker.py
tests/test_collect_0935_feedback.py
reports/analysis/replay/p2_3c_0935_query_subprocess_hardening_review.md
reports/analysis/replay/p2_3c_0935_query_subprocess_hardening_manifest.md
reports/analysis/replay/p2_3c_0935_subprocess_backfill_gap_20260703.md
reports/analysis/replay/p2_3c_0935_subprocess_backfill_gap_20260706.md
```

## Generated Artifacts

No real 09:35 artifact is generated in this package.

## Query Backend

```text
subprocess
```

## Query Modes Retried

```text
historical-snapshot-query
historical-min1-kline
```

Both returned structured parent-level failure:

```text
structured_json_missing
```

## Candidate Count

20260703:

```text
candidate_count = 52
matched_count = 0
missing_count = 52
```

20260706:

```text
candidate source missing
```

## Tests

P2.3C adds tests for:

- Worker JSON marker emission.
- Worker structured errors.
- Worker request does not echo config values.
- Parent framed JSON parsing.
- Parent missing marker handling.
- Subprocess timeout structured error.
- Mocked subprocess snapshot success.
- Mocked subprocess min1 success.
- Existing temporal parser preference remains unchanged.

## How ChatGPT Should Use This Result

Treat P2.3C as subprocess hardening plus a structured failure record. It proves the collector can now return a machine-readable failure instead of silent output loss, but it does not complete the 20260703 real backfill.

The next loop should inspect why the AmazingData worker process fails to emit markers before attempting another write.

## Next Loop Questions

1. Is the AmazingData SDK exiting the interpreter before worker `emit()`?
2. Is login/bootstrap producing process-level termination instead of Python exceptions?
3. Should the worker be run through a smaller probe that imports AmazingData only after emitting a preflight marker?
4. Should the next retry prefer min1 query directly if snapshot causes process termination?
