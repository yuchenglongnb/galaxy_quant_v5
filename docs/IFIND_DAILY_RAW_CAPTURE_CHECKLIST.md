# iFind Daily Raw Capture Checklist

This checklist is the daily operating layer for iFind market-structure raw
capture. It keeps CP exemption evidence replayable without fabricating raw data,
snapshots, or strategy evidence.

## Daily Scope

After market close, capture raw files for the target trade date:

```text
AmazingData_Store/YYYYMMDD/ifind/raw/
  sector_strength_raw.csv
  theme_limitup_raw.csv
  limitup_ladder_raw.csv
  raw_manifest.json
```

Priority:

1. `sector_strength_raw.csv`
2. `theme_limitup_raw.csv`
3. `limitup_ladder_raw.csv`

The minimum usable state is `sector_only`. Full theme and ladder raw files are
useful, but they are not required for the first CP evidence smoke.

## Required Raw Files

### sector_strength_raw.csv

Required fields:

```text
sector_name
pct
turnover_rate
amount_yuan
dde_net_buy_yuan
limitup_count
member_count
```

When this file exists and all required fields are present, readiness can reach
`sector_only`.

### theme_limitup_raw.csv

Required fields:

```text
theme_name
limitup_count
second_board_count
third_board_count
highest_board
```

Missing or incomplete theme raw must not be treated as `full_ready`.

### limitup_ladder_raw.csv

Required fields:

```text
code
name
board_count
theme
group
limitup_time
```

Missing or incomplete ladder raw must not be treated as `full_ready`.

## Daily Commands

Check readiness:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe main.py ifind raw-readiness --date=YYYYMMDD
```

Dry-run validate a sector-strength export before staging:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\validate_sector_strength_raw_export.py --date YYYYMMDD --file PATH_TO_SECTOR_STRENGTH_RAW
```

Run the single-day smoke:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\run_ifind_raw_capture_smoke.py --date YYYYMMDD
```

Run the sector-only rebuild smoke after `sector_strength_raw.csv` is ready:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\run_sector_only_snapshot_rebuild_smoke.py --date YYYYMMDD
```

If raw exports are staged from explicit files:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\capture_ifind_market_structure_raw.py --date YYYYMMDD --sector-raw PATH_TO_SECTOR_RAW
```

Optional full raw staging:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\capture_ifind_market_structure_raw.py --date YYYYMMDD --sector-raw PATH_TO_SECTOR_RAW --theme-raw PATH_TO_THEME_RAW --limitup-raw PATH_TO_LADDER_RAW
```

## Readiness Gates

`missing`:

- Stop.
- Do not rebuild snapshots.
- Do not rerun auction from rebuilt evidence.
- Do not rerun CP audits as evidence refresh.

`sector_only`:

- Snapshot rebuild is allowed in sector-only mode.
- `sector_strength_snapshot.csv` can be generated.
- Theme and ladder evidence remain unavailable and must stay marked missing.

`full_ready`:

- Full market-structure snapshot rebuild is allowed.
- Sector, theme, and ladder snapshots can be generated from raw.

`theme_only` or `ladder_only`:

- Do not rebuild CP exemption evidence.
- Capture or fix `sector_strength_raw.csv` first.

## Rebuild Chain

Only when readiness is `sector_only` or `full_ready`:

1. Run raw readiness.
2. Rebuild market-structure snapshot from raw.
3. Run `main.py auction YYYYMMDD`.
4. Rerun CP evidence audits:
   - `scripts/evaluate_cp_structural_repair_audit.py`
   - `scripts/evaluate_cp_exemption_evidence_coverage.py`
   - `scripts/evaluate_cp_evidence_backfill_readiness.py`
5. Compare before/after:
   - `snapshot_missing`
   - `evidence_missing_false_positive`
   - `exemption_ready_false_positive`
   - `rule_gap_false_positive`

## Hard Stops

- Do not fabricate raw files.
- Do not fabricate market-structure snapshots.
- Do not fill missing iFind fields from post-close outcomes.
- Do not use after-the-fact validation as real-time evidence.
- Do not change CP thresholds.
- Do not expand CP exemptions.
- Do not modify `CPRiskEvaluator`.
- Do not write lessons or patterns from a raw-capture smoke.

## Sector-only Smoke

Use `scripts/run_sector_only_snapshot_rebuild_smoke.py` when the first real
`sector_strength_raw.csv` is available for a date. This smoke intentionally
uses only sector raw to rebuild `sector_strength_snapshot.csv`; theme and ladder
raw can remain missing.

The smoke must stop when readiness is `missing`, `theme_only`, or `ladder_only`.
It can continue when readiness is `sector_only` or `full_ready`.

## Sector-strength Export Dry Run

Use `scripts/validate_sector_strength_raw_export.py` before staging a fresh
iFind export. The dry run checks required fields and reports common Chinese
column-name mapping suggestions, but it does not rewrite, stage, or normalize
the raw file.

Required fields:

```text
sector_name
pct
turnover_rate
amount_yuan
dde_net_buy_yuan
limitup_count
member_count
```

## Daily Acceptance

A date is ready for CP evidence replay only when:

- `raw_manifest.json` exists.
- readiness is `sector_only` or `full_ready`.
- required fields for the ready raw files are present.
- smoke report confirms `snapshot_rebuild_allowed`.
- no fabricated raw or snapshot is introduced.
