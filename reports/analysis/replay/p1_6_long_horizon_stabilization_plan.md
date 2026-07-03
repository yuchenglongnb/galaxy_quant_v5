# P1.6 Long-horizon Stabilization Plan

## 当前状态总结

P1.4R-P1.5E 已经把竞价验证链路从零散复盘推进到可复用的 validation stack：

- P1.4R：lesson / pattern wording 降级为 observation-only。
- P1.5A：新增 OHLC excursion 验证字段。
- P1.5B：形成两日 intraday path replay。
- P1.5C：扩展到 broader-window path distribution。
- P1.5D：新增 rule-proposal gate。
- P1.5E：完成提交前 diff packaging 和 commit plan。

当前结论：

- 退潮路径集中度上升只是后验观察。
- 当前证据不足以改变策略规则。
- 当前 gate 输出 `rule_change_allowed=false`。

## 长期路线

### P1.6A: 提交 / PR 准备

- 目标：按 P1.5E 分包计划整理提交和 PR。
- 输入：P1.4R-P1.5D diff、packaging report、测试结果。
- 输出：reviewable commit stack 或 PR。
- 禁止事项：不混入早期未审研究资产；不改策略规则。
- 通过标准：提交分组清晰，PR 描述明确 analysis-only 和 `rule_change_allowed=false`。

### P1.6B: 扩展到 20+ 交易日 Path Distribution

- 目标：把 path distribution 从 5 个交易日扩展到至少 20 个交易日。
- 输入：多日 signal_detail、OHLC、T+1 可用缓存。
- 输出：长窗口 path distribution 报告。
- 禁止事项：不补造数据，不运行重型重建。
- 通过标准：覆盖表完整，unmatched ratio 和 manual patch dependency 可解释。

### P1.6C: 跨市场阶段 Path Stability Review

- 目标：比较修复段、震荡段、退潮段的路径稳定性。
- 输入：P1.6B 长窗口 summary。
- 输出：阶段稳定性审查报告。
- 禁止事项：不把阶段标签写进策略逻辑。
- 通过标准：阶段内外结论分离，避免全窗口均值误导。

### P1.6D: Manual Patch 依赖降低

- 目标：减少历史 signal_detail 对 derived/manual patch 的依赖。
- 输入：历史 signal_detail、code backfill policy、manual patch 文件。
- 输出：更清晰的 code-keyed join 覆盖报告。
- 禁止事项：不覆盖原始历史文件。
- 通过标准：manual/derived input ratio 下降，unmatched 可解释。

### P1.6E: T+1 Join 质量提升

- 目标：提升 T+1 code-keyed resolved denominator。
- 输入：T+1 quote、signal_detail、derived/manual patch。
- 输出：T+1 coverage quality report。
- 禁止事项：不使用静默 name fallback。
- 通过标准：unmatched ratio 低于 gate 配置阈值。

### P1.6F: 反例库与 Contradiction Tracking

- 目标：把强观察中的反例系统化记录为 review evidence。
- 输入：path distribution、T+1 summary、representative cases。
- 输出：contradiction tracking 报告。
- 禁止事项：不写 lesson/pattern，不改 registry。
- 通过标准：每个 potential proposal 都有反例检查。

### P1.6G: Future Rule Proposal Template

- 目标：设计未来规则提案模板，但不提交任何规则变更。
- 输入：gate review、长期样本、反例库。
- 输出：rule proposal template。
- 禁止事项：不实施策略规则。
- 通过标准：模板必须包含样本量、稳定性、反例、out-of-sample、回滚条件。

## 规则提案准入标准

这些是研究治理条件，不是交易阈值：

- `min_dates >= 8`
- 每个 signal family 有足够样本，例如 `min_signal_samples >= 50`
- T+1 resolved 样本达到最低要求，例如 `min_t1_resolved >= 30`
- unmatched ratio 低于治理阈值，例如 `max_unmatched_ratio <= 0.20`
- manual/derived input dependency 不应过高
- 均值和中位数方向一致
- 结果不能只由单日驱动
- 修复段和退潮段不能混在一个均值里直接解释
- 必须通过 contradiction check
- 必须有 out-of-sample replay

## 提交建议

延续 P1.5E 的 4 commit plan：

1. `P1.4R: downgrade auction lessons to observation-only wording`
2. `P1.5A: add intraday OHLC excursion validation fields`
3. `P1.5B-C: add intraday path replay and broader-window distribution reports`
4. `P1.5D: add path stability gate for rule-proposal governance`

P1.6 文档可以作为第 5 个文档提交：

`P1.6: document auction validation stack and PR plan`

## 风险

- 样本窗口仍短。
- 市场阶段混合会扭曲均值。
- manual patch 依赖仍需要降低。
- T+1 denominator 必须持续对账。
- 报告可能被误读为交易规则，因此必须持续保留 analysis-only 和 `rule_change_allowed=false` 边界。

## 下一步建议

优先进入 P1.6A：commit / PR 准备。不要继续扩功能，先把当前验证栈变成可审查、可交接的工程资产。
