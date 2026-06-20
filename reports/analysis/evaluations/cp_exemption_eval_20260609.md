# CP Exemption Eval 20260609

- cp_total: `1`
- real_snapshot_missing: `True`
- snapshot_status: `missing`
- snapshot_present_files: `none`
- snapshot_missing_files: `sector_strength_snapshot.csv, theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`

## Decision Distribution

| decision | count | success_count | success_rate | avg_body_pct |
|---|---:|---:|---:|---:|
| crowded_observe | 1 | 0 | 0.00% | +2.2555 |

## Notes

- 20260609 validation remains pending: ifind market-structure directory is missing.

## Examples: crowded_observe

```json
[
  {
    "code": "002463.SZ",
    "name": "沪电股份",
    "target_type": "stock",
    "group": "印制电路板",
    "theme_cluster": "印制电路板",
    "cp": 98.5,
    "auction_pct": 0.7299,
    "body_pct": 2.2555,
    "market_regime": "strong_repair",
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
  }
]
```
