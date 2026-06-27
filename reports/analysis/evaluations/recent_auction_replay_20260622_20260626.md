# Recent Auction Replay: 20260622-20260626

## Data Status

- Sync command: `python main.py sync 5 --force`
- Synced dates: `20260622`, `20260623`, `20260624`, `20260625`, `20260626`
- Latest closed cache: `20260626`
- `20260626` cache rows: `stocks=198`, `indices=31`
- Post-close validation: allowed

## Auction Validation

| date | regime | environment | leading clusters | trap | reversal | trend |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 20260622 | mixed | mixed_wait_confirmation | 数字芯片设计, 证券, 贵金属, 垂直应用软件, IT服务 | 1/17 (5.88%) | 8/8 (100.00%) | 26/48 (54.17%) |
| 20260623 | risk_off | selective_reversal_only | 数字芯片设计, 证券, 垂直应用软件 | 14/14 (100.00%) | 2/8 (25.00%) | 18/66 (27.27%) |
| 20260624 | risk_off | selective_reversal_only | 数字芯片设计, 消费电子零部件及组装, 印制电路板, 贵金属, IT服务 | 0/1 (0.00%) | 19/20 (95.00%) | 13/23 (56.52%) |
| 20260625 | mixed | mixed_wait_confirmation | 数字芯片设计, 消费电子零部件及组装, 印制电路板, 证券 | 0/14 (0.00%) | 12/16 (75.00%) | 13/24 (54.17%) |
| 20260626 | risk_off | selective_reversal_only | 数字芯片设计, 军工电子 | 0/0 (0.00%) | 5/23 (21.74%) | 11/28 (39.29%) |

## Post-Close Review

`20260626` panoramic review says broad environment is bad, but structural environment remains selective. Stronger clusters were:

- 航天装备
- 工程咨询服务
- 半导体设备
- 风电整机
- 军工电子

This means the next auction should not read the tape as pure broad capitulation. The better framing is: broad risk is high, but watch whether a small number of structural clusters continue or fail.

## T+1 Backtest

Default actionable-only backtest produced only one executable sample:

- Output: `reports/t1_backtest/20260622_20260622/open_proxy`
- Reason: `20260623-20260626` currently have no `actionable=true` samples under the active shortlist filters.

All-candidate diagnostic backtest:

- Output: `reports/t1_backtest/20260622_20260626/open_proxy`

| signal | universe | trades | avg T+1 open return | T+1 open win rate | avg T+1 close return | T+1 close win rate |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| reversal | ETF | 42 | 0.2758% | 64.2857% | 0.0414% | 54.7619% |
| reversal | stock | 1 | 14.2032% | 100.0000% | 19.2921% | 100.0000% |
| trend | ETF | 9 | -2.0827% | 22.2222% | -0.8422% | 33.3333% |
| trend | stock | 146 | -0.7008% | 41.7808% | 0.0547% | 45.2055% |

## Analyst Judgment

1. `20260622` was a broad repair day. Reversal worked extremely well, while CP was mostly a false positive because leading clusters continued to absorb.
2. `20260623` was the opposite regime: profit-taking and risk-off dominated. CP was clean, while reversal and trend were weak.
3. `20260624-20260625` were structural repair days. CP again failed as a mechanical avoidance rule, especially around chip and consumer-electronics clusters.
4. `20260626` rolled back into risk-off. Reversal and trend both weakened, but post-close structure still identified a narrow set of clusters worth monitoring.
5. The T+1 diagnostic does not support opening trend active mode yet. Trend stock candidates still need better `09:35` confirmation coverage before being promoted from observation into execution.

## Open Issues

- Multi-day auction replay should remain sequential because root validation CSVs are shared write targets.
- Default actionable-only T+1 backtest is narrow for `20260623-20260626`; this is a shortlist-coverage issue, not a file-writing bug.
- Trend confirmation remains under-covered. Continue expanding isolated-query `09:35` confirmation before enabling active trend gates.
- CP false positives on structural repair days should continue to be explained through leading-cluster evidence, sector breadth, and prior-day context rather than by loosening CP thresholds immediately.

## Next Steps

- Continue `PriorDayContext P1B`: stock-only multi-day validation.
- Expand `09:35` confirmation coverage with isolated-query backfill.
- Compare CP exemption and trend confirmation across `20260622-20260626` to separate true risk-off CP from leading-cluster repair exemptions.
