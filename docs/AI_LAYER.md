# AI 优化层

本文档整合 AI 报告、硬编码替代、RAG/Skill 和模型调用边界。

## 1. AI 的定位

AI 不负责生成原始行情数据，也不负责替代底层数值计算。

AI 主要做三件事：

- 把硬编码文案改成更贴合市场结构的解释。
- 对复杂场景做语义归纳，例如“高开诱多”和“强势后弱开兑现”。
- 把历史验证结果沉淀为方法论和案例库。

## 2. 当前模式

配置入口：

```text
config/settings.py
  AIReportConfig
```

环境变量：

```powershell
$env:AI_REPORT_MODE="assist"
$env:AI_MODEL_BASE_URL="..."
$env:AI_MODEL_NAME="..."
$env:AI_MODEL_API_KEY="..."
$env:AI_MODEL_TIMEOUT_SECONDS="8"
$env:AI_MODEL_MAX_CALLS_PER_RUN="3"
```

模式：

```text
off      关闭 AI，只用模板
shadow   只记录 trace，不写入报告
assist   AI 或本地解释器参与报告
replace  预留，未来更强替代模式
```

## 3. 模块分工

```text
ai/model_client.py
  OpenAI-compatible API 调用

ai/signal_feature_builder.py
  构造信号解释输入特征

ai/signal_interpreter.py
  调度外部模型和本地兜底

ai/local_interpreter.py
  本地解释器，API 不可用或超时时使用

ai/validator.py
  校验 AI 输出，防止非 JSON、字段缺失、置信度异常

ai/trace_logger.py
  保存 AI 调用轨迹

ai/signal_labels.py
  信号子类型标签，例如高开诱多、强势后弱开兑现
```

## 4. 输入输出边界

AI 输入应是结构化 JSON，包含：

```text
target
signal_category
auction_pct
close_pct
body_pct
cp
sa
prev_pct
prev_body_pct
vol_ratio
pos_5d
market_oar
scenario
```

AI 输出必须是可校验 JSON，不能只返回自然语言。

推荐字段：

```text
scenario_label
direction
confidence
report_text
evidence
risk
advice
```

## 5. 速度策略

直接调用外部 API 普遍较慢，所以采用分层降级：

1. 关键少数信号调用外部模型。
2. 超过 `AI_MODEL_MAX_CALLS_PER_RUN` 后使用本地解释器。
3. 外部 API 超时后使用本地解释器。
4. 所有 AI 输入输出写入 `reports/ai_traces/`。

## 6. RAG 和 Skill

后续方法论沉淀建议分三类：

```text
methodology/
  CP风险.md
  反核机会.md
  趋势机会.md

cases/
  20260527_深科技_CP成功.md
  20260527_宁德时代_CP失败.md

feedback/
  threshold_review.md
  failed_cases.md
```

AI 在解释信号时可以检索：

- 同类历史成功/失败样本。
- 当前市场环境。
- 对应 ETF 和概念背景。
- 方法论规则。

## 7. 风控边界

必须保留硬规则的部分：

- 行情数据清洗。
- CP/SA 数值计算。
- 验证结果。
- 日志和快照落盘。

适合 AI 替代的部分：

- 标题和文案。
- 场景语义解释。
- 风险提示。
- 复盘总结。
- 失败案例归因。

