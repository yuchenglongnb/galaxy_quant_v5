# iFind Daily Raw Capture Checklist Evaluation

## Operating Decision

The daily iFind raw workflow is now gated by raw readiness:

- `missing`: stop at readiness.
- `sector_only`: allow sector snapshot rebuild.
- `full_ready`: allow full market-structure snapshot rebuild.

## Minimum Usable Condition

`sector_strength_raw.csv` must exist under:

```text
AmazingData_Store/YYYYMMDD/ifind/raw/
```

It must include:

```text
sector_name
pct
turnover_rate
amount_yuan
dde_net_buy_yuan
limitup_count
member_count
```

When these fields are present, the date can reach `sector_only`.

## Full Ready Condition

`full_ready` requires all three raw files to exist with required fields:

- `sector_strength_raw.csv`
- `theme_limitup_raw.csv`
- `limitup_ladder_raw.csv`

Theme or ladder raw alone must not unlock snapshot rebuild for CP exemption
evidence.

## Blocked Condition

When readiness is `missing`, the workflow must stop:

```text
raw missing
-> snapshot rebuild blocked
-> auction replay blocked
-> CP audit rerun blocked
```

## Commands

Readiness:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe main.py ifind raw-readiness --date=YYYYMMDD
```

Smoke:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\run_ifind_raw_capture_smoke.py --date YYYYMMDD
```

Explicit raw staging:

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe scripts\capture_ifind_market_structure_raw.py --date YYYYMMDD --sector-raw PATH_TO_SECTOR_RAW
```

## Guardrails

- Do not fabricate raw.
- Do not fabricate snapshots.
- Do not use post-close outcomes as real-time evidence.
- Do not modify CP rules.
- Do not modify Trend rules.
- Do not write lessons or patterns from this smoke.

## Conclusion

Daily operation should follow:

```text
real iFind raw
-> raw readiness
-> sector_only/full_ready
-> snapshot rebuild
-> auction replay
-> CP evidence audit
-> rule_gap judgment
```

Until real raw exists, the system should remain stopped at readiness.
