# CP Market-structure Snapshot Backfill

- dates: `['20260622', '20260623', '20260624', '20260625', '20260626']`
- execute: `False`
- rebuilt_dates: `[]`
- not_rebuilt_dates: `['20260622', '20260623', '20260624', '20260625', '20260626']`
- ifind_raw_missing_dates: `['20260622', '20260623', '20260624', '20260625', '20260626']`
- warnings: `['ifind_raw_missing', 'dry_run_no_snapshot_rebuild']`

## Before / After

- builder_attachment_missing: `{'before': 0, 'after': 0}`
- evidence_missing_false_positive: `{'before': 28, 'after': 28}`
- exemption_ready_false_positive: `{'before': 3, 'after': 3}`
- leading_cluster_snapshot_missing: `{'before': 28, 'after': 28}`
- rule_gap_false_positive: `{'before': 0, 'after': 0}`
- sector_breadth_snapshot_missing: `{'before': 28, 'after': 28}`
- snapshot_missing: `{'before': 28, 'after': 28}`

## Sector Breadth Field Coverage

- 20260622: `{'exists': False, 'present_fields': [], 'missing_fields': ['amount_yuan', 'dde_net_buy_yuan', 'limitup_count', 'limitup_ratio', 'member_count', 'net_active_buy_yuan', 'pct', 'sector_name', 'sector_strength_score', 'turnover_rate'], 'coverage_ratio': 0.0}`
- 20260623: `{'exists': False, 'present_fields': [], 'missing_fields': ['amount_yuan', 'dde_net_buy_yuan', 'limitup_count', 'limitup_ratio', 'member_count', 'net_active_buy_yuan', 'pct', 'sector_name', 'sector_strength_score', 'turnover_rate'], 'coverage_ratio': 0.0}`
- 20260624: `{'exists': False, 'present_fields': [], 'missing_fields': ['amount_yuan', 'dde_net_buy_yuan', 'limitup_count', 'limitup_ratio', 'member_count', 'net_active_buy_yuan', 'pct', 'sector_name', 'sector_strength_score', 'turnover_rate'], 'coverage_ratio': 0.0}`
- 20260625: `{'exists': False, 'present_fields': [], 'missing_fields': ['amount_yuan', 'dde_net_buy_yuan', 'limitup_count', 'limitup_ratio', 'member_count', 'net_active_buy_yuan', 'pct', 'sector_name', 'sector_strength_score', 'turnover_rate'], 'coverage_ratio': 0.0}`
- 20260626: `{'exists': False, 'present_fields': [], 'missing_fields': ['amount_yuan', 'dde_net_buy_yuan', 'limitup_count', 'limitup_ratio', 'member_count', 'net_active_buy_yuan', 'pct', 'sector_name', 'sector_strength_score', 'turnover_rate'], 'coverage_ratio': 0.0}`

## Recommended Next Actions

- collect_ifind_market_structure_raw
- rebuild_market_structure_snapshot_after_raw_available
- backfill_sector_breadth_fields
- review_sector_alias_after_snapshot_backfill
