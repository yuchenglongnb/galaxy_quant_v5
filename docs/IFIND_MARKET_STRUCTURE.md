# iFinD Market Structure Snapshot

## Goal

This stage adds a local normalization layer for iFinD market-structure data:

- limit-up ladder
- sector strength
- theme diffusion

It does **not** change shortlist decisions yet.

## Principle

The repository still does not call iFinD MCP directly.

Workflow:

```text
iFinD MCP query in Codex session
-> raw CSV snapshot
-> local provider normalization
-> local cache / evaluation outputs
```

## CLI

```powershell
python main.py ifind market-structure --date=YYYYMMDD --limitup-raw=PATH --sector-raw=PATH
```

## Inputs

- `limitup_raw`: raw CSV exported from iFinD MCP for涨停/连板/题材归属
- `sector_raw`: raw CSV exported from iFinD MCP for板块强度/成交金额/净主动买入额

## Outputs

```text
AmazingData_Store/YYYYMMDD/ifind/
  limitup_ladder_snapshot.csv
  sector_strength_snapshot.csv
  theme_limitup_distribution.csv

reports/analysis/evaluations/
  ifind_market_structure_YYYYMMDD.json
  ifind_market_structure_YYYYMMDD.md
```

## What This Stage Solves

1. standardizes messy raw field names
2. preserves missing `连板天数` instead of forcing `0`
3. builds a reproducible sector strength score
4. prepares later `leading_cluster_evidence` inputs

## What This Stage Does Not Do

1. CP leading-cluster exemption
2. trend hard gate
3. direct shortlist filtering
4. direct MCP access inside repo code

## Next Recommended Step

After this layer is stable:

```text
market structure snapshot
-> leading_cluster_evidence expansion
-> CP risk evaluator
-> trend triple gate
```
