# Intraday Confirmation Expansion 20260616

| max_stocks | selection_priority | signal_enriched_count | rs_vs_index_coverage | amount_1m_ratio_coverage | rs_vs_etf_coverage | shadow_distribution | slow_batches | failed_batches |
| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| 30 | leading_cluster | 10 | 0.0926 | 0.0926 | 0.0000 | {'observe': 102, 'drop': 6} | 0 | 0 |
| 60 | leading_cluster | 60 | 0.5556 | 0.5556 | 0.0000 | {'observe': 77, 'drop': 30, 'main': 1} | 0 | 0 |

- conclusion: `confirmation coverage is improving under isolated-query replay; active mode remains disabled until rs/index and amount coverage lift further.`