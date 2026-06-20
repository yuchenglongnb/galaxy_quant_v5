# Trend Gate Coverage Diagnosis 20260616

## 1. Core Status

- regime: `mixed`
- trend_total: `108`
- target_type_distribution: `{'index': 1, 'ETF': 1, 'stock': 101, 'industry': 5}`
- intraday_dir_exists: `False`
- confirmation_available: `False`
- confirmation_feature_timestamp: `None`
- signal_enriched_count: `0`
- benchmark_fallback_attached_count: `19`

## 2. Overall Coverage

| metric | value |
| --- | ---: |
| candidate_count | 108 |
| rs_vs_etf_coverage | 0.0 |
| rs_vs_index_coverage | 0.0 |
| amount_1m_ratio_coverage | 0.0 |
| benchmark_etf_coverage | 0.1759 |
| benchmark_index_coverage | 0.1759 |
| mapped_benchmark_etf_potential | 0.1944 |
| mapped_benchmark_index_potential | 0.1944 |
| leading_cluster_active_count | 3 |
| sector_positive_evidence_count | 3 |
| shadow_distribution | {'observe': 107, 'drop': 1} |

## 3. Coverage By Target Type

| target_type | count | rs_vs_etf | rs_vs_index | amount | benchmark_etf | benchmark_index | mapped_etf_potential | mapped_index_potential | leading_active | sector_positive | shadow_distribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ETF | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | {'observe': 1} |
| index | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | {'observe': 1} |
| industry | 5 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.4000 | 0.4000 | 0 | 0 | {'observe': 5} |
| stock | 101 | 0.0000 | 0.0000 | 0.0000 | 0.1881 | 0.1881 | 0.1881 | 0.1881 | 3 | 3 | {'observe': 100, 'drop': 1} |

## 4. Main Blocking Reasons

| blocker | count |
| --- | ---: |
| relative_strength_unverified | 108 |

## 5. Missing-Field Top Groups

| group | candidate_count | miss_rs_etf | miss_rs_index | miss_bench_etf | miss_bench_index | miss_amount | leading_missing | sector_positive_missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 证券 | 7 | 7 | 7 | 0 | 0 | 7 | 6 | 7 |
| 垂直应用软件 | 6 | 6 | 6 | 6 | 6 | 6 | 6 | 6 |
| 贵金属 | 5 | 5 | 5 | 5 | 5 | 5 | 5 | 5 |
| 数字芯片设计 | 4 | 4 | 4 | 0 | 0 | 4 | 3 | 3 |
| 消费电子零部件及组装 | 4 | 4 | 4 | 0 | 0 | 4 | 3 | 3 |
| IT服务 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| 广告营销 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| 磷肥及磷化工 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| 能源及重型设备 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| 航运 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| 印制电路板 | 3 | 3 | 3 | 0 | 0 | 3 | 2 | 2 |
| 其他电源设备 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 其他通用设备 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 军工电子 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 基础建设 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 工控设备 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 横向通用软件 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 稀土 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 航空装备 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| 输变电设备 | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |

## Active Leading Cluster But Observe

- 601138.SH | 工业富联 | type=stock | group=消费电子零部件及组装 | filter=keep | shadow=observe | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=159732.SZ | bench_idx=399006.SZ | blocker=relative_strength_unverified
- 300476.SZ | 胜宏科技 | type=stock | group=印制电路板 | filter=keep | shadow=observe | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=159732.SZ | bench_idx=399006.SZ | blocker=relative_strength_unverified
- 688256.SH | 寒武纪 | type=stock | group=数字芯片设计 | filter=keep | shadow=observe | leading=半导体 (active, 74.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=512480.SH | bench_idx=000688.SH | blocker=relative_strength_unverified

## Shadow Drop Samples

- 600030.SH | 中信证券 | type=stock | group=证券 | filter=keep | shadow=drop | leading=金融科技 (stale_ifind_snapshot, 0.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=512880.SH | bench_idx=000001.SH | blocker=relative_strength_unverified

## Benchmark Missing With Group

- 300308.SZ | 中际旭创 | type=stock | group=通信网络设备及器件 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 600111.SH | 北方稀土 | type=stock | group=稀土 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 601179.SH | 中国西电 | type=stock | group=输变电设备 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 601899.SH | 紫金矿业 | type=stock | group=贵金属 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 603083.SH | 剑桥科技 | type=stock | group=通信终端及配件 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 601872.SH | 招商轮船 | type=stock | group=航运 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 000630.SZ | 铜陵有色 | type=stock | group=铜 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 002466.SZ | 天齐锂业 | type=stock | group=锂 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 688012.SH | 中微公司 | type=stock | group=半导体设备 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 300475.SZ | 香农芯创 | type=stock | group=其他电子 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified

## Non-Stock Trend Candidates

- 000001.SH | 上证 | type=index | group=- | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 515790.SH | 光伏 | type=ETF | group=- | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- - | 印制电路板 | type=industry | group=印制电路板 | filter=keep | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- - | 证券 | type=industry | group=证券 | filter=keep | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- - | 贵金属 | type=industry | group=贵金属 | filter=keep | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- - | 垂直应用软件 | type=industry | group=垂直应用软件 | filter=keep | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- - | IT服务 | type=industry | group=IT服务 | filter=keep | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified

## Mismatch Examples

- 000001.SH | 上证 | type=index | group=- | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 515790.SH | 光伏 | type=ETF | group=- | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 300308.SZ | 中际旭创 | type=stock | group=通信网络设备及器件 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 600111.SH | 北方稀土 | type=stock | group=稀土 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 601138.SH | 工业富联 | type=stock | group=消费电子零部件及组装 | filter=keep | shadow=observe | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=159732.SZ | bench_idx=399006.SZ | blocker=relative_strength_unverified
- 300476.SZ | 胜宏科技 | type=stock | group=印制电路板 | filter=keep | shadow=observe | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=159732.SZ | bench_idx=399006.SZ | blocker=relative_strength_unverified
- 688256.SH | 寒武纪 | type=stock | group=数字芯片设计 | filter=keep | shadow=observe | leading=半导体 (active, 74.0) | rs_etf=None | rs_index=None | amt=None | bench_etf=512480.SH | bench_idx=000688.SH | blocker=relative_strength_unverified
- 300059.SZ | 东方财富 | type=stock | group=证券 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=512880.SH | bench_idx=000001.SH | blocker=relative_strength_unverified
- 688525.SH | 佰维存储 | type=stock | group=数字芯片设计 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=512480.SH | bench_idx=000688.SH | blocker=relative_strength_unverified
- 601179.SH | 中国西电 | type=stock | group=输变电设备 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 002436.SZ | 兴森科技 | type=stock | group=印制电路板 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=159732.SZ | bench_idx=399006.SZ | blocker=relative_strength_unverified
- 601899.SH | 紫金矿业 | type=stock | group=贵金属 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 603083.SH | 剑桥科技 | type=stock | group=通信终端及配件 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 601872.SH | 招商轮船 | type=stock | group=航运 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified
- 000630.SZ | 铜陵有色 | type=stock | group=铜 | filter=keep | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | blocker=relative_strength_unverified