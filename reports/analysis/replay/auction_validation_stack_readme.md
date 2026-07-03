# Auction Validation Stack 使用说明

## 背景

P1.4R-P1.5D 的目标是增强竞价验证层，而不是改变策略层。当前验证栈用于回答三个问题：

1. 竞价候选在日内 OHLC 路径上如何演化。
2. T+1 code-keyed 验证是否稳定、可审计。
3. 当前证据是否达到未来规则提案的最低研究准入要求。

当前默认结论仍是 analysis-only。任何观察都不能直接转成 CP 阈值、CP 豁免、Trend active、反核触发或排序逻辑的变更。

## 分层架构

### Layer 1: OHLC Excursion Feature

- 文件：`reports/intraday_excursion.py`
- 输入：`open/high/low/close`
- 输出：日内路径字段和 `signal_path_type`
- 用途：给竞价验证、T+1 验证和 replay 报告提供统一路径描述。

### Layer 2: Daily / T+1 Replay

- 文件：`reports/intraday_path_replay.py`
- 输入：`signal_detail.csv`、manual/code-backfilled derived signal_detail、`AmazingData_Store/<date>/stocks.csv`、`AmazingData_Store/<date>/indices.csv`
- 输出：两日 replay Markdown/JSON
- 用途：复盘单日和 T+1 路径，不改变候选生成和验证规则。

### Layer 3: Broader-window Distribution

- 文件：`reports/intraday_path_replay.py`
- 输入：多日 signal_detail + OHLC
- 输出：多日 path distribution Markdown/JSON
- 用途：检查路径分型在不同日期、信号类别、阶段标签下是否稳定。

### Layer 4: Rule-proposal Gate

- 文件：`reports/path_stability_gate.py`
- 输入：broader-window summary JSON
- 输出：gate review Markdown/JSON
- 用途：判断未来是否允许进入“规则提案草案”阶段。当前 gate 输出 `rule_change_allowed=false`。

### Layer 5: Commit / PR Packaging

- 文件：`reports/analysis/replay/p1_4r_to_p1_5d_diff_packaging.md`
- 输入：工作区 diff 和生成物
- 输出：提交分包、风险审计、复现命令和 PR 准备建议。

## 核心字段定义

- `open_to_high_pct`：日内最高价相对开盘价的涨幅。
- `open_to_low_pct`：日内最低价相对开盘价的跌幅。
- `close_to_high_drawdown_pct`：收盘价相对日内最高价的回撤。
- `intraday_range_pct`：日内最高价相对最低价的振幅。
- `mfe_pct`：验证层字段，当前等同于 `open_to_high_pct`。
- `mae_pct`：验证层字段，当前等同于 `open_to_low_pct`。
- `signal_path_type`：基于 OHLC 的保守路径标签，例如 `one_way_selloff`、`low_open_rebound_failed`、`rush_up_fade`、`high_open_trap`、`range_chop`。

## 口径定义

- `body_pct`：当日 `close / open - 1`，即开盘到收盘的实体表现。
- `t1_open_return`：T+1 `open / pre_close - 1`。
- `t1_close_return`：T+1 `close / pre_close - 1`。
- `t1_close_positive_rate`：resolved code-joined 样本中 `t1_close_return > 0` 的比例。

Denominator 规则：

- `manual_scope_excluded`：行业/板块项不进入 code-level denominator，但必须计数。
- `pending_blocked`：人工未决项不进入 resolved denominator，但必须保留。
- `unmatched`：code-keyed join 失败项不进入收益指标，但必须计入覆盖质量。
- `fallback_name_join_count`：当前路径验证栈不依赖静默 name fallback。

## 标准运行命令

两日 replay：

```bash
python -m reports.intraday_path_replay --dates 20260701 20260702 --output reports/analysis/replay/20260701_20260702_intraday_path_replay.md --json-output reports/analysis/replay/20260701_20260702_intraday_path_summary.json
```

多日 path distribution：

```bash
python -m reports.intraday_path_replay --start-date 20260626 --end-date 20260702 --output-md reports/analysis/replay/20260626_20260702_intraday_path_distribution.md --output-json reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json
```

规则提案准入 gate review：

```bash
python -m reports.path_stability_gate --input-json reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json --output-md reports/analysis/replay/20260626_20260702_path_stability_gate_review.md --output-json reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json
```

## 标准测试命令

```bash
python -m pytest tests/test_intraday_excursion_features.py tests/test_intraday_path_replay.py tests/test_path_stability_gate.py -q
python -m pytest tests/test_t1backtest_input_integrity.py tests/test_multiday_t1_validation.py -q
python -m py_compile reports/intraday_excursion.py reports/intraday_path_replay.py reports/path_stability_gate.py reports/t1_backtest.py runners/auction.py
```

## 安全边界

本验证栈不做以下事项：

- 不调整 CP 阈值。
- 不扩大 CP 豁免。
- 不启用 Trend active。
- 不修改 Trend active / shadow gate。
- 不修改反核 trigger。
- 不修改 signal ranking / shortlist / evaluator decision logic。
- 不写新的 lesson / pattern。
- 不写 `market_pattern_registry.json`。
- 不运行 sync、snapshot rebuild、P1.2J 或 CP audit。
- 不输出交易建议。

## 如何解读报告

- `analysis_only=true`：报告仅用于验证和审计。
- `posterior validation`：报告使用后验 OHLC 和 T+1 数据解释路径表现。
- `insufficient_sample`：当前样本不足以支持规则提案。
- `rule_change_allowed=false`：当前证据没有通过规则提案准入 gate。

## 常见误区

- 不要用单日路径直接改规则。
- 不要混用 `body_pct` 与 `t1_close_return`。
- 不要忽略 unmatched denominator。
- 不要把修复段和退潮段混在一个均值里直接下结论。
- 不要把 `eligible_for_human_review` 理解成已经可以实施规则；它最多代表未来可以起草研究提案。
