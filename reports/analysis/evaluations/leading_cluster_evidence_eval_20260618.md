# Leading Cluster Evidence Eval 20260618

- real_snapshot_missing: `True`
- snapshot_status: `missing`
- snapshot_present_files: `none`
- snapshot_missing_files: `sector_strength_snapshot.csv, theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- candidate_total: `71`
- market_structure_hit_rate: `0.00%`
- sector_strength_hit_rate: `0.00%`
- theme_diffusion_hit_rate: `0.00%`
- limitup_ladder_hit_rate: `0.00%`
- active_with_market_structure_count: `0`

## Notes

- 20260618 leading-cluster validation remains pending: ifind market-structure directory is missing.

## Status Distribution

| status | count |
|---|---:|
| missing_ifind_overlay | 63 |
| partial | 4 |
| stale_ifind_snapshot | 4 |

## Evidence Distribution

| evidence | count |
|---|---:|
| ifind_catalyst_confirmed | 2 |
| ifind_theme_match | 4 |

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
    "name": "消费电子零部件及组装",
    "group": "",
    "theme_cluster": "消费电子零部件及组装",
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
    "name": "印制电路板",
    "group": "",
    "theme_cluster": "印制电路板",
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
    "name": "军工电子",
    "group": "",
    "theme_cluster": "军工电子",
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
    "leading_cluster_risk_flags": [
      "ifind_snapshot_date_fallback"
    ]
  },
  {
    "code": "159516.SZ",
    "name": "半导体设备",
    "group": "",
    "theme_cluster": "半导体设备",
    "signal_category": "trend",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": [
      "ifind_snapshot_date_fallback"
    ]
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
    "leading_cluster_risk_flags": [
      "ifind_snapshot_date_fallback"
    ]
  },
  {
    "code": "159732.SZ",
    "name": "消费电子",
    "group": "",
    "theme_cluster": "消费电子",
    "signal_category": "trap",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": [
      "ifind_snapshot_date_fallback"
    ]
  },
  {
    "code": "159246.SZ",
    "name": "AI人工智能",
    "group": "",
    "theme_cluster": "AI人工智能",
    "signal_category": "trend",
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_evidence": [],
    "leading_cluster_missing_fields": [
      "missing_ifind_overlay"
    ],
    "leading_cluster_risk_flags": [
      "ifind_snapshot_date_fallback"
    ]
  }
]
```
