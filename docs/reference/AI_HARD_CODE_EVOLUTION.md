# AI 替代硬编码研判的演进方案

## 背景

当前报告里仍有一类典型硬编码问题：数值触发逻辑和文字解释逻辑没有分层。

例子：

```text
半导体 auction_pct = -0.17%
CP 被触发，因为昨日大涨后“弱低开/不深低开”仍有兑现风险
但文案写成“高位逆势高开”
```

这个问题不是行情数据错误，而是“规则场景”和“语言模板”绑定得太死。类似问题后续还会反复出现：

- 低开但被写成高开。
- 缩量承压但被写成正常洗盘。
- CP 高但日内转强，仍被写成诱多。
- SA 高但没有实体修复，仍被写成反核机会。
- 指数形态字段是 T-1/T-2 语境，但市场环境框拿它当今日结论。

## 核心原则

AI 不替代数值计算，AI 替代语义解释。

程序负责：

- 行情读取。
- OHLCV、涨跌幅、实体、影线、量比、位置、均线距离。
- CP/SA 分数。
- 排名、过滤、阈值触发。
- 回测胜率统计。

AI 负责：

- 判断当前信号属于哪一种语义场景。
- 解释为什么触发。
- 识别硬规则与事实的冲突。
- 输出观察点和失效条件。
- 根据用户纠错持续沉淀方法论。

## 推荐架构

```text
DataManager / DataProcessor
  -> FeatureBuilder
      生成结构化事实
  -> MethodologyRetriever
      检索方法论、历史案例、用户纠错
  -> AIInterpreter
      调用模型 API，输出 JSON
  -> Validator
      校验输出是否引用真实字段，是否违背数值事实
  -> ReportRenderer
      渲染报告
  -> FeedbackCollector
      收集纠错，沉淀为案例/skill
```

## 分层替代范围

### 第一层：必须保留硬规则

这些不交给 AI：

- `auction_pct`
- `close_pct`
- `body_pct`
- `vol_ratio`
- `pos_5d`
- `CP`
- `SA`
- `rank`
- `signal_triggered`

原因：这些是可回测、可复盘、可对比的确定性事实。

### 第二层：AI 优先替代

这些适合交给 AI：

- `scenario_label`
- `scenario_reason`
- `risk_summary`
- `opportunity_summary`
- `watch_points`
- `invalid_if`
- `report_text`

原因：这些是语义归纳，硬编码最容易出错。

### 第三层：AI 与硬规则并行

过渡期可以双轨：

```text
硬规则信号: CP=94.5, 诱多
AI语义: 高位弱开兑现风险
冲突标记: 不是高开诱多，不应使用“高开”模板
```

等积累足够纠错案例后，再让 AI 语义成为报告主文案。

## 模型输入协议

不要把原始 CSV 或整段报告直接丢给模型。应传结构化事实。

```json
{
  "task": "explain_auction_signal",
  "target": {
    "name": "半导体",
    "type": "ETF",
    "date": 20260526
  },
  "facts": {
    "t2_pct": 2.67,
    "t1_pct": 7.26,
    "auction_pct": -0.17,
    "close_pct": -1.15,
    "body_pct": -0.98,
    "vol_ratio": 1.08,
    "pos_5d": 88,
    "cp": 94.5,
    "sa": null
  },
  "hard_rule": {
    "signal": "TRAP",
    "trigger_reason": "prev_pct > 3 and auction_pct > -0.3",
    "old_template": "高位逆势高开"
  },
  "retrieved_methodology": [
    "昨日大涨后弱低开，如果没有快速修复，更多表征获利盘兑现，而不是高开诱多。",
    "文案必须区分：高开诱多、弱低开兑现、深低开承接失败。"
  ],
  "output_schema": "AuctionSignalInterpretationV1"
}
```

## 模型输出协议

模型必须输出 JSON，不直接输出自由文本。

```json
{
  "scenario_label": "强势后弱开兑现风险",
  "direction": "risk",
  "confidence": 0.82,
  "evidence": [
    "T-1上涨+7.26%，短线获利盘较厚",
    "竞价-0.17%，不是高开，不能使用高开诱多模板",
    "收盘-1.15%，实体-0.98%，弱开后未修复"
  ],
  "watch_points": [
    "次日能否收回今日实体",
    "是否跌破5日区间中枢",
    "半导体设备/科创50是否继续拖累"
  ],
  "invalid_if": [
    "次日放量反包今日阴线",
    "板块核心ETF重新站回短期均线"
  ],
  "report_text": "半导体不是高开诱多，而是昨日大涨后的弱开兑现风险。竞价仅小幅低开，但收盘未能修复，说明获利盘压力仍在。"
}
```

## Validator 校验规则

AI 输出后必须经过程序校验。

硬约束：

- 如果 `auction_pct <= 0`，文案不能出现“高开”作为今日行为。
- 如果 `body_pct <= 0`，不能写“日内转强确认”。
- 如果 `close_pct < auction_pct`，不能写“低开高走”。
- 如果 `SA` 为空，不能写“SA 高”。
- 如果 `CP` 为空，不能写“CP 高”。
- `evidence` 中的数字必须来自输入 facts。

校验失败时：

```text
AI 文案不通过 -> 降级到本地解释器 -> 记录 ai_validation_failed
```

## Skill 沉淀方式

这里的 skill 不是单纯 prompt，而是项目方法论协议。

建议目录：

```text
skills/
  market-report-interpreter/
    SKILL.md
    references/
      label_taxonomy.md
      auction_signal_rules.md
      index_trend_rules.md
      examples.md
      corrections.md
```

`SKILL.md` 只放核心流程：

- 先读结构化 facts。
- 不改写数值事实。
- 先判断硬规则是否与事实冲突。
- 再选择语义标签。
- 每个结论必须给证据。
- 低置信度必须输出观察，不输出定论。

`label_taxonomy.md` 放标签体系：

```text
高开诱多
强势后弱开兑现风险
低开承接失败
低开强修复
缩量承压回落
缩量震荡
放量突破
高位冲高回落
低位探底修复
```

`corrections.md` 放用户纠错：

```text
2026-05-26 半导体
旧输出: 高位逆势高开
问题: auction_pct=-0.17%，不是高开
修正: 强势后弱开兑现风险
新增原则: auction_pct<=0 时，禁止使用“高开诱多/逆势高开”模板。
```

## 进化闭环

每次报告生成时记录：

```text
reports/ai_traces/YYYYMMDD_signal_interpretation.jsonl
```

每条包括：

- input facts
- retrieved methodology
- model output
- validator result
- final rendered text
- user correction if any

用户纠错后进入：

```text
knowledge/feedback/corrections.md
```

定期归并：

```text
knowledge/methodology/auction_signal_rules.md
skills/market-report-interpreter/references/auction_signal_rules.md
```

这样 AI 的能力进化不是靠“记忆聊天”，而是靠可审计的案例和方法论文件。

## 最小落地版本

第一步先做信号卡解释，不动 CP/SA 分数。

新增模块：

```text
ai/
  schemas.py
  model_client.py
  signal_feature_builder.py
  signal_interpreter.py
  validator.py
  trace_logger.py
```

调用位置：

```text
analyzers/factors.py
  ScenarioIdentifier 仍负责信号触发
  CommentaryGenerator 改成优先调用 AI
  AI 失败再回退模板
```

环境变量：

```text
AI_MODEL_API_KEY=
AI_MODEL_BASE_URL=
AI_MODEL_NAME=
AI_REPORT_MODE=off|shadow|assist|replace
```

模式说明：

- `off`: 只用硬编码。
- `shadow`: AI 只记录，不进报告。
- `assist`: AI 进入报告，但保留硬规则对照。
- `replace`: AI 文案替代硬编码模板。

建议先用 `assist`。

## 与当前代码的衔接

当前已经有：

- `ai/feature_builder.py`
- `ai/local_interpreter.py`
- `AuctionAnalyzer` 中的 AI 旁路字段。

下一步应补：

1. `SignalFeatureBuilder`：为 ETF/行业/股票池分组生成信号解释 facts。
2. `ModelInterpreter`：调用你的模型 API。
3. `AIOutputValidator`：校验模型是否违背事实。
4. `TraceLogger`：保存输入输出和校验结果。
5. `FeedbackCollector`：把你指出的问题转成 correction case。

## 风险边界

- AI 不直接决定买卖。
- AI 不修改 CP/SA 分数。
- AI 不生成不存在的行情事实。
- AI 不能覆盖程序校验失败。
- AI 输出必须可回放、可审计、可复盘。

