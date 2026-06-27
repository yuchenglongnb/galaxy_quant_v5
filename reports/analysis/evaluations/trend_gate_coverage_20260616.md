# Trend Gate Coverage Diagnosis 20260616

## 1. Core Status

- regime: `mixed`
- trend_total: `108`
- target_type_distribution: `{'index': 1, 'ETF': 1, 'stock': 101, 'industry': 5}`
- intraday_dir_exists: `True`
- confirmation_available: `True`
- confirmation_feature_timestamp: `935`
- signal_enriched_count: `60`
- benchmark_fallback_attached_count: `101`
- board_index_fallback_attached_count: `80`

## 2. Overall Coverage

| metric | value |
| --- | ---: |
| candidate_count | 108 |
| rs_vs_etf_coverage | 0.0 |
| rs_vs_index_coverage | 0.5556 |
| amount_1m_ratio_coverage | 0.5556 |
| benchmark_etf_coverage | 0.1759 |
| benchmark_index_coverage | 0.9352 |
| board_index_fallback_coverage | 0.5 |
| rs_vs_board_index_coverage | 0.1574 |
| mapped_benchmark_etf_potential | 0.1944 |
| mapped_benchmark_index_potential | 0.1944 |
| leading_cluster_active_count | 3 |
| sector_positive_evidence_count | 3 |
| board_index_codes_used | ['000001.SH', '000688.SH', '399001.SZ', '399006.SZ'] |
| shadow_distribution | {'observe': 77, 'drop': 30, 'main': 1} |

## 3. Coverage By Target Type

| target_type | count | rs_vs_etf | rs_vs_index | rs_vs_board_index | amount | benchmark_etf | benchmark_index | board_index_fallback | mapped_etf_potential | mapped_index_potential | leading_active | sector_positive | shadow_distribution |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| ETF | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | {'observe': 1} |
| index | 1 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 0 | {'observe': 1} |
| industry | 5 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.4000 | 0.4000 | 0 | 0 | {'observe': 5} |
| stock | 101 | 0.0000 | 0.5941 | 0.1683 | 0.5941 | 0.1881 | 1.0000 | 0.5347 | 0.1881 | 0.1881 | 3 | 3 | {'observe': 70, 'drop': 30, 'main': 1} |

## 4. Main Blocking Reasons

| blocker | count |
| --- | ---: |
| relative_strength_unverified | 78 |
| weak_vs_index | 30 |

## 5. Missing-Field Top Groups

| group | candidate_count | miss_rs_etf | miss_rs_index | miss_bench_etf | miss_bench_index | miss_amount | leading_missing | sector_positive_missing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 证券 | 7 | 7 | 1 | 0 | 0 | 1 | 6 | 7 |
| 垂直应用软件 | 6 | 6 | 4 | 6 | 0 | 4 | 6 | 6 |
| 贵金属 | 5 | 5 | 0 | 5 | 0 | 0 | 5 | 5 |
| 数字芯片设计 | 4 | 4 | 1 | 0 | 0 | 1 | 3 | 3 |
| 消费电子零部件及组装 | 4 | 4 | 2 | 0 | 0 | 2 | 3 | 3 |
| IT服务 | 3 | 3 | 3 | 3 | 0 | 3 | 3 | 3 |
| 广告营销 | 3 | 3 | 1 | 3 | 0 | 1 | 3 | 3 |
| 磷肥及磷化工 | 3 | 3 | 0 | 3 | 0 | 0 | 3 | 3 |
| 能源及重型设备 | 3 | 3 | 2 | 3 | 0 | 2 | 3 | 3 |
| 航运 | 3 | 3 | 2 | 3 | 0 | 2 | 3 | 3 |
| 印制电路板 | 3 | 3 | 0 | 0 | 0 | 0 | 2 | 2 |
| 其他电源设备 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 2 |
| 其他通用设备 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 2 |
| 军工电子 | 2 | 2 | 2 | 2 | 0 | 2 | 2 | 2 |
| 基础建设 | 2 | 2 | 1 | 2 | 0 | 1 | 2 | 2 |
| 工控设备 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 2 |
| 横向通用软件 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 2 |
| 稀土 | 2 | 2 | 2 | 2 | 0 | 2 | 2 | 2 |
| 航空装备 | 2 | 2 | 1 | 2 | 0 | 1 | 2 | 2 |
| 输变电设备 | 2 | 2 | 0 | 2 | 0 | 0 | 2 | 2 |

## Active Leading Cluster But Observe

- none

## Shadow Drop Samples

- 601138.SH | 工业富联 | type=stock | group=消费电子零部件及组装 | filter=observe | shadow=drop | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=-0.7158 | amt=1.0502 | bench_etf=159732.SZ | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 688256.SH | 寒武纪 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=半导体 (active, 74.0) | rs_etf=None | rs_index=-6.7803 | amt=0.6852 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 300059.SZ | 东方财富 | type=stock | group=证券 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-9.5797 | amt=0.5826 | bench_etf=512880.SH | bench_idx=000001.SH | source=group_benchmark_map | board_idx=- | blocker=weak_vs_index
- 688525.SH | 佰维存储 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-12.473 | amt=0.7896 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 601179.SH | 中国西电 | type=stock | group=输变电设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-1.377 | amt=0.6125 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 002436.SZ | 兴森科技 | type=stock | group=印制电路板 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-13.9979 | amt=1.389 | bench_etf=159732.SZ | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 603083.SH | 剑桥科技 | type=stock | group=通信终端及配件 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-15.8511 | amt=0.5587 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 688766.SH | 普冉股份 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-33.3415 | amt=0.53 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 688012.SH | 中微公司 | type=stock | group=半导体设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-13.9511 | amt=0.5887 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 600030.SH | 中信证券 | type=stock | group=证券 | filter=observe | shadow=drop | leading=金融科技 (stale_ifind_snapshot, 0.0) | rs_etf=None | rs_index=-5.0324 | amt=0.58 | bench_etf=512880.SH | bench_idx=000001.SH | source=group_benchmark_map | board_idx=- | blocker=weak_vs_index

## Benchmark Missing With Group

- 300308.SZ | 中际旭创 | type=stock | group=通信网络设备及器件 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=399006.SZ | source=board_index_fallback | board_idx=399006.SZ | blocker=relative_strength_unverified
- 600111.SH | 北方稀土 | type=stock | group=稀土 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=relative_strength_unverified
- 601179.SH | 中国西电 | type=stock | group=输变电设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-1.377 | amt=0.6125 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 601899.SH | 紫金矿业 | type=stock | group=贵金属 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=11.5082 | amt=0.6553 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=relative_strength_unverified
- 603083.SH | 剑桥科技 | type=stock | group=通信终端及配件 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-15.8511 | amt=0.5587 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 601872.SH | 招商轮船 | type=stock | group=航运 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=relative_strength_unverified
- 000630.SZ | 铜陵有色 | type=stock | group=铜 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=4.1505 | amt=0.8417 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=relative_strength_unverified
- 002466.SZ | 天齐锂业 | type=stock | group=锂 | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=399001.SZ | source=board_index_fallback | board_idx=399001.SZ | blocker=relative_strength_unverified
- 688012.SH | 中微公司 | type=stock | group=半导体设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-13.9511 | amt=0.5887 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 300475.SZ | 香农芯创 | type=stock | group=其他电子 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-27.6396 | amt=0.5583 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index

## Non-Stock Trend Candidates

- 000001.SH | 上证 | type=index | group=- | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- 515790.SH | 光伏 | type=ETF | group=- | filter=observe | shadow=observe | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- - | 印制电路板 | type=industry | group=印制电路板 | filter=observe | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- - | 证券 | type=industry | group=证券 | filter=observe | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- - | 贵金属 | type=industry | group=贵金属 | filter=observe | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- - | 垂直应用软件 | type=industry | group=垂直应用软件 | filter=observe | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified
- - | IT服务 | type=industry | group=IT服务 | filter=observe | shadow=observe | leading=- (partial, None) | rs_etf=None | rs_index=None | amt=None | bench_etf=- | bench_idx=- | source=- | board_idx=- | blocker=relative_strength_unverified

## Mismatch Examples

- 601138.SH | 工业富联 | type=stock | group=消费电子零部件及组装 | filter=observe | shadow=drop | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=-0.7158 | amt=1.0502 | bench_etf=159732.SZ | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 300476.SZ | 胜宏科技 | type=stock | group=印制电路板 | filter=observe | shadow=main | leading=AI硬件 (active, 100.0) | rs_etf=None | rs_index=3.0645 | amt=1.2434 | bench_etf=159732.SZ | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=relative_strength_unverified
- 688256.SH | 寒武纪 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=半导体 (active, 74.0) | rs_etf=None | rs_index=-6.7803 | amt=0.6852 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 300059.SZ | 东方财富 | type=stock | group=证券 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-9.5797 | amt=0.5826 | bench_etf=512880.SH | bench_idx=000001.SH | source=group_benchmark_map | board_idx=- | blocker=weak_vs_index
- 688525.SH | 佰维存储 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-12.473 | amt=0.7896 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 601179.SH | 中国西电 | type=stock | group=输变电设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-1.377 | amt=0.6125 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 002436.SZ | 兴森科技 | type=stock | group=印制电路板 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-13.9979 | amt=1.389 | bench_etf=159732.SZ | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 603083.SH | 剑桥科技 | type=stock | group=通信终端及配件 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-15.8511 | amt=0.5587 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 688766.SH | 普冉股份 | type=stock | group=数字芯片设计 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-33.3415 | amt=0.53 | bench_etf=512480.SH | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 688012.SH | 中微公司 | type=stock | group=半导体设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-13.9511 | amt=0.5887 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 600030.SH | 中信证券 | type=stock | group=证券 | filter=observe | shadow=drop | leading=金融科技 (stale_ifind_snapshot, 0.0) | rs_etf=None | rs_index=-5.0324 | amt=0.58 | bench_etf=512880.SH | bench_idx=000001.SH | source=group_benchmark_map | board_idx=- | blocker=weak_vs_index
- 300475.SZ | 香农芯创 | type=stock | group=其他电子 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-27.6396 | amt=0.5583 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 600026.SH | 中远海能 | type=stock | group=航运 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-8.3976 | amt=0.7484 | bench_etf=- | bench_idx=000001.SH | source=board_index_fallback | board_idx=000001.SH | blocker=weak_vs_index
- 300870.SZ | 欧陆通 | type=stock | group=其他电源设备 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-6.9099 | amt=1.1665 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index
- 300803.SZ | 指南针 | type=stock | group=垂直应用软件 | filter=observe | shadow=drop | leading=- (missing_ifind_overlay, None) | rs_etf=None | rs_index=-8.1688 | amt=0.654 | bench_etf=- | bench_idx=000001.SH | source=default_index_fallback | board_idx=- | blocker=weak_vs_index