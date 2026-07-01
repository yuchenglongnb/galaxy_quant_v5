# iFind Raw Capture Smoke 20260626

- raw_readiness: `missing`
- manifest_path: `C:\Users\40857\Desktop\galaxy_quant_v5\AmazingData_Store\20260626\ifind\raw\raw_manifest.json`
- snapshot_rebuild_attempted: `False`
- snapshot_rebuild_success: `False`
- auction_replay_attempted: `False`
- auction_replay_success: `False`
- cp_audit_rerun_attempted: `False`
- cp_audit_rerun_success: `False`
- warnings: `['limitup_ladder_raw.csv:missing', 'raw_missing', 'sector_strength_raw.csv:missing', 'theme_limitup_raw.csv:missing']`
- conclusion: `['do_not_fabricate_snapshot', 'keep_cp_rules_unchanged', 'raw_capture_smoke_only', 'raw_missing', 'snapshot_rebuild_blocked']`

## Before / After

- snapshot_missing: `{'before': 0, 'after': 0}`
- evidence_missing_false_positive: `{'before': 0, 'after': 0}`
- exemption_ready_false_positive: `{'before': 0, 'after': 0}`
- rule_gap_false_positive: `{'before': 0, 'after': 0}`

## Raw Files

```json
{
  "sector_strength_raw.csv": {
    "exists": false,
    "rows": 0,
    "columns": [],
    "required_fields_missing": [
      "amount_yuan",
      "dde_net_buy_yuan",
      "limitup_count",
      "member_count",
      "pct",
      "sector_name",
      "turnover_rate"
    ],
    "missing_reason": "not_available",
    "schema_version": "v1"
  },
  "theme_limitup_raw.csv": {
    "exists": false,
    "rows": 0,
    "columns": [],
    "required_fields_missing": [
      "highest_board",
      "limitup_count",
      "second_board_count",
      "theme_name",
      "third_board_count"
    ],
    "missing_reason": "not_available",
    "schema_version": "v1"
  },
  "limitup_ladder_raw.csv": {
    "exists": false,
    "rows": 0,
    "columns": [],
    "required_fields_missing": [
      "board_count",
      "code",
      "group",
      "limitup_time",
      "name",
      "theme"
    ],
    "missing_reason": "not_available",
    "schema_version": "v1"
  }
}
```
