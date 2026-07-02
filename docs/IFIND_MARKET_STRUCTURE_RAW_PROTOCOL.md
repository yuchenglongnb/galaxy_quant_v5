# iFind Market-structure Raw Protocol

This protocol standardizes the local raw inputs required before rebuilding
market-structure snapshots for leading-cluster and CP exemption evidence.

The repository does not fabricate iFind raw data and does not call iFind MCP
directly from strategy evaluators. Raw exports must be captured first, then
validated locally.

## Directory

```text
AmazingData_Store/YYYYMMDD/ifind/raw/
  sector_strength_raw.csv
  theme_limitup_raw.csv
  limitup_ladder_raw.csv
  raw_manifest.json
```

## Raw Files

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

Optional fields:

```text
limitup_ratio
sector_code
main_net_inflow_yuan
rank
source
```

### theme_limitup_raw.csv

Required fields:

```text
theme_name
limitup_count
second_board_count
third_board_count
highest_board
```

Optional fields:

```text
member_count
diffusion_score
source
```

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

Optional fields:

```text
first_limitup_time
last_limitup_time
sealed_amount
open_count
source
```

## Manifest

`raw_manifest.json` records raw-file existence, row counts, columns, missing
required fields, readiness, and warnings.

Readiness values:

- `full_ready`: sector, theme, and ladder raw files all exist with required fields.
- `sector_only`: sector raw exists with required fields; theme/ladder are missing or incomplete.
- `theme_only`: theme raw exists with required fields but sector is not ready.
- `ladder_only`: ladder raw exists with required fields but sector is not ready.
- `missing`: no usable raw input is available.

## CLI

```powershell
python scripts/evaluate_ifind_raw_readiness.py --date YYYYMMDD
python scripts/evaluate_ifind_raw_readiness.py --start-date YYYYMMDD --end-date YYYYMMDD
python main.py ifind raw-readiness --date=YYYYMMDD
python main.py ifind raw-readiness --start-date=YYYYMMDD --end-date=YYYYMMDD
```

Daily operating checklist:

```text
docs/IFIND_DAILY_RAW_CAPTURE_CHECKLIST.md
```

Single-day smoke:

```powershell
python scripts/run_ifind_raw_capture_smoke.py --date YYYYMMDD
```

Explicit raw staging:

```powershell
python scripts/capture_ifind_market_structure_raw.py --date YYYYMMDD --sector-raw PATH_TO_SECTOR_RAW
```

Sector-strength export dry-run:

```powershell
python scripts/validate_sector_strength_raw_export.py --date YYYYMMDD --file PATH_TO_SECTOR_STRENGTH_RAW
python scripts/validate_sector_strength_raw_export.py --template
```

## Guardrails

- Do not generate market-structure snapshots when raw files are missing.
- Do not fill missing raw fields with guessed values.
- Do not use AmazingData industry data as iFind theme/limit-up breadth evidence.
- Do not change CP rules or leading-cluster rules based on missing raw.
- Rebuild snapshots only after raw readiness reaches `sector_only` or `full_ready`.
