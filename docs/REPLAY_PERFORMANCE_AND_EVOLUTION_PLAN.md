# 复盘性能与策略演进路线图

更新时间: 2026-06-12

## 1. 目标

这份文档服务三个长期目标：

1. 让盘后复盘、竞价回放、分时回补尽量优先走本地缓存，减少被壳层和远端校验拖慢。
2. 让环境门控和主线簇识别成为策略主轴，而不是继续围绕 CP / SA 单点修补。
3. 把每天的验证结果沉淀成可以持续升级的规则、模式和排序特征。

## 2. 当前业务链路

### 2.1 数据链路

1. AmazingData 登录
2. 交易日列表校验
3. 日线同步
4. 竞价 / noon / close 分钟口径同步
5. 历史 snapshot 回补 `09:25`
6. min1 K 回补 `09:30-09:35`
7. 生成 `stock_confirmation_latest.csv`
8. 竞价分析 / 盘后复盘 / validation 落盘

### 2.2 分析链路

1. 读取日线与竞价缓存
2. 生成指数 / ETF / 个股 / 行业因子
3. 生成 CP / reversal / trend 候选
4. 环境门控
5. 主线簇识别
6. `09:35` 确认层修正
7. shortlist 排序
8. daily validation / lesson / pattern 沉淀

## 3. 为什么现在耗时高

### 3.1 入口层重复做远端校验

最典型的是盘后重跑 `auction`：

- 入口先取最近交易日
- 发现本地 `_trading_days_cache.txt` 只有 10 天
- 为了拼出 6 日分析窗口，又去调用远端验证最近交易日

即使 `AmazingData_Store/YYYYMMDD` 已经是完整 `closed` 缓存，也会被这层卡住。

### 3.2 同步链路存在“低价值慢步骤”

当前单日同步里，个股：

- `stocks_noon` 常常耗时数秒且经常返回空
- `stocks_close` 仍然需要额外远端调用

对于盘后复盘来说，真正有价值的往往是：

- 日线 closed
- 竞价精确快照
- `09:30-09:35` 早盘确认

并不是每一步都必须重新从远端串行拉一次。

### 3.3 壳层问题放大了主流程耗时

目前观察到三类“非分析本身”的拖慢：

1. `main.py` 入口先碰登录，再做本地动作
2. PowerShell 编码导致 `python -c` 打印卡顿或异常
3. 长日志持续输出让工具层表现得像“命令卡住”

### 3.4 分时监控和盘后回补仍然是两套心智模型

虽然现在已经有：

- 实时 snapshot
- 历史 snapshot 回补 `09:25`
- min1 K 回补 `09:30-09:35`

但实盘守护和盘后回补还没有完全抽象成统一的数据产品层，因此维护和排障成本偏高。

## 4. 已经明确的三个核心问题

### 核心问题 A：复盘入口太依赖远端

表现：

- 本地已有 `closed` 数据
- 盘后复跑却仍被交易日验证、登录和壳层输出拖慢

影响：

- 每次复盘要花很多时间确认“是不是入口在卡”
- 不利于做批量验证、消融和多日重放

### 核心问题 B：环境门控升级不够快

表现：

- `20260609` 这种连续承压后的强修复日，`09:25` 仍然偏保守
- 收盘才发现是科技主线的系统性修复

影响：

- CP 容易误伤真正的强修复主线
- 趋势信号的优先级提升不够快

### 核心问题 C：主线簇识别还没完全压过单票直觉

表现：

- 单票高开/弱开仍然容易主导判断
- ETF、行业聚合、中军个股的一致性还没有成为最强信号

影响：

- 普修日和强主线修复日不容易区分
- 反核与趋势排序还不够贴近真实盘面

## 5. 已落地的近期改动

### 5.1 入口与性能

1. 盘后 replay 优先使用本地完整日线缓存
2. `get_analysis_window_days()` 优先从本地完整缓存切窗口
3. `main.py auction YYYYMMDD` 主入口已经显式切换为“本地复盘优先”
4. `main.py auction 20260609` 实测已从“远端校验卡顿”降到约 8 秒级别完成
5. `main.py review` 主入口已经切换为“本地复盘优先”，避免再被 TGW push 初始化拖住

### 5.2 数据与确认层

1. `historical_snapshot_925` 已接入主链路
2. `09:25` 与 `09:30-09:35` 已拆分为不同数据口径
3. `09:35` 确认层已经生成并进入 trend 过滤/加权
4. 未撮合 / 零价竞价快照已经单独落盘并进入股票池可靠性统计

### 5.3 策略语义层

1. 新增 `strong_repair` 环境标签
2. `strong_repair` 已接入：
   - shortlist regime bonus
   - 市场环境展示
   - environment gate
   - pattern registry
3. `confirmed_strength` 与 `preopen_signal_action` 已开始反哺 shortlist
4. `theme_cluster_strength` 已开始基于历史 `regime_cluster_summary.csv` 反哺 trend / reversal 排序
5. shortlist / daily analysis review 已开始显式记录分数拆解与主线簇加权贡献，方便后续做消融与参数校准
6. `risk_off` 下的 reversal 已拆分为：
   - `high_confidence_structural_repair`
   - `weak_reversal_observation`
   并新增 `structural_repair_detected / structural_repair_flags / reversal_preference` 字段，优先用“成长指数修复 + 半导体/资源类ETF同步转强 + 正收益集中”识别结构修复日
7. `auction-review-analyst` skill 已补充“盘中分析 -> 盘后验证 -> lesson/pattern 更新”闭环，后续可直接用盘中数据给出 provisional judgment，并在收盘后复核

## 5.4 当前仍待改进

1. 历史样本还不够厚，`strong_repair` 与主线簇统计还缺跨月份证据
2. `theme_cluster_strength` 已进入统一排序特征，但目前仍属于保守接入阶段，样本门槛和权重还需要继续校准
3. 技术路线对比虽然已进入 daily review，但还缺跨阶段的统一周报 / 月报沉淀
4. 分时守护与盘后回补虽然都可用，但还没完全收敛成统一数据产品层
5. `leading_clusters` 仍主要停留在复盘解释层，还没完全进入主排序
6. `risk_off` 结构修复识别已上线第一版，但阈值仍需要靠更多跨月份样本继续校准
7. `strong_repair` 还没有正式细分成 `broad_strong_repair` 与 `rotational_strong_repair`

## 6. 中期优化方案（1-4 周）

### 6.1 让复盘链路彻底本地优先

目标：

- `closed` 数据存在时，不再默认触发远端交易日校验

建议：

1. 增加明确的离线复盘模式
2. `auction/review/regime` 默认优先读本地完整缓存
3. 只有缺少窗口数据时才按需刷新某一日

预期收益：

- 盘后重跑显著提速
- 批量回测和消融更稳定

### 6.2 把 `09:35` 确认层升级成正式二次决策层

目标：

- 不只是“辅助确认”，而是允许覆盖 `09:25` 的早盘误判

建议：

1. 对 trend 建立 `09:25 -> 09:35 -> close` 的两阶段验证表
2. 对 CP 建立“翻案条件”
3. 对 reversal 建立“确认承接 / 弱势延续”分流

预期收益：

- 少追错修复日里的强主线
- 少在弱势延续日里误做反核

### 6.3 主线簇识别进入主排序

目标：

- ETF + 行业聚合 + 中军 + confirmed_strength 共同决定优先级

建议：

1. 建立 `theme_cluster_strength` 统一特征
2. 按 regime 统计簇内 confirmed_strength 表现
3. trend / reversal 都引入主线簇一致性加权
4. 在 daily review 里保留 shortlist score driver，避免排序升级后不可解释

预期收益：

- 少依赖单票偶然高开
- 更接近真实交易中的“做主线而不是做点”

## 7. 中长期优化方案（1-3 个月）

### 7.1 统一数据产品层

目标：

- 把实时 snapshot、历史 snapshot、min1 K fallback、validation 全部收进同一层数据接口

建议：

1. 统一输出标准字段：
   - `auction_source`
   - `auction_price_exact`
   - `auction_amount_exact`
   - `confirmation_source`
   - `feature_timestamp`
2. 让分析器不关心“原始数据从哪里来”，只认标准字段

### 7.2 环境驱动的策略矩阵

目标：

- 不是“一个策略打天下”，而是不同环境启用不同子策略

建议：

1. hostile：默认空仓/极窄观察
2. risk_off：默认只保留 ETF / 指数级修复观察；若命中 `structural_repair_detected`，再开放高置信结构修复反核
3. repair：主线簇修复观察
4. strong_repair：允许趋势和修复跟随
5. continuation：主线趋势优先

后续建议继续细分：

- `broad_strong_repair`：指数与成长方向普遍共振，趋势可以相对放开
- `rotational_strong_repair`：指数修复成立，但旧主线兑现、新主线切换，趋势不能普开

### 7.3 从规则走向排序模型

目标：

- 保留硬规则做门控，用模型做排序

建议：

1. 继续积累 `confirmed_strength`、主线簇、环境分层样本
2. 先做轻量排序模型而不是二分类
3. 分 universe 建模：
   - ETF reversal
   - stock trend
   - industry cluster continuation

## 8. 建议纳入本地长期目标

建议把项目长期目标明确成下面四条：

1. **复盘快**
   - 当天收盘后 5-10 分钟内能稳定重跑核心报告

2. **盘前准**
   - `09:25` 候选尽量精确，减少被 `09:30` 混入口径污染

3. **盘中能确认**
   - `09:35` 能对早盘判断做有效修正

4. **方法论会成长**
   - 每天的失败和成功样本会自动沉淀到 lesson / pattern / validation

## 9. 后续执行顺序

建议按下面顺序推进：

1. 补齐最近 40-60 个连续交易日的竞价复盘 / validation 样本
2. 基于补齐后的样本建立按 regime 分层的长期绩效面板
3. 已完成：`theme_cluster_strength` 正式引入 trend / reversal 排序（保守版）
4. 已完成：daily review 开始记录 shortlist score driver 与技术路线对比
5. 已完成：把 `risk_off` 下的 reversal 拆成“结构修复高置信”与“弱反核观察”
6. 把 `leading_clusters` / `theme_cluster_summary` 正式引入 shortlist 排序，而不只用于盘后解释
7. 再继续压缩分时守护与盘后回补之间的实现分叉
8. 把 `strong_repair` 继续细分成 `broad_strong_repair` 与 `rotational_strong_repair`
9. 趋势排序加入三道结构过滤：
   - 相对所属 ETF 强弱
   - 相对指数强弱
   - 是否属于 leading cluster

### 9.1 当前执行状态

- [x] 第一步之前的前置工作：主入口本地复盘优先
- [x] 历史样本补齐：最近 60 个连续交易日 (`20260312 - 20260609`) 已重放并补齐 daily validation
- [x] regime 长期绩效面板：已生成 `reports/analysis/regime_cluster/20260312_20260609/`
- [x] `theme_cluster_strength` 已正式进入排序（保守版）
- [x] daily analysis review 已开始记录 shortlist score driver 与技术路线对比
- [x] `main.py review` 已切换为本地 `closed` 缓存优先
- [x] `risk_off structural repair` 第一版识别与 reversal 分层已上线
- [x] `auction-review-analyst` skill 已支持盘中 provisional judgment 与盘后验证闭环
- [ ] `leading_clusters` 直接进入 shortlist 主排序
- [ ] `strong_repair` 子环境拆分：broad vs rotational
- [ ] 趋势排序加入 ETF / 指数 / leading_cluster 三重过滤
- [ ] 按月沉淀技术路线对比周报 / 月报

### 9.2 当前样本结论摘要

基于 `20260312 - 20260609` 的 60 个交易日样本：

1. `risk_off / reversal` 整体最稳定，胜率约 55%，定向实体为正。
2. `hostile / reversal` 名义胜率也高，但更适合作为“窄观察池”，不适合直接放大做多。
3. `continuation / trend` 的总体样本很多，但整体均值仍显著为负，说明“continuation” 里混入了大量假趋势日。
4. `strong_repair / trend` 当前样本仍少，且整体均值为负，说明它已经是值得单独建模的环境，但还不该直接大幅加权。
5. 主线簇在 `数字芯片设计 / 印制电路板 / 消费电子零部件及组装 / 垂直应用软件 / 军工电子` 上重复出现，已经足够支撑下一步做 `theme_cluster_strength`。
6. `theme_cluster_strength` 现阶段只对样本足够的簇做有限加权，避免被单月局部行情带偏。
7. 现阶段最合适的技术分工已经逐渐清晰：硬规则做触发与门控，regime/cluster 统计做排序增强，09:35 确认做翻案层，AI 主要做解释层与方法论沉淀。
8. `20260610` 提供了新的反例样本：`risk_off` 环境里反核大面积失效，而 CP 风险相对更有效，说明“低开不等于可反核”，环境优先级必须高于 SA 单点分数。
9. `20260611` 则提供了相反样本：指数仍弱，但科创修复与半导体/资源类 ETF 同步转强，说明 `risk_off` 不能粗暴等价为“全部反核关闭”，而应继续细分为“弱势延续”与“结构修复”。
10. `20260612` 提供了新的关键样本：不是“环境差所以不能做”，也不是“强修复所以趋势普开”，而是“指数修复 + 主线切换 + 老高位兑现”，说明 `strong_repair` 也需要继续细分。

## 9.2.1 20260610 新观察

1. 竞价报告给出 `risk_off`，盘后全景复盘给出 `🔴 环境恶劣 (空仓观望)`，两者一致。
2. 当天验证结果中：
   - CP 风险 `3 -> 2` 成功，胜率约 `67%`
   - 反核机会 `29 -> 10` 成功，胜率约 `34%`
   - 趋势机会 `9 -> 4` 成功，胜率约 `44%`
3. 创业板与科创50收盘实体都为负，且大量高 SA 候选最终没有修复成功，说明当日更接近“反弹后再承压”而不是“低开承接修复”。
4. 这条样本支持后续把以下条件加入反核降权门控：
   - `market_regime = risk_off`
   - 创业板、科创50收盘实体双负
   - SA 候选样本数显著偏多但整体胜率显著偏低

## 9.2.2 20260611 新观察

1. 竞价层仍给出 `risk_off`，但盘后验证显示这不是“普修”，而是“结构修复”。
2. 当天更值得信任的不是机械 SA，而是：
   - 科创50收盘实体转正
   - 半导体设备、工业有色、稀有金属 ETF 同步走强
   - 主线簇集中在数字芯片设计 / PCB / 消费电子链
3. 这类样本支持把 `risk_off` 继续细分成：
   - `weak_reversal_observation`
   - `high_confidence_structural_repair`
4. 当前第一版代码已经按这个方向落地，但 `leading_clusters` 还没有完全进入盘前排序，下一步仍应继续把簇一致性压过单票直觉。

## 9.2.3 20260612 新观察

1. 当天竞价报告给出 `strong_repair`，方向上没有问题，但不能直接翻译成“趋势普开”。
2. 当天更准确的盘面语言是：
   - 指数修复
   - 主线切换
   - 老高位兑现
3. 资源 / 有色 / 券商比半导体链更强，而双创高开后实体转弱，说明这不是 `broad_strong_repair`，更接近 `rotational_strong_repair`。
4. 验证结果也支持这个判断：
   - CP 风险 `12 -> 8`，胜率 `66.67%`
   - 反核机会 `2 -> 2`，胜率 `100%`
   - 趋势机会 `30 -> 17`，胜率 `56.67%`，但平均实体 `-0.99%`
5. 这说明趋势候选数量虽然多，但没有真正完成“结构过滤”，后续应优先增加：
   - 相对所属 ETF 强弱
   - 相对指数强弱
   - 是否属于 leading cluster
6. 同时，CP 也不能只看数值本身，必须区分：
   - 老高位兑现
   - 新主线加速

## 9.2.4 近期优先提炼

基于 `20260610 / 20260611 / 20260612` 这三天，当前最值得继续沉淀的不是单一阈值，而是三件事：

1. `risk_off` 下区分“弱势延续”与“结构修复”
2. `strong_repair` 下区分“全面修复”与“结构性切换”
3. CP / 趋势都引入“主线簇优先于单票直觉”的解释和排序框架

## 9.4 对路线图本身的优化建议

为了让这份文档后续更像“工程驾驶舱”而不只是长说明，建议固定保留三块：

1. **已完成**
   - 只写已经进代码、可运行、可验证的改动
2. **进行中**
   - 只写已经开始但还没完全闭环的事项
3. **证据样本**
   - 用最近 3-5 个关键交易日说明为什么这个方向值得继续做

这样后面每次更新时，我们就能更快判断：
- 是基础设施问题
- 是环境门控问题
- 还是主线簇排序问题

## 9.3 技术路线对比（当前结论）

1. `hard_rules`
   - 适合：主入口触发、环境门控、批量回放
   - 优点：快、稳、可验证
   - 缺点：语义僵硬，容易误伤强修复日

2. `regime_cluster_statistics`
   - 适合：trend / reversal 排序增强
   - 优点：能把环境与主线簇历史表现喂回当日排序
   - 缺点：依赖样本量，需要持续补样本和做消融

3. `intraday_confirmation_0935`
   - 适合：盘中确认层、翻案层
   - 优点：更贴近执行，能修正 09:25 的保守误判
   - 缺点：不能替代盘前决策，依赖分时数据完整性

4. `ai_semantic_interpretation`
   - 适合：文案解释、lesson/pattern 沉淀、方法论升级
   - 优点：能处理上下文和子类型表达
   - 缺点：直接接管排序会慢且不稳，因此当前更适合做 assist 层而不是 core 层
