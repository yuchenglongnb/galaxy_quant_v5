# P2.3D AmazingData Worker Preflight Manifest

## Included Files

```text
scripts/amazing_0935_preflight_probe.py
scripts/run_0935_preflight_probe.py
tests/test_amazing_0935_preflight_probe.py
reports/analysis/evaluations/amazing_0935_preflight_20260703.json
reports/analysis/evaluations/amazing_0935_preflight_20260703.md
reports/analysis/replay/p2_3d_amazingdata_worker_preflight_review.md
reports/analysis/replay/p2_3d_amazingdata_worker_preflight_manifest.md
reports/analysis/replay/p2_3d_0935_backfill_gap_20260703.md
reports/analysis/replay/p2_3d_0935_backfill_gap_20260706.md
```

## Generated Artifacts

The probe generated a structured diagnostic report for 20260703. It did not generate row-level 09:35 confirmation artifacts.

## Query Backend

```text
backend = subprocess preflight
worker = scripts/amazing_0935_preflight_probe.py
runner = scripts/run_0935_preflight_probe.py
```

## Date Coverage

```text
20260703: candidate source exists, 52 rows, login stage failed
20260706: candidate source missing, no query attempted
```

## Candidate / Matched / Missing Counts

```text
20260703 candidate_count = 52
20260703 probe_code_count = 1
20260703 matched_count = not attempted
20260703 missing_count = not attempted
```

## First Failing Stage

```text
login
```

The probe reached `import_amazingdata` successfully and then failed at `login` with a sanitized `SystemExit` result.

## Sensitive Content Boundary

This package does not commit passwords, tokens, secrets, username values, host values, port values, supplier logs, or full-market raw snapshots. The committed report only records boolean config readiness and sanitized stage status.

## Tests

```bash
python -m pytest tests/test_amazing_0935_preflight_probe.py -q
python -m pytest tests/test_amazing_0935_query_worker.py -q
python -m pytest tests/test_collect_0935_feedback.py -q
python -m pytest tests/test_temporal_feedback_matrix.py -q
python -m py_compile scripts/amazing_0935_preflight_probe.py scripts/run_0935_preflight_probe.py scripts/amazing_0935_query_worker.py scripts/collect_0935_feedback.py reports/temporal_feedback_matrix.py
python -m pytest tests/test_prior_day_context_stock_effect.py -q
python -m pytest tests/test_cp_evidence_backfill_readiness.py -q
```

## How ChatGPT Should Use This

Use the report to avoid blind retries. The next debugging step is the login stage, not snapshot parsing, min1 parsing, temporal matrix logic, or candidate matching.

## Next Loop Questions

```text
1. Why does AmazingData login raise SystemExit in the worker process?
2. Does the login style need to match a known working script exactly?
3. Should the next retry use an existing successful login helper or a narrower login probe?
4. Can 20260706 candidate generation be produced before another 09:35 backfill attempt?
```
