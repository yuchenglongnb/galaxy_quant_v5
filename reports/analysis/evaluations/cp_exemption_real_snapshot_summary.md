# CP Exemption Real Snapshot Summary

| date | real_snapshot | snapshot_status | cp_total | hard_trap | crowded_observe | leading_cluster_exempt | pending_validation | notes |
|---|---|---|---:|---:|---:|---:|---|---|
| 20260616 | False | sector_only_partial | 23 | 19 | 4 | 0 | True | 20260616 only has basic sector strength snapshot; breadth or money-flow fields are still missing for strong replay validation. |
| 20260618 | False | missing | 11 | 10 | 1 | 0 | True | 20260618 validation remains pending: ifind market-structure directory is missing. |
| 20260609 | False | missing | 1 | 0 | 1 | 0 | True | 20260609 validation remains pending: ifind market-structure directory is missing. |
| 20260608 | False | missing | 0 | 0 | 0 | 0 | True | 20260608 validation remains pending: ifind market-structure directory is missing. |

## Detail

### 20260616

- snapshot_status: `sector_only_partial`
- snapshot_missing_files: `theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- hard_success_rate: `26.32%`
- crowded_success_rate: `0.00%`
- exempt_success_rate: `0.00%`
- leading_cluster_market_structure_hit_rate: `0.00%`

### 20260618

- snapshot_status: `missing`
- snapshot_missing_files: `sector_strength_snapshot.csv, theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- hard_success_rate: `0.00%`
- crowded_success_rate: `100.00%`
- exempt_success_rate: `0.00%`
- leading_cluster_market_structure_hit_rate: `0.00%`

### 20260609

- snapshot_status: `missing`
- snapshot_missing_files: `sector_strength_snapshot.csv, theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- hard_success_rate: `0.00%`
- crowded_success_rate: `0.00%`
- exempt_success_rate: `0.00%`
- leading_cluster_market_structure_hit_rate: `0.00%`

### 20260608

- snapshot_status: `missing`
- snapshot_missing_files: `sector_strength_snapshot.csv, theme_limitup_distribution.csv, limitup_ladder_snapshot.csv`
- hard_success_rate: `0.00%`
- crowded_success_rate: `0.00%`
- exempt_success_rate: `0.00%`
- leading_cluster_market_structure_hit_rate: `0.00%`

