# 因子设计与验证框架

本文档整合 CP/SA/趋势信号设计、验证口径和因子快照表。

## 1. 核心思想

竞价信号不是直接预测全天涨跌，而是判断开盘后资金是否继续承接。

因此当前验证重点使用实体涨跌幅：

```text
body_pct = (close - open) / prev_close * 100
```

如果开盘很强但收盘相对开盘走弱，说明竞价后的承接不足；如果低开或平开后实体为正，说明盘中有修复或趋势延续。

## 2. 信号分类

| 类型 | 机器分类 | 含义 | 成功定义 |
|---|---|---|---|
| CP风险 | `trap` | 高开诱多、强势后兑现、拥挤兑现风险 | `body_pct < 0` |
| 反核机会 | `reversal` | 低开后承接修复 | `body_pct > 0` |
| 趋势机会 | `trend` | 强趋势延续 | `body_pct > 0` |

## 3. CP 风险

CP 用于刻画拥挤兑现风险。

主要输入：

```text
auction_pct
prev_pct
prev_body_pct
prev_vol_ratio
pos_5d
amt_rank
market_oar
```

典型场景：

- 高位高开但后续承接不足。
- 昨日强势后今日平开/弱开，资金开始兑现。
- 板块或个股短线过热，竞价阶段已经消耗买盘。

## 4. SA 反核

SA 用于刻画低开承接机会。

主要输入：

```text
auction_pct
auction_amount
amt_rank
pos_5d
prev_pct
prev_body_pct
market_oar
```

典型场景：

- 个股或板块低开，但竞价额不弱。
- 前一日恐慌或调整后，今日出现承接。
- 市场环境不是极端恶劣。

## 5. 趋势机会

趋势机会和反核不同。

反核强调“低开后修复”，趋势强调“已有强度继续延续”。

后续应重点增加：

- ETF 同向强度。
- 概念热度。
- 个股成交额排名。
- 历史趋势信号成功率。

## 6. 验证文件

```text
reports/validation/
  auction_signal_validation.csv
  auction_signal_daily_summary.csv
  auction_signal_metrics.csv
  daily/YYYYMMDD/
    signal_detail.csv
    signal_summary.csv
    signal_metrics.csv
    factor_snapshot_index.csv
    factor_snapshot_etf.csv
    factor_snapshot_stock.csv
    factor_snapshot_industry_topk.csv
```

## 7. 表格职责

### signal_detail.csv

只记录触发信号的样本。

用途：

- 人工复盘。
- 统计成功和失败。
- 回看具体失败样本。

### signal_metrics.csv

每天固定记录三类信号，即使某类没有触发也保留一行。

用途：

- 画胜率曲线。
- 判断某类信号是否阶段性失效。
- 分析不同市场阶段下的表现。

### factor_snapshot_*.csv

记录完整因子快照，包括未触发信号的样本。

用途：

- 重新评估 CP/SA 阈值。
- 查找“没触发但表现明显”的漏检样本。
- 分析指数、ETF、个股、板块之间的共振。

## 8. 快照核心字段

```text
date
universe_type
code
name
group
rank
is_topk
prev2_pct
prev1_pct
prev_body_pct
prev_vol_ratio
prev_close
open
high
low
close
auction_pct
close_pct
body_pct
amount
auction_amount
volume
turnover_rate
vol_ratio
oar
amount_rank
pos_5d
trend_state
stock_count
cp
sa
cp_triggered
sa_triggered
trend_triggered
signal_category
signal_family
signal_label
scenario
validation_rule
validation_success
validation_result
```

## 9. 推荐调参方法

CP 优化：

- 看 `cp` 高但失败的样本，判断是否误伤强趋势。
- 看 `cp` 低但实体大跌的样本，判断阈值是否过高。
- 按 `pos_5d`、`amount_rank`、`market_oar` 分层。

SA 优化：

- 看低开后实体为正样本，判断 SA 阈值是否漏掉承接。
- 按市场环境和 ETF 背景分层。

趋势优化：

- 看趋势成功样本是否集中于高成交排名。
- 看 ETF/概念共振是否显著提高胜率。

