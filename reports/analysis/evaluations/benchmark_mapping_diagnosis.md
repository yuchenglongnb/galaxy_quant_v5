# Benchmark Mapping Diagnosis

## 1. Diagnosis Scope

- start: `20260608`
- end: `20260609`
- days_scanned: `2`
- mapping_file: `watchlists\group_benchmark_map.csv`

## 2. Active Dates Summary

| date | raw_trend | confirmation_coverage | rs_vs_index_coverage | rs_vs_etf_coverage | benchmark_etf_mapping | benchmark_index_mapping |
| ---- | --------: | --------------------: | -------------------: | -----------------: | --------------------: | ----------------------: |
| 20260608 | 4 | 1.0000 | 1.0000 | 0.2500 | 0.2500 | 0.2500 |
| 20260609 | 14 | 0.9286 | 1.0000 | 0.3846 | 0.3846 | 0.3846 |

## 3. Unmapped Group Distribution

| group | trend_signal_count | dates | current_mapping | suggested_action | suggested_benchmark | confidence |
| ----- | -----------------: | ----- | --------------- | ---------------- | ------------------- | ---------- |
| IT服务 | 2 | 20260609 | - | manual_review | 159246.SZ | manual_required |
| 其他通用设备 | 2 | 20260609 | - | manual_review | - | manual_required |
| 其他自动化设备 | 1 | 20260609 | - | manual_review | - | manual_required |
| 其他计算机设备 | 1 | 20260608 | - | manual_review | 159246.SZ | manual_required |
| 军工电子 | 1 | 20260609 | - | manual_review | 159206.SZ | manual_required |
| 原料药 | 1 | 20260608 | - | manual_review | 512170.SH | medium |
| 垂直应用软件 | 1 | 20260609 | - | manual_review | 159246.SZ | manual_required |
| 工控设备 | 1 | 20260609 | - | manual_review | - | manual_required |
| 金属制品 | 1 | 20260608 | - | manual_review | - | manual_required |

## 4. Unmapped Theme Cluster Distribution

| theme_cluster | trend_signal_count | dates | current_mapping | suggested_action |
| ------------- | -----------------: | ----- | --------------- | ---------------- |
| - | 0 | - | - | - |

## 5. Top Mapping Gaps

- IT服务 | count=2 | dates=20260609 | suggested=159246.SZ | confidence=manual_required
- 其他通用设备 | count=2 | dates=20260609 | suggested=manual_review | confidence=manual_required
- 其他自动化设备 | count=1 | dates=20260609 | suggested=manual_review | confidence=manual_required
- 其他计算机设备 | count=1 | dates=20260608 | suggested=159246.SZ | confidence=manual_required
- 军工电子 | count=1 | dates=20260609 | suggested=159206.SZ | confidence=manual_required
- 原料药 | count=1 | dates=20260608 | suggested=512170.SH | confidence=medium
- 垂直应用软件 | count=1 | dates=20260609 | suggested=159246.SZ | confidence=manual_required
- 工控设备 | count=1 | dates=20260609 | suggested=manual_review | confidence=manual_required
- 金属制品 | count=1 | dates=20260608 | suggested=manual_review | confidence=manual_required

## 6. Recommended Minimal Fixes

- 低置信 group 保持 manual review，不为追求 coverage 统一映射到宽基 ETF。