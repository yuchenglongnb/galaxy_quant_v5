# P1.6 PR Preparation Note

## PR 标题建议

`Add auction validation path replay and rule-proposal gate`

## PR 摘要

本 PR 将 P1.4R-P1.5D 的竞价验证工作整理为 analysis-only validation stack：包括 OHLC excursion 字段、日内路径 replay、多日 path distribution、规则提案准入 gate、以及长期维护文档。当前证据明确 `rule_change_allowed=false`，不包含策略规则变更。

## 改动分组

### P1.4R Observation-only Wording

- `reports/analysis/lessons/auction_lessons.jsonl`
- `reports/analysis/patterns/pattern_progress.json`

用途：把既存 lesson/pattern wording 降级为 observation-only。

### P1.5A OHLC Excursion

- `reports/intraday_excursion.py`
- `tests/test_intraday_excursion_features.py`
- `runners/auction.py`
- `reports/t1_backtest.py`

用途：在验证和报告层提供 OHLC 路径字段。

### P1.5B/C Replay And Distribution

- `reports/intraday_path_replay.py`
- `tests/test_intraday_path_replay.py`
- `reports/analysis/replay/20260701_20260702_intraday_path_replay.md`
- `reports/analysis/replay/20260701_20260702_intraday_path_summary.json`
- `reports/analysis/replay/20260626_20260702_intraday_path_distribution.md`
- `reports/analysis/replay/20260626_20260702_intraday_path_distribution_summary.json`

用途：复盘日内路径和 broader-window path distribution。

### P1.5D Gate Governance

- `reports/path_stability_gate.py`
- `tests/test_path_stability_gate.py`
- `reports/analysis/replay/20260626_20260702_path_stability_gate_review.md`
- `reports/analysis/replay/20260626_20260702_path_stability_gate_review_summary.json`

用途：定义未来规则提案前的研究准入 gate。当前结果为 `rule_change_allowed=false`。

### P1.6 Documentation

- `reports/analysis/replay/auction_validation_stack_readme.md`
- `reports/analysis/replay/p1_6_long_horizon_stabilization_plan.md`
- `reports/analysis/replay/p1_6_pr_preparation_note.md`
- `reports/analysis/replay/p1_4r_to_p1_5d_diff_packaging.md`

用途：长期维护说明、路线图、PR 准备和提交分包说明。

## 测试结果

```bash
python -m pytest tests/test_intraday_excursion_features.py tests/test_intraday_path_replay.py tests/test_path_stability_gate.py -q
```

结果：`31 passed`

```bash
python -m pytest tests/test_t1backtest_input_integrity.py tests/test_multiday_t1_validation.py -q
```

结果：`13 passed`

```bash
python -m py_compile reports/intraday_excursion.py reports/intraday_path_replay.py reports/path_stability_gate.py reports/t1_backtest.py runners/auction.py
```

结果：通过。

## 风险控制

本 PR 明确不包含：

- 策略规则变更
- evaluator 逻辑变更
- signal ranking / shortlist 变更
- CP threshold 变更
- CP 豁免扩展
- Trend active 状态变更
- 反核 trigger 变更
- `market_pattern_registry.json` 变更
- sync / snapshot rebuild / P1.2J / CP audit
- 交易建议

## Reviewer 重点

1. OHLC excursion 字段是否保持 validation-only。
2. T+1 denominator 是否清晰区分 resolved、unmatched、manual_scope_excluded、pending_blocked。
3. Broader-window distribution 是否避免阶段混合误读。
4. Gate review 是否明确 `rule_change_allowed=false`。
5. P1.4R observation-only wording 是否足够保守。
6. 生成报告和 JSON 是否适合入库。

## 不应纳入本 PR 的文件

以下早期研究资产不应混入本 PR：

- `scripts/evaluate_cp_structural_repair_audit.py`
- 其他未审 CP / ETF / prior-day / trend coverage 研究脚本
- 对应未审 evaluation reports
- 任何 runtime progress、临时缓存或未确认数据产物

这些文件应单独进入后续 phase review。
