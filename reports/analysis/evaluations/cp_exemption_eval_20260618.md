# CP Exemption Eval 20260618

- cp_total: `11`
- real_snapshot_missing: `True`

## Decision Distribution

| decision | count | success_count | success_rate | avg_body_pct |
|---|---:|---:|---:|---:|
| crowded_observe | 1 | 1 | 100.00% | -3.6956 |
| hard_trap | 10 | 0 | 0.00% | +5.3908 |

## Notes

- 20260618 validation remains pending real market-structure snapshot when ifind dir is absent.

## Examples: crowded_observe

```json
[
  {
    "code": "688110.SH",
    "name": "东芯股份",
    "target_type": "stock",
    "group": "数字芯片设计",
    "theme_cluster": "数字芯片设计",
    "cp": 12.1,
    "auction_pct": 5.9673,
    "body_pct": -3.6956,
    "market_regime": "risk_off",
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
    "validation_success": true
  }
]
```

## Examples: hard_trap

```json
[
  {
    "code": "000688.SH",
    "name": "科创50",
    "target_type": "index",
    "group": "",
    "theme_cluster": "科创50",
    "cp": 72.7,
    "auction_pct": -0.2038,
    "body_pct": 4.044,
    "market_regime": "risk_off",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
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
    "cp": 84.5,
    "auction_pct": -0.1257,
    "body_pct": 4.0637,
    "market_regime": "risk_off",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
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
    "cp": 73.1,
    "auction_pct": -0.2933,
    "body_pct": 2.6979,
    "market_regime": "risk_off",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "588000.SH",
    "name": "科创50ETF",
    "target_type": "etf",
    "group": "",
    "theme_cluster": "科创50ETF",
    "cp": 74.8,
    "auction_pct": -0.2063,
    "body_pct": 4.229,
    "market_regime": "risk_off",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "",
    "leading_cluster_strength": null,
    "leading_cluster_status": "missing_ifind_overlay",
    "leading_cluster_evidence": [],
    "cp_risk_reasons": [
      "high_cp_score",
      "hard_trap_conditions_met"
    ],
    "cp_risk_flags": [],
    "validation_success": false
  },
  {
    "code": "603986.SH",
    "name": "兆易创新",
    "target_type": "stock",
    "group": "数字芯片设计",
    "theme_cluster": "数字芯片设计",
    "cp": 171.5,
    "auction_pct": 2.2287,
    "body_pct": 6.0236,
    "market_regime": "risk_off",
    "cp_risk_decision": "hard_trap",
    "leading_cluster_name": "半导体",
    "leading_cluster_strength": 0.0,
    "leading_cluster_status": "stale_ifind_snapshot",
    "leading_cluster_evidence": [
      "ifind_theme_match",
      "ifind_catalyst_confirmed"
    ],
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
