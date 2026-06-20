# Leading Cluster Evidence Eval 20260616

- real_snapshot_missing: `False`
- full_snapshot_missing: `True`
- snapshot_status: `sector_breadth_ready`
- snapshot_present_files: `sector_strength_snapshot.csv`
- snapshot_missing_files: `theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- candidate_total: `139`
- market_structure_hit_rate: `2.88%`
- sector_strength_hit_rate: `2.88%`
- theme_diffusion_hit_rate: `0.00%`
- limitup_ladder_hit_rate: `0.00%`
- active_with_market_structure_count: `0`

## Notes

- 20260616 leading-cluster validation can use sector breadth evidence even though full ladder/theme diffusion files are incomplete.

## Status Distribution

| status | count |
|---|---:|
| missing_ifind_overlay | 127 |
| partial | 7 |
| stale_ifind_snapshot | 5 |

## Evidence Distribution

| evidence | count |
|---|---:|
| ifind_catalyst_confirmed | 3 |
| ifind_sector_strength_confirmed | 4 |
| ifind_theme_match | 5 |
| sector_limitup_breadth_confirmed | 4 |
| sector_money_flow_confirmed | 4 |

## Active Examples

```json
[]
```

## Partial Examples

```json
[
  {
    "code": "",
    "name": "数字芯片设计",
    "group": "",
    "theme_cluster": "数字芯片设计",
    "signal_category": "trap",
    "leading_cluster_status": "partial",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_code"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "",
    "name": "消费电子零部件及组装",
    "group": "",
    "theme_cluster": "消费电子零部件及组装",
    "signal_category": "trap",
    "leading_cluster_status": "partial",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_code"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "",
    "name": "印制电路板",
    "group": "",
    "theme_cluster": "印制电路板",
    "signal_category": "trend",
    "leading_cluster_status": "partial",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_code"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "",
    "name": "证券",
    "group": "",
    "theme_cluster": "证券",
    "signal_category": "trend",
    "leading_cluster_status": "partial",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_code"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "",
    "name": "贵金属",
    "group": "",
    "theme_cluster": "贵金属",
    "signal_category": "trend",
    "leading_cluster_status": "partial",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_code"
    ],
    "leading_cluster_risk_flags": []
  }
]
```

## Missing Examples

```json
[
  {
    "code": "000001.SH",
    "name": "上证",
    "group": "",
    "theme_cluster": "上证",
    "signal_category": "trend",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "399006.SZ",
    "name": "创业板",
    "group": "",
    "theme_cluster": "创业板",
    "signal_category": "trap",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "000688.SH",
    "name": "科创50",
    "group": "",
    "theme_cluster": "科创50",
    "signal_category": "trap",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "159516.SZ",
    "name": "半导体设备",
    "group": "",
    "theme_cluster": "半导体设备",
    "signal_category": "trap",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": []
  },
  {
    "code": "512480.SH",
    "name": "半导体",
    "group": "",
    "theme_cluster": "半导体",
    "signal_category": "trap",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": []
  }
]
```
