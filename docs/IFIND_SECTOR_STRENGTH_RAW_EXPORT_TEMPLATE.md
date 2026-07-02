# iFind Sector Strength Raw Export Template

This template defines the minimum sector-strength raw export needed for the
`sector_only` iFind market-structure readiness gate.

The export is a raw evidence input. It must be collected from iFind or a trusted
manual export, then validated before any snapshot rebuild.

## Target Path

```text
AmazingData_Store/YYYYMMDD/ifind/raw/sector_strength_raw.csv
```

## Required Columns

```text
sector_name
pct
turnover_rate
amount_yuan
dde_net_buy_yuan
limitup_count
member_count
```

## Optional Columns

```text
limitup_ratio
sector_code
main_net_inflow_yuan
rank
source
```

## Common Chinese Column Hints

```text
板块名称 -> sector_name
概念名称 -> sector_name
名称 -> sector_name
涨跌幅 -> pct
涨幅 -> pct
换手率 -> turnover_rate
成交额 -> amount_yuan
DDE净额 -> dde_net_buy_yuan
DDE大单净额 -> dde_net_buy_yuan
主力净流入 -> main_net_inflow_yuan
涨停家数 -> limitup_count
涨停股票数量 -> limitup_count
成分股数量 -> member_count
股票数 -> member_count
```

The validator reports these hints but does not silently rewrite the raw export.

## Dry-run Command

Validate a raw export without staging or rebuilding:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\validate_sector_strength_raw_export.py --date YYYYMMDD --file PATH_TO_SECTOR_STRENGTH_RAW
```

Validate the repository template:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\validate_sector_strength_raw_export.py --template
```

## Guardrails

- Do not fabricate raw files.
- Do not fabricate snapshots.
- Do not use post-close validation to fill real-time evidence.
- Do not modify CP rules because an export is missing fields.
- Treat this as a dry-run until the raw file is explicitly staged.
