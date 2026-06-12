# 特征建模与策略演进路线

## 1. 当前结论

竞价系统已经具备可用于研究的数据骨架：

- 指数、ETF、自选股、行业 TopK 因子快照。
- CP、SA、趋势分类。
- `auction_pct`、`body_pct`、`oar`、量比、排名、5 日位置等字段。
- 每日盘后验证和周度汇总。

但在训练模型之前，需要先修复标签泄漏：

- CP 候选由竞价时点数据触发，盘后用 `body_pct < 0` 验证，逻辑可用于真实回测。
- 反核机会在复盘模式中要求 `body_pct > 2` 才进入信号集，因此当前胜率偏乐观。
- 趋势机会在复盘模式中要求 `body_pct > 1` 才进入信号集，因此当前胜率不是盘前预测胜率。

正确做法是拆成两步：

```text
盘前/竞价阶段
  -> 只使用当时可见特征生成 candidate

盘后阶段
  -> 使用 body_pct 生成 label
  -> 评估 candidate 是否成功
```

## 2. 推荐分层

### 2.1 硬规则层

保留硬规则，负责：

- 数据完整性和 `intraday/closed` 状态门禁。
- CP、SA 候选生成。
- 风险底线和异常值处理。
- 可解释的基础场景标签。

硬规则适合稳定业务定义，不适合穷举复杂组合。

### 2.2 市场状态层

先判断市场 regime，再解释 CP/SA：

```text
continuation  强势扩散
repair        超跌修复
risk_off      风险释放
mixed         结构分化
```

建议输入：

```text
主要指数 auction_pct / body_pct / oar
指数上涨家数或正实体比例
ETF 正实体比例、负实体比例
成长 ETF 与价值 ETF 强弱差
板块收益离散度
昨日市场强弱和量能变化
```

初期使用硬规则或逻辑回归。样本积累后再比较树模型。

### 2.3 概率预测层

对不同任务分别建模：

```text
CP 模型:
  label = body_pct < 0
  output = P(兑现风险)

反核模型:
  label = body_pct > 0
  strong_label = body_pct > 2
  output = P(修复) / P(强修复)

趋势模型:
  label = body_pct > 0
  strong_label = body_pct > 2
  output = P(延续) / P(强趋势)
```

推荐顺序：

1. 逻辑回归：作为可解释基线。
2. LightGBM 或 XGBoost：处理非线性交互、缺失值和阈值组合。
3. 概率校准：输出可比较的概率。

不建议当前直接使用深度学习。现阶段有效 closed 样本天数太少，复杂模型更容易拟合噪声。

### 2.4 TopK 排序层

当目标是“每天选出最值得看的若干标的”，排序模型比单纯分类更匹配：

```text
group / qid = date
label       = 分桶后的 body_pct 或收益质量
metric      = precision@k / ndcg@k
model       = LambdaMART
```

排序层输出：

```text
指数 TopK
ETF TopK
自选股 TopK
行业 TopK
```

建议按 universe 分开训练或至少加入 `universe_type`。

### 2.5 RAG / LLM 层

LLM 不负责算 CP、SA 或预测概率。适合负责：

- 检索相似历史交易日。
- 总结本次与历史样本的差异。
- 解释硬规则与模型输出冲突。
- 生成观察点和失效条件。
- 将人工修正沉淀为 lesson。

## 3. 训练字段边界

### 可以作为模型输入

仅使用决策时点已经可见的字段：

```text
date
universe_type
code
group
rank
prev2_pct
prev1_pct
prev_body_pct
prev_vol_ratio
prev_close
auction_pct
auction_amount
oar
amount_rank
pos_5d
trend_state
stock_count
cp
sa
```

### 只能作为盘后标签或分析字段

```text
high
low
close
close_pct
body_pct
validation_success
validation_result
```

训练时如果把这些字段放入输入，会造成未来数据泄漏。

## 4. 验证方法

不要随机打散交易日。

推荐：

```text
walk-forward
TimeSeriesSplit(gap=N)
按日期分组
训练窗口只使用测试日期之前的数据
```

如果标签使用未来多个交易日收益，需要增加 purge 和 embargo，避免训练集和测试集标签窗口重叠。

## 5. 项目接入点

建议新增：

```text
features/
  candidate_builder.py
  dataset_builder.py
  regime_features.py

models/
  baseline_logistic.py
  gbdt_predictor.py
  ranker.py
  calibration.py

reports/
  weekly_review.py

artifacts/
  models/
  datasets/
```

推荐命令：

```text
python main.py weekly
python main.py weekly 20260525 20260529
```

当前已经实现周度复盘命令。竞价主链路已完成候选与标签分离：

- CP、反核、趋势候选只使用竞价时点可见字段生成。
- `body_pct` 只用于盘后验证，不参与候选筛选。
- 验证明细和全量快照记录 `candidate_generated_at`、`outcome_label_source`、`strong_validation_success`。
- 历史日期需要重新运行 `python main.py auction YYYYMMDD`，才能生成口径一致的新样本。

下一阶段可以把候选生成进一步抽取到 `candidate_builder.py`，并优先增加市场状态层。

## 6. 可执行短名单

研究候选和交易观察清单必须分开：

```text
signals
  -> 全量候选
  -> 用于盘后验证、阈值校准和模型训练

shortlist
  -> 竞价时点市场状态 + 可执行评分 + 分类型分市场 TopK
  -> 用于报告展示和盘中观察
```

短名单评分只允许使用竞价时点可见字段：

```text
cp / sa
auction_pct
prev_pct
prev_vol_ratio
pos_5d
amt_rank
target_type
```

禁止在短名单评分中使用：

```text
close
close_pct
body_pct
validation_success
```

当前市场状态层使用指数和 ETF 的竞价涨跌幅宽度，输出：

```text
continuation
repair
risk_off
mixed
```

短名单先按指数、ETF、自选股、行业分别限制 TopK，再按信号类型限制最终 TopK。当前 CP、反核、趋势各最多展示 5 条，每日理论上最多 15 条。原始候选不会删除，验证 CSV 中额外记录：

```text
actionable
action_score
shortlist_reason
action_filter_reason
market_regime
```
