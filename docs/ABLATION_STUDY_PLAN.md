# 竞价策略消融实验方案

## 1. 实验目标

本方案用于回答三个问题：

1. 哪些特征真正提高 CP 风险、反核机会、趋势机会的识别质量？
2. 市场环境分层是否有效，是否应该改变候选阈值、评分权重或 TopK？
3. 不同 TopK 对命中率、覆盖率、可交易性和稳定性的影响是什么？

当前阶段只评估竞价短名单。分钟和盘中执行确认暂不纳入本轮消融：

```text
阶段 A：9:25 竞价短名单
  -> 仅使用竞价时点可见特征
```

盘后 `body_pct` 只作为标签，不允许进入候选生成、评分或排序。

## 2. 标签与实验单位

### 2.1 标签

| 信号类型 | 标签 | 成功条件 |
|---|---|---|
| CP 风险 | `trap` | `body_pct < 0` |
| 反核机会 | `reversal` | `body_pct > 0` |
| 趋势机会 | `trend` | `body_pct > 0` |

建议额外统计强标签：

| 信号类型 | 强成功条件 |
|---|---|
| CP 风险 | `body_pct <= -1.0` |
| 反核机会 | `body_pct >= +1.0` |
| 趋势机会 | `body_pct >= +1.0` |

### 2.2 实验单位

主实验单位是：

```text
date + signal_category + universe_type + code
```

结果必须分别统计：

```text
index
ETF
stock
industry
```

不能把指数、ETF、个股和行业样本直接混成一个胜率。

## 3. 核心指标

### 3.1 预测质量

| 指标 | 含义 |
|---|---|
| `avg_directed_body_pct` | 主指标。CP 使用 `-body_pct`，反核和趋势使用 `+body_pct`；越高越好 |
| `median_directed_body_pct` | 主指标。观察典型样本，降低极端值干扰 |
| `p25_directed_body_pct` / `p75_directed_body_pct` | 主指标。观察分布和尾部风险 |
| `direction_hit_rate` | 辅助指标。方向调整后的实体涨幅是否大于 0 |
| `strong_direction_hit_rate` | 辅助指标。方向调整后的实体涨幅是否至少达到 1% |
| `coverage` | 入选数量 / 原始候选数量 |
| `avg_body_pct` | CP 越低越好；反核和趋势越高越好 |
| `median_body_pct` | 降低极端样本干扰 |
| `p25_body_pct` / `p75_body_pct` | 查看分布稳定性 |

### 3.2 可交易性

| 指标 | 含义 |
|---|---|
| `selected_count_per_day` | 每日实际需要观察的数量 |
| `selected_count_p90` | 极端日期观察压力 |
| `amount_rank_median` | 流动性质量 |
| `auction_amount_median` | 竞价成交额质量 |
| `duplicate_group_ratio` | 短名单是否过度集中在单一板块 |

### 3.3 稳定性

| 指标 | 含义 |
|---|---|
| `daily_precision_std` | 每日胜率波动 |
| `weekly_precision` | 周度命中率 |
| `regime_precision` | 不同环境下的命中率 |
| `topk_overlap_ratio` | 不同参数版本短名单重合度 |

不要只看总胜率。总胜率提高但每日候选只有 1 条，或者样本集中在单周，结论都不可靠。

## 4. 数据范围与切分

### 4.1 当前可立即执行

历史竞价层使用：

```text
reports/validation/daily/YYYYMMDD/signal_detail.csv
reports/validation/daily/YYYYMMDD/factor_snapshot_index.csv
reports/validation/daily/YYYYMMDD/factor_snapshot_etf.csv
reports/validation/daily/YYYYMMDD/factor_snapshot_stock.csv
reports/validation/daily/YYYYMMDD/factor_snapshot_industry_topk.csv
```

当前已有 5 个交易日样本，只适合做流程验证和发现明显问题，不适合确定最终参数。

### 4.2 延期项：分钟层

分钟数据暂不参与当前竞价消融。后续需要时再使用：

```text
AmazingData_Store/YYYYMMDD/intraday/
  indices_1min.csv
  etf_1min.csv
  stocks_1min.csv
  stock_confirmation_history.csv
```

至少积累 20 个完整交易日，再评估 9:35 和 9:45 两个固定截面。

### 4.3 正式切分

推荐 walk-forward，不随机打乱日期：

```text
训练窗口：过去 40 至 60 个交易日
验证窗口：随后 10 个交易日
滚动步长：5 个交易日
最终观察：至少 4 个滚动窗口
```

所有阈值和权重只允许在训练窗口调整。

## 5. 基线版本

所有实验必须从同一个基线出发：

```text
B0 当前短名单
  原始 CP / SA / 趋势候选
  + 硬过滤
  + market_regime 环境加分
  + action_score 排序
  + 分 universe TopK
  + 每类最终 TopK
```

当前默认参数：

```text
ACTION_TOPK_INDEX = 2
ACTION_TOPK_ETF = 3
ACTION_TOPK_STOCK = 5
ACTION_TOPK_INDUSTRY = 3
ACTION_TOPK_PER_CATEGORY = 5
```

每个消融实验只修改一个变量组，其余保持 B0 不变。

## 6. 特征消融

### 6.1 竞价层特征组

| 实验编号 | 修改 | 目的 |
|---|---|---|
| `F00` | B0 全特征 | 基线 |
| `F01` | 去掉 `rank_bonus` | 判断流动性排名是否有效 |
| `F02` | 去掉 `auction_pct` 加分 | 判断竞价缺口是否被过度强调 |
| `F03` | 去掉 `pos_5d` | 判断高位拥挤度对 CP 是否有效 |
| `F04` | 去掉 `prev_pct` | 判断昨日涨跌是否对反核、趋势有效 |
| `F05` | 去掉 `prev_vol_ratio` | 判断昨日量能是否改善趋势筛选 |
| `F06` | 去掉所有环境加分 | 判断环境调整的净贡献 |
| `F07` | 只保留 `cp` / `sa` 主因子 | 衡量附加特征的整体价值 |
| `F08` | 只保留流动性和竞价缺口 | 判断主因子是否不可替代 |

输出必须按 `trap`、`reversal`、`trend` 分开。某个特征可能只改善一种信号，不能因为总体平均值下降就直接删除。

### 6.2 硬过滤消融

| 实验编号 | 修改 | 目的 |
|---|---|---|
| `H00` | B0 全过滤 | 基线 |
| `H01` | 不过滤 `extreme_auction_pct` | 检查极端竞价是否应保留观察 |
| `H02` | 股票排名阈值 `100 -> 50` | 提高流动性要求 |
| `H03` | 股票排名阈值 `100 -> 150` | 检查是否误删机会 |
| `H04` | 趋势最低竞价 `-0.5 -> 0.0` | 仅保留不弱开的趋势 |
| `H05` | 趋势最低竞价 `-0.5 -> -1.0` | 检查弱开趋势修复机会 |
| `H06` | 取消最低 `action_score` | 衡量阈值过滤贡献 |

### 6.3 延期项：分钟量价确认消融

本轮不执行。分钟数据积累后再单独建立实验：

| 实验编号 | 修改 | 目的 |
|---|---|---|
| `M00` | 仅使用 9:25 短名单 | 分钟层基线 |
| `M01` | 加 `rs_vs_index_pct` | 检查个股相对指数强弱 |
| `M02` | 加 `rs_vs_etf_pct` | 检查个股相对板块 ETF 强弱 |
| `M03` | 加 `amount_1m_ratio` | 检查单分钟成交额放大 |
| `M04` | 加 `amount_acceleration_3m` | 检查连续成交额加速 |
| `M05` | 加 `price_vs_open_pct` | 检查是否站稳开盘价 |
| `M06` | 加 `volume_price_state` | 检查量价方向一致性 |
| `M07` | 相对强弱全量 | `M01 + M02` |
| `M08` | 成交额全量 | `M03 + M04` |
| `M09` | 量价全量 | `M03 + M04 + M05 + M06` |
| `M10` | 全部分钟特征 | `M07 + M09` |

分别在 `9:35` 和 `9:45` 截面运行，不能用更晚时点的数据替代早盘截面。

## 7. 环境消融

### 7.1 当前环境分类

当前 `market_regime` 使用指数和 ETF 竞价涨跌宽度：

```text
continuation
repair
risk_off
mixed
```

### 7.2 环境实验

| 实验编号 | 修改 | 目的 |
|---|---|---|
| `E00` | B0 当前四分类环境加分 | 基线 |
| `E01` | 所有环境视为 `mixed` | 衡量环境层整体贡献 |
| `E02` | 只保留指数环境 | 判断 ETF 宽度是否有效 |
| `E03` | 只保留 ETF 环境 | 判断指数环境是否有效 |
| `E04` | 环境只用于报告，不参与分数 | 判断加分是否造成排序偏差 |
| `E05` | 环境只改变 TopK，不改变分数 | 判断风险控制是否优于排序干预 |
| `E06` | 四分类合并为 `risk_off / non_risk_off` | 检查简化环境是否更稳定 |

推荐重点比较 `E04` 与 `E05`。环境信息通常更适合作为仓位和候选数量门禁，不一定适合作为个股排序加分。

### 7.3 环境动态 TopK

建议测试：

| 环境 | CP 风险 TopK | 反核 TopK | 趋势 TopK |
|---|---:|---:|---:|
| `risk_off` | 5 | 1 | 0 |
| `repair` | 3 | 5 | 2 |
| `continuation` | 2 | 2 | 5 |
| `mixed` | 3 | 3 | 3 |

该表是待验证假设，不应直接作为最终规则上线。

## 8. TopK 消融

### 8.1 单变量 TopK

先固定其他参数，只改变最终每类 TopK：

```text
K01 = 1
K03 = 3
K05 = 5
K08 = 8
K10 = 10
K15 = 15
```

每个 K 输出：

```text
avg_directed_body_pct
median_directed_body_pct
p25_directed_body_pct
p75_directed_body_pct
direction_hit_rate
strong_direction_hit_rate
selected_count_per_day
selected_count_p90
coverage
```

### 8.2 分 universe TopK

再测试：

| 实验编号 | 指数 | ETF | 个股 | 行业 | 每类最终上限 |
|---|---:|---:|---:|---:|---:|
| `U00` | 2 | 3 | 5 | 3 | 5 |
| `U01` | 1 | 2 | 3 | 2 | 5 |
| `U02` | 1 | 3 | 5 | 0 | 5 |
| `U03` | 0 | 3 | 5 | 0 | 5 |
| `U04` | 2 | 5 | 8 | 3 | 10 |
| `U05` | 0 | 0 | 5 | 0 | 5 |

解释：

- `U02`：观察行业信号是否重复占位。
- `U03`：仅 ETF 和个股，更贴近实际交易。
- `U05`：只看个股，测试 ETF 和指数是否更适合做环境而非候选。

### 8.3 选择原则

不要直接选胜率最高的 K。推荐约束：

```text
每日总观察数 <= 10
每日个股观察数 <= 5
selected_count_p90 <= 15
precision 相比 B0 不下降
strong_precision 尽量提高
至少覆盖 4 个 walk-forward 窗口
```

## 9. 实验输出格式

建议新增：

```text
reports/ablation/YYYYMMDD_YYYYMMDD/
  experiment_summary.csv
  experiment_daily.csv
  experiment_by_regime.csv
  experiment_by_universe.csv
  experiment_by_data_universe.csv
  universe_topk_summary.csv
  experiment_event_daily.csv
  experiment_event_summary.csv
  experiment_monthly_walk_forward.csv
  reversal_layer_samples.csv
  reversal_layer_summary.csv
  experiment_selected_samples.csv
  ablation_report.md
  ablation_metadata.json
```

### 9.1 experiment_summary.csv

```text
experiment_id
experiment_group
signal_category
selected_count
selected_count_per_day
selected_count_p90
direction_hit_rate
strong_direction_hit_rate
coverage
avg_directed_body_pct
median_directed_body_pct
p25_directed_body_pct
p75_directed_body_pct
daily_precision_std
baseline_avg_directed_body_pct
avg_directed_body_delta
notes
```

### 9.2 experiment_daily.csv

```text
date
experiment_id
market_regime
signal_category
universe_type
selected_count
success_count
precision
avg_body_pct
median_body_pct
```

### 9.3 experiment_selected_samples.csv

```text
date
experiment_id
signal_category
universe_type
code
name
group
rank_in_experiment
action_score
market_regime
auction_pct
cp
sa
prev_pct
prev_vol_ratio
pos_5d
body_pct
validation_success
selection_reason
```

分钟消融额外增加：

```text
feature_timestamp
rs_vs_etf_pct
rs_vs_index_pct
amount_1m_ratio
amount_acceleration_3m
price_vs_open_pct
volume_price_state
execution_bias
```

## 10. 推荐执行顺序

### 第一阶段：现在即可运行

命令：

```powershell
python main.py ablation 20260525 20260529
```

1. `F00-F08`：判断竞价特征净贡献。
2. `H00-H06`：检查硬过滤是否误删。
3. `E00-E06`：判断环境应该参与排序还是只参与门禁。
4. `K01-K15`：寻找可交易观察数量。
5. `U00-U05`：决定指数、ETF、个股、行业信号是否都应占短名单名额。

### 延期阶段：需要时再评估分钟数据

1. 固定第一阶段最优竞价短名单。
2. 分别运行 `9:35`、`9:45` 截面。
3. 执行 `M00-M10`。
4. 比较“无盘中确认”和“有盘中确认”的命中率、强命中率与覆盖率。

### 第三阶段：模型化

当完整样本达到至少 60 个交易日后：

1. 用硬规则消融筛掉明显无效特征。
2. 使用 Logistic Regression 作为可解释基线。
3. 使用 LightGBM 或 XGBoost 做非线性排序。
4. 用 walk-forward 验证模型排序的 TopK 是否稳定优于硬规则。
5. AI 只负责解释和复盘归纳，不直接生成未经约束的交易分数。

## 11. 防泄漏检查

任何实验输入中禁止出现：

```text
close
close_pct
body_pct
validation_success
validation_result
high
low
```

说明：

- `high`、`low` 如果来自收盘日线，也属于未来信息。
- 盘中确认实验可以使用截面时点之前已经发生的分钟高低点，但字段必须带 `feature_timestamp`。
- 盘后字段只允许出现在标签和结果表。

## 12. 当前结论

现有 5 个交易日数据足以验证消融框架是否正确，但不足以确定最终 TopK 和环境权重。优先级最高的是：

1. 重放 `E01`、`E04`、`E05`，确认环境更适合做排序加分还是数量门禁。
2. 重放 `K01`、`K03`、`K05`、`K08`，找到每日可控观察数量。
3. 比较 `U03` 和 `U05`，确认 ETF 是否应占候选名额，还是只作为个股背景特征。
4. 优先扩充纯竞价历史样本，再决定是否恢复分钟层实验。

## 13. 第一轮竞价消融结果

已使用 `20260525-20260529` 五个交易日完成第一轮重放。当前样本只用于发现明显问题，不用于冻结参数。

基线：

| 信号 | 入选数 | 平均方向调整实体 | 中位方向调整实体 | 方向命中率 |
|---|---:|---:|---:|---:|
| CP 风险 | 13 | +1.03% | +0.98% | 61.54% |
| 反核机会 | 17 | +0.47% | -0.31% | 41.18% |
| 趋势机会 | 20 | -1.48% | -0.57% | 45.00% |

初步观察：

1. CP 风险当前有效，`TopK=3` 比 `TopK=5` 更紧凑，平均方向调整实体提高到 `+1.15%`。
2. 反核 `TopK=3` 平均方向调整实体为 `+0.53%`，观察数量更少；但中位数仍为负，需要扩充样本。
3. 趋势基线明显较弱。移除环境加分后平均方向调整实体由 `-1.48%` 改善到 `-1.26%`，仍未转正。
4. 环境动态 TopK `E05` 在当前样本上恶化，不应直接上线。
5. 趋势 `TopK=1` 暂时改善到 `+1.03%`，但只有 4 条样本。它只说明趋势需要更强收缩，不能直接据此冻结参数。
6. 趋势需要单独重构候选和评分，不宜继续与 CP、反核共用同一套收缩逻辑。

## 12. 55 日连续窗口结果

已补齐最近 60 个交易日日线，并使用 `20260310 - 20260529` 的 55 个完整窗口目标日重新执行竞价复盘。

本轮已落地：

- CP 主报告只展示 Top3，Top1 标记最高优先级。
- CP 主报告只保留热门拥挤和高位加速兑现风险，其他场景保留在研究 CSV。
- 反核主报告保留 Top5，后续继续区分高置信与观察场景。
- 趋势删除高开加分，增加高开惩罚，并将高位加速分流到 CP 风险。
- 趋势主报告仅展示放量延续 Top1，温和延续保留在研究 CSV。

详细结论见：

`reports/ablation/20260310_20260529/SYSTEMATIC_ANALYSIS.md`
