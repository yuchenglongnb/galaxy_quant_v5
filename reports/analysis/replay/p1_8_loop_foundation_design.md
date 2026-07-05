# P1.8 Loop Foundation Design

## Loop 目标

P1.8 的目标是把竞价验证工程从“单点工具开发”推进到“真实反馈驱动的循环工程”。

核心循环是：

```text
sample window
-> run validation / replay / gate tools
-> generate real reports
-> commit curated real evidence pack
-> ChatGPT reviews reports
-> identify failure modes
-> Codex formalizes tools / tests / gates
-> expand date window / sample coverage
-> repeat
```

这不是公开发布优先的脱敏工程。当前优先级是保留足够真实的报告、失败样本、日期窗口、信号分组、指标口径和中间结论，让后续复盘能够直接读取证据。

## 当前系统阶段

当前 main 已包含：

- P1.4R observation-only memory cleanup
- P1.5A OHLC excursion validation fields
- P1.5B/C intraday path replay and broader-window distribution
- P1.5D path stability gate
- P1.6 validation stack documentation
- P1.7A read-only CP audit tools
- P1.7B readiness gate precondition tool

这些能力已经可以支撑从候选信号、T+1 回放、路径分型、稳定性 gate、CP 证据完整性到后续反馈分析的基本闭环。

## 为什么报告是一等资产

真实报告包含代码本身无法保存的上下文：

- 哪些日期窗口被分析过
- 哪些样本失败
- 哪些分组存在反例
- 哪些指标口径发生过歧义
- 哪些输出存在 mojibake 或环境路径问题
- 哪些工具还只是研究资产
- 哪些结论仍是 `insufficient_sample` 或 `rule_change_allowed=false`

这些信息是后续 ChatGPT / Codex 发现系统缺口的主要输入，因此 Markdown / JSON summary / replay report / gate report 应作为工程资产提交，而不是仅作为临时输出。

## 数据飞轮路径

1. 选择一个可解释样本窗口。
2. 运行 auction validation、T+1 replay、path distribution、gate review、CP evidence review。
3. 保留真实报告和真实失败样本。
4. 让 ChatGPT 读取报告，识别不足、反例、口径歧义和工具缺口。
5. 让 Codex formalize 新工具、测试、gate 或报告索引。
6. 扩展日期窗口或信号覆盖。
7. 继续沉淀新报告和新审计。

## 报告提交规范

优先提交：

- Markdown 复盘报告
- JSON summary
- gate review
- triage / packaging / formalization report
- 含真实日期、指标、样本、失败原因的分析报告

暂缓提交：

- 超大 raw data
- 纯 runtime dump
- execute/backfill 输出
- 用途尚未清楚的脚本和测试
- 含凭据、token、password 的文件

本机路径不是默认 blocker，但应在 inventory 中标注为 environment-specific。真实股票代码、真实日期、真实指标和失败样本应保留。

## 真实反馈保留原则

- 不因为样本结论负面而删除报告。
- 不因为指标显示失败而改写报告。
- 不把后验观察改成交易指令。
- 不把 evidence completeness 改成 backfill execution permission。
- 不把 gate eligibility 改成 rule implementation。
- mojibake 能安全修复时修复，不能修复时保留并标注 readability issue。

## 代码、测试、报告之间的关系

- 代码负责生成可复用分析。
- 测试负责保护输出契约和安全边界。
- 报告负责保存真实反馈和系统缺口。
- index / manifest 负责告诉后续 reviewer 哪些报告值得读，哪些仍应暂缓。

## 每轮迭代推荐流程

1. 从 main 新建独立分支。
2. inventory 当前未提交资产。
3. 选择一小批最高 loop value 的报告。
4. 生成或更新 evidence inventory。
5. 若新增工具，补 targeted tests。
6. 精确 add，不使用 broad add。
7. 提交 curated evidence pack。
8. 创建 PR，并在 PR body 中说明提交报告、暂缓报告和安全边界。

## 哪些报告优先提交

当前优先级：

1. CP structural repair / exemption / readiness 真实评估报告。
2. P1.7 triage 和 cleanup 报告。
3. 后续 prior-day / ETF / trend summary 报告。
4. 后续 market-structure backfill safety review，而不是 execute 输出。

## 哪些文件暂缓提交

- market-structure backfill script/test/report
- ETF / benchmark scripts and tests
- prior-day context scripts and tests
- trend / confirmation scripts and tests
- intraday confirmation execute reports
- bulk prior-day daily reports

这些资产仍有价值，但需要独立分支逐组处理。

## 后续如何让 ChatGPT 做不足分析

每个 evidence pack 应包含：

- 真实报告路径
- 日期窗口
- 指标口径
- 失败样本类型
- readability / environment notes
- 当前是否支持规则变更
- 下一步该扩大窗口、修工具、还是设计 gate

ChatGPT 可以直接读取这些报告，输出：

- 系统缺口
- 口径冲突
- 反例集中区
- 下一轮 Codex 工程任务
- 是否需要更多样本

## P1.8 之后路线图

- P1.9: Market-structure Backfill Execution Gate Refactor
- P1.10: Prior-day Context Evidence Loop
- P1.11: Trend Confirmation Coverage Expansion
- P1.12: Auction Replay Evidence Pack Expansion

P1.8 只建立 loop foundation，不修改 CP threshold、exemption、Trend active、strategy logic 或 registry。
