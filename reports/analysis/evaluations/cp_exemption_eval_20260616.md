# CP Exemption Eval 20260616

- cp_total: `23`
- real_snapshot_missing: `False`

## Decision Distribution

| decision | count | success_count | success_rate | avg_body_pct |
|---|---:|---:|---:|---:|
| crowded_observe | 4 | 0 | 0.00% | +2.0867 |
| hard_trap | 19 | 5 | 26.32% | +0.6758 |

## Notes

- real market-structure snapshot detected for this date.

## Examples: crowded_observe

```json
[
  {
    "code": "561380.SH",
    "name": "电网设备",
    "target_type": "etf",
    "group": "",
    "theme_cluster": "电网设备",
    "cp": 88.1,
    "auction_pct": 0.1345,
    "body_pct": 3.4065,
    "market_regime": "mixed",
    "cp_risk_decision": "crowded_observe",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "crowded_observe_default",
      "no_strong_exempt_evidence"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "002428.SZ",
    "name": "云南锗业",
    "target_type": "stock",
    "group": "其他小金属",
    "theme_cluster": "其他小金属",
    "cp": 71.1,
    "auction_pct": 1.813,
    "body_pct": 3.3895,
    "market_regime": "mixed",
    "cp_risk_decision": "crowded_observe",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "crowded_observe_default",
      "no_strong_exempt_evidence"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "300489.SZ",
    "name": "光智科技",
    "target_type": "stock",
    "group": "光学元件",
    "theme_cluster": "光学元件",
    "cp": 39.3,
    "auction_pct": 7.2404,
    "body_pct": 0.8443,
    "market_regime": "mixed",
    "cp_risk_decision": "crowded_observe",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_open",
      "crowded_observe_default",
      "no_strong_exempt_evidence"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "",
    "name": "消费电子零部件及组装",
    "target_type": "industry",
    "group": "",
    "theme_cluster": "消费电子零部件及组装",
    "cp": 99.4,
    "auction_pct": 0.9088,
    "body_pct": 0.7063,
    "market_regime": "mixed",
    "cp_risk_decision": "crowded_observe",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "partial",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "crowded_observe_default",
      "partial_leading_cluster",
      "no_strong_exempt_evidence"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  }
]
```

## Examples: hard_trap

```json
[
  {
    "code": "399006.SZ",
    "name": "创业板",
    "target_type": "index",
    "group": "",
    "theme_cluster": "创业板",
    "cp": 149.1,
    "auction_pct": 0.7868,
    "body_pct": 1.7083,
    "market_regime": "mixed",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "very_high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "000688.SH",
    "name": "科创50",
    "target_type": "index",
    "group": "",
    "theme_cluster": "科创50",
    "cp": 140.9,
    "auction_pct": 0.1933,
    "body_pct": 0.5815,
    "market_regime": "mixed",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "very_high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "159516.SZ",
    "name": "半导体设备",
    "target_type": "etf",
    "group": "",
    "theme_cluster": "半导体设备",
    "cp": 133.3,
    "auction_pct": 0.2165,
    "body_pct": 0.5051,
    "market_regime": "mixed",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "very_high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "512480.SH",
    "name": "半导体",
    "target_type": "etf",
    "group": "",
    "theme_cluster": "半导体",
    "cp": 153.8,
    "auction_pct": 0.2689,
    "body_pct": 0.8965,
    "market_regime": "mixed",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "very_high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "159732.SZ",
    "name": "消费电子",
    "target_type": "etf",
    "group": "",
    "theme_cluster": "消费电子",
    "cp": 172.8,
    "auction_pct": 0.5019,
    "body_pct": 1.2547,
    "market_regime": "mixed",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "very_high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  }
]
```
