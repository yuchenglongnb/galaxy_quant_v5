# CP Evidence Backfill Readiness Audit

- dates: `['20260622', '20260623', '20260624', '20260625', '20260626']`
- total_evidence_missing_false_positives: `28`
- missing_reason_distribution: `{'leading_cluster_snapshot_missing': 28, 'sector_breadth_snapshot_missing': 28, 'snapshot_missing': 28, 'alias_or_group_unmatched': 5}`
- recommended_backfill_actions: `['rebuild_market_structure_snapshot', 'add_sector_alias', 'backfill_sector_breadth_fields']`
- conclusion: `['keep_cp_threshold', 'repair_evidence_first', 'no_rule_change_yet', 'not_ready_for_exemption_expansion', 'ready_for_evidence_backfill']`

## By Date

- 20260622: `{'evidence_missing_false_positive_total': 14, 'snapshot_missing_count': 14, 'alias_or_group_unmatched_count': 2, 'sector_breadth_snapshot_missing_count': 14, 'sector_breadth_field_missing_count': 0, 'builder_attachment_missing_count': 0, 'recommended_backfill_actions': ['rebuild_market_structure_snapshot', 'add_sector_alias', 'backfill_sector_breadth_fields']}`
- 20260623: `{'evidence_missing_false_positive_total': 0, 'snapshot_missing_count': 0, 'alias_or_group_unmatched_count': 0, 'sector_breadth_snapshot_missing_count': 0, 'sector_breadth_field_missing_count': 0, 'builder_attachment_missing_count': 0, 'recommended_backfill_actions': ['keep_manual_review']}`
- 20260624: `{'evidence_missing_false_positive_total': 1, 'snapshot_missing_count': 1, 'alias_or_group_unmatched_count': 0, 'sector_breadth_snapshot_missing_count': 1, 'sector_breadth_field_missing_count': 0, 'builder_attachment_missing_count': 0, 'recommended_backfill_actions': ['rebuild_market_structure_snapshot', 'backfill_sector_breadth_fields']}`
- 20260625: `{'evidence_missing_false_positive_total': 13, 'snapshot_missing_count': 13, 'alias_or_group_unmatched_count': 3, 'sector_breadth_snapshot_missing_count': 13, 'sector_breadth_field_missing_count': 0, 'builder_attachment_missing_count': 0, 'recommended_backfill_actions': ['rebuild_market_structure_snapshot', 'add_sector_alias', 'backfill_sector_breadth_fields']}`
- 20260626: `{'evidence_missing_false_positive_total': 0, 'snapshot_missing_count': 0, 'alias_or_group_unmatched_count': 0, 'sector_breadth_snapshot_missing_count': 0, 'sector_breadth_field_missing_count': 0, 'builder_attachment_missing_count': 0, 'recommended_backfill_actions': ['keep_manual_review']}`

## Top Groups

- 数字芯片设计: `{'candidate_count': 5, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 5, 'sector_breadth_snapshot_missing': 5, 'snapshot_missing': 5}}`
- 创业板: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 半导体: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 半导体设备: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 消费电子: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 消费电子零部件及组装: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 科创50: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- 科创50ETF: `{'candidate_count': 2, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 2, 'sector_breadth_snapshot_missing': 2, 'snapshot_missing': 2}}`
- AI人工智能: `{'candidate_count': 1, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 专业工程: `{'candidate_count': 1, 'missing_reason_distribution': {'alias_or_group_unmatched': 1, 'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 其他电子: `{'candidate_count': 1, 'missing_reason_distribution': {'alias_or_group_unmatched': 1, 'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 医疗: `{'candidate_count': 1, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 工程咨询服务: `{'candidate_count': 1, 'missing_reason_distribution': {'alias_or_group_unmatched': 1, 'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 电网设备: `{'candidate_count': 1, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 通信终端及配件: `{'candidate_count': 1, 'missing_reason_distribution': {'alias_or_group_unmatched': 1, 'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 通信网络设备及器件: `{'candidate_count': 1, 'missing_reason_distribution': {'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`
- 集成电路封测: `{'candidate_count': 1, 'missing_reason_distribution': {'alias_or_group_unmatched': 1, 'leading_cluster_snapshot_missing': 1, 'sector_breadth_snapshot_missing': 1, 'snapshot_missing': 1}}`

## Snapshot Availability

- 20260622: ifind_dir_exists=False, snapshot_missing=True
- 20260623: ifind_dir_exists=False, snapshot_missing=True
- 20260624: ifind_dir_exists=False, snapshot_missing=True
- 20260625: ifind_dir_exists=False, snapshot_missing=True
- 20260626: ifind_dir_exists=False, snapshot_missing=True
