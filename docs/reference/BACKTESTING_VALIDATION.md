# 回测与验证框架

本文档说明竞价信号验证、因子快照和后续调参分析的设计。

## 1. 目标

回测验证层的目标不是立刻形成完整交易系统，而是先把每天的信号和事实沉淀成可分析样本。

需要回答的问题：

- CP 风险信号触发后，实体是否为负？
- 反核机会触发后，实体是否为正？
- 趋势机会触发后，实体是否为正？
- 哪些阈值过松，哪些阈值过紧？
- ETF、指数、个股、板块之间是否存在共振？
- 未触发信号但表现明显的样本有什么共同特征？

## 2. 当前验证分类

| 中文类型 | 机器类型 | 当前规则 | 成功定义 |
|---|---|---|---|
| CP风险 | `trap` | 高开诱多、强势后兑现、拥挤兑现风险 | `body_pct < 0` |
| 反核机会 | `reversal` | 低开后承接修复 | `body_pct > 0` |
| 趋势机会 | `trend` | 强趋势延续 | `body_pct > 0` |

实体涨跌幅定义：

```text
body_pct = (close - open) / prev_close * 100
```

这个口径比单纯 `close_pct` 更适合验证竞价判断，因为它衡量的是“开盘以后市场如何投票”。

## 3. 文件结构

```text
reports/validation/
  auction_signal_validation.csv       # 跨日期信号明细总表
  auction_signal_daily_summary.csv    # 跨日期按类型/标的分组汇总
  auction_signal_metrics.csv          # 跨日期三类信号胜率总表
  daily/YYYYMMDD/
    signal_detail.csv                 # 当日触发信号明细
    signal_summary.csv                # 当日按类型和标的类型汇总
    signal_metrics.csv                # 当日 CP/反核/趋势三类胜率
    factor_snapshot_index.csv         # 指数全量因子快照
    factor_snapshot_etf.csv           # ETF 全量因子快照
    factor_snapshot_stock.csv         # 自选股全量因子快照
    factor_snapshot_industry_topk.csv # 板块 TopK 因子快照
```

## 4. 表格职责

### 4.1 signal_detail.csv

只记录当天真正触发的信号。

适合用于：

- 人工复盘。
- 统计每个信号的成败。
- 回看具体失败样本。

核心字段：

```text
date
signal_category
signal_family
signal_order
signal_label
target_type
target_order
name
scenario
trigger_reason
cp
sa
auction_pct
close_pct
body_pct
prev_pct
prev_body_pct
prev_vol_ratio
vol_ratio
pos_5d
amt_rank
validation_rule
validation_success
validation_result
log_path
```

### 4.2 signal_metrics.csv

每天固定记录三类信号，即使当天没有触发，也会保留 `trigger_count=0` 的行。

适合用于：

- 画每日胜率曲线。
- 观察某类信号是否阶段性失效。
- 比较不同市场环境下的表现。

字段：

```text
date
signal_family
signal_category
validation_rule
trigger_count
success_count
failure_count
success_rate
avg_body_pct
median_body_pct
avg_auction_pct
avg_close_pct
avg_cp
max_cp
avg_sa
max_sa
signal_order
```

### 4.3 factor_snapshot_*.csv

记录当天完整因子快照，包括未触发信号的样本。

这是后续调参最重要的数据，因为只看触发样本会有幸存者偏差。

统一字段：

```text
date
universe_type
code
name
group
rank
is_topk
source
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

## 5. 标的范围

### 5.1 指数

文件：

```text
factor_snapshot_index.csv
```

记录四大指数：

- 上证
- 创业板
- 科创50
- 北证50

用途：

- 判断市场环境。
- 判断 CP/SA 信号是否和指数环境共振。
- 后续可作为模型的市场状态特征。

### 5.2 ETF

文件：

```text
factor_snapshot_etf.csv
```

记录配置中的主题 ETF 和宽基 ETF。

用途：

- 替代粗粒度行业指数，表达市场真实资金偏好。
- 判断个股信号是否处在同方向 ETF 强弱背景中。

### 5.3 自选股

文件：

```text
factor_snapshot_stock.csv
```

记录股票池全量，不只记录 TopK。

用途：

- 对比触发和未触发样本。
- 优化 CP/SA 阈值。
- 找出接近阈值但表现明显的股票。
- 分析不同概念、不同 5 日位置、不同竞价额排名下的表现。

### 5.4 板块

文件：

```text
factor_snapshot_industry_topk.csv
```

板块只记录每日 TopK。

原因：

- 板块聚合更适合观察主线方向，不需要保留过多低流动性噪声。
- 当前股票池较小，板块聚合更多作为辅助解释。

## 6. 推荐分析方法

### 6.1 CP 风险优化

重点看：

```text
cp
auction_pct
prev_body_pct
prev_vol_ratio
pos_5d
amount_rank
body_pct
```

常见分析：

- CP 高但失败的样本：是不是强趋势主升，而不是诱多？
- CP 低但实体大跌的样本：是不是阈值太高？
- 高位 `pos_5d > 80` 和低位 `pos_5d < 30` 是否应该使用不同阈值？

### 6.2 反核机会优化

重点看：

```text
sa
auction_pct
prev_pct
prev_body_pct
pos_5d
oar
body_pct
```

常见分析：

- 低开后实体为正的样本是否集中在市场 OAR 平量或放量环境？
- 弱市中 SA 阈值是否需要提高？
- 反核成功是否依赖 ETF/指数环境共振？

### 6.3 趋势机会优化

重点看：

```text
trend_state
prev1_pct
prev_body_pct
auction_pct
close_pct
body_pct
amount_rank
pos_5d
```

常见分析：

- 趋势成功是否集中在成交额排名靠前的标的？
- 昨日强实体后，今日平开/小高开是否更容易延续？
- 哪些主题 ETF 强势时，个股趋势胜率更高？

## 7. 后续扩展

建议下一步增加：

- `concepts` 字段：同花顺有效概念标签。
- `etf_context` 字段：个股所属主题 ETF 的当天强弱。
- `market_regime` 字段：市场环境，如恶劣、震荡、强势。
- `next_day_pct` 字段：次日延续性验证。
- `max_intraday_drawdown_pct` 字段：盘中最大回撤。
- `max_intraday_gain_pct` 字段：盘中最大上冲。

这些字段可以把验证从“当天开盘到收盘”扩展到“交易路径质量”和“次日延续性”。

