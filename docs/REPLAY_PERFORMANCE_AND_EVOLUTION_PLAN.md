# 复盘性能与策略演进路线图

更新时间: 2026-06-16

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
- [ ] `shrinking_volume_trend_continuation` 的 continuation 子环境识别与 CP 豁免
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

## 9.2.5 20260616 新观察

1. 当天不是放量强修复，也不是高位兑现主导，而是“缩量但趋势延续”。
2. 验证结果显示：
   - CP 风险 `23 -> 5`，胜率约 `21.74%`
   - 反核机会 `8 -> 7`，胜率约 `87.50%`
   - 趋势机会 `108 -> 76`，胜率约 `70.37%`，平均实体为正
3. 这说明在主线簇没有瓦解、指数整体不转弱时，机械 CP 很容易误伤主线延续样本。
4. 当天更适合的交易语言是：
   - 可以做结构，不适合做普涨
   - 可以跟主线，不适合靠 CP 去反向猜顶
   - 低开承接比高开兑现更有效
5. 因此后续优先级应进一步明确为：
   - CP 加 `leading_cluster` 豁免
   - 趋势候选继续按 ETF 相对强弱、指数相对强弱、主线簇强度压缩
   - 反核只保留主线低开承接，不做弱板块普反
6. 今天还有一个数据层问题需要单独记住：
   - `20260616` 暴露出的根因不是“收盘后一定拿不到 close”，而是 same-day `session_state` 之前按固定时间粗糙判断
   - A 股应以 **15:00 以后** 进入收盘态判断，港股应以 **16:00 以后** 进入收盘态判断
   - 即使 sidecar 还写着 `intraday`，本地复盘链路也需要一层 `close finalization` 兜底，把已过本地收盘时点的 same-day cache 视为 `closed`

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

## 9.4 下一步最值得做（实施顺序）

1. `close_finalization`
   - 状态：已开始落地
   - 目标：same-day cache 在本地过了对应市场收盘时点后，不再因为 sidecar 仍是 `intraday` 而阻塞复盘
   - 代码入口：`core/data_manager.py`
   - 验证方式：A 股 15:00 后 / 港股 16:00 后，`get_daily_cache_status()` 应返回 `closed`

2. `cp_leading_cluster_exemption`
   - 目标：把“老高位兑现”和“新主线加速”拆开，避免 CP 机械打掉真正的 leading cluster
   - 第一版做法：只在 `continuation` / `strong_repair` / `shrinking_volume_trend_continuation` 里生效
   - 触发条件：`theme_cluster_bonus > 0` 或 `group_regime_bonus > 0`，且属于当日主线簇
   - 输出要求：在 shortlist 里明确标注 `cp_exempt_by_leading_cluster`

3. `trend_three_stage_filter`
   - 目标：把趋势候选从“分数 TopK”收敛成“相对 ETF 强、相对指数强、属于主线簇”的少量候选
   - 三层顺序：
     - 个股相对所属 ETF 强弱
     - ETF / 行业相对指数强弱
     - leading cluster 持续性
   - 第一版结果要求：
     - 主报告只保留极少数 actionable 候选
     - 其余进入 `trend_observation`
     - 每个保留 / 剔除都要有 explain 字段

4. `regime_cluster_panel`
   - 目标：累计按环境分层的长期胜率面板，回答“什么环境下该开趋势、什么环境下只看承接修复”
   - 主要输入：`auction_signal_metrics.csv`、daily validation、pattern registry
   - 作用：后续给 CP 豁免和趋势过滤提供统计回灌，而不是只凭当天主观判断

## 9.5 20260618 补充样本结论

1. `20260618` 不是“全市场环境安全”，更像“广谱一般，但主线结构安全”。
2. 当天验证结果：
   - CP 风险 `11 -> 1`，胜率仅 `9.09%`
   - 反核机会 `10 -> 5`，胜率 `50%`
   - 趋势机会 `50 -> 42`，胜率 `84%`
3. 这说明：
   - 机械 CP 在强主线延续日会大面积误伤
   - 普反并不稳定，不能把低开自动翻译成可做反核
   - 真正高有效的是主线簇内的趋势延续
4. 因此后续统一改成双层环境表达：
   - `broad_env`: 回答“能不能大面积做多”
   - `structural_env`: 回答“能不能围绕主线集中做多”
5. 对应工程动作：
   - [x] 盘后 `Level 1` 拆成 `broad_env + structural_env`
   - [ ] 竞价侧后续也补齐同一套双层环境语言
   - [ ] trend 三重过滤继续优先围绕 leading cluster 收敛
## 10. Recent Snapshot Layer Progress

- `P1.0A` completed: iFinD market-structure snapshot layer is now normalized into:
  - `limitup_ladder_snapshot.csv`
  - `sector_strength_snapshot.csv`
  - `theme_limitup_distribution.csv`
- `P1.0B` completed in current working tree: market-structure evidence is now wired into `LeadingClusterEvidenceBuilder`
- current boundary is still strict:
  - enrich evidence only
  - do not change CP / trend / reversal shortlist decisions yet
- next planned step remains:
  - `P1.0C`: CP leading-cluster exemption

## 11. P1.0C Progress

- `P1.0C` is now implemented in the current working tree with a new `CPRiskEvaluator`
- current boundary remains tight:
  - only CP / trap candidates are re-layered
  - trend / reversal routing is unchanged
  - evaluator consumes only unified `leading_cluster_*` evidence and confirmation fields
  - evaluator does not read raw iFinD snapshot fields directly
- new CP decisions:
  - `hard_trap`
  - `crowded_observe`
  - `leading_cluster_exempt`
- shortlist behavior:
  - `hard_trap` stays in the main CP shortlist
  - `crowded_observe` is routed into `trap_observation`
  - `leading_cluster_exempt` is routed into `trap_exempted`
- initial evaluation artifacts added:
  - `reports/analysis/evaluations/cp_exemption_eval_20260616.{json,md}`
  - `reports/analysis/evaluations/cp_exemption_eval_20260618.{json,md}`
- current read on those two dates:
  - `20260616`: real iFinD snapshot exists, but no candidate reached `leading_cluster_exempt`; distribution was `hard_trap=19`, `crowded_observe=4`
  - `20260618`: still marked `pending validation` for real CP exemption effect because `AmazingData_Store/20260618/ifind/` is missing
- implication:
  - code path is ready for CP exemption
  - but real exemption quality still depends on completing dated iFinD snapshot coverage for replay dates
- next recommended step:
  - `P1.1`: trend triple gate
  - before that, preferably backfill one or more dated iFinD market-structure snapshots for key replay days such as `20260618`

## 12. P1.0C-R Snapshot Validation

- `P1.0C-R` is now partially completed:
  - `relative_strength_partially_unverified` has been tightened to trigger when either key relative-strength leg is missing
  - `CPRiskEvaluator` now also accepts `cp_score` as a compatible alias
  - snapshot validation has been upgraded from "ifind folder exists" to "required market-structure files are actually present"
- new evaluation artifacts:
  - `reports/analysis/evaluations/leading_cluster_evidence_eval_20260616.{json,md}`
  - `reports/analysis/evaluations/leading_cluster_evidence_eval_20260618.{json,md}`
  - `reports/analysis/evaluations/cp_exemption_eval_20260608.{json,md}`
  - `reports/analysis/evaluations/cp_exemption_eval_20260609.{json,md}`
  - `reports/analysis/evaluations/cp_exemption_real_snapshot_summary.{json,md}`
- current snapshot-readiness conclusion:
  - `20260616`: `partial` snapshot, only `sector_strength_snapshot.csv` exists; `theme_limitup_distribution.csv` and `limitup_ladder_snapshot.csv` are missing
  - `20260618`: `missing` snapshot, no dated `ifind` market-structure directory
  - `20260609`: `missing` snapshot
  - `20260608`: `missing` snapshot
- current methodological conclusion:
  - no real `leading_cluster_exempt` sample has been validated yet
  - this is currently explained more by missing dated market-structure evidence than by evaluator over-constraint
  - `crowded_observe` has started to separate "do not mechanically call it a trap" from `hard_trap`, but the exemption branch still lacks real replay coverage
- gating recommendation remains:
  - do **not** move directly to trend active gate
  - next safest order is:
    - backfill dated iFinD market-structure snapshots for key replay dates
    - rerun CP exemption validation
    - then enter `P1.1A` trend triple gate in shadow mode

## 13. P1.0C-R2A Sector Breadth Primary Path

- update date: `2026-06-20`
- decision:
  - full limit-up ladder detail is no longer a hard prerequisite for the next phase
  - iFinD `sector strength + breadth + money flow` becomes the primary replay-evidence path
  - full ladder stays as an optional enhancement for later

### 13.1 New readiness semantics

- `full_ready`
  - `sector_strength_snapshot.csv`
  - `theme_limitup_distribution.csv`
  - `limitup_ladder_snapshot.csv`
- `sector_breadth_ready`
  - dated `sector_strength_snapshot.csv` exists
  - snapshot includes `limitup_count`
  - snapshot includes `net_active_buy_yuan` or `dde_net_buy_yuan`
- `sector_only_partial`
  - dated `sector_strength_snapshot.csv` exists
  - but breadth or money-flow fields are still missing
- `missing`
  - no dated sector snapshot is available

### 13.2 New primary evidence flags

- `sector_breadth_strength_confirmed`
- `sector_limitup_breadth_confirmed`
- `sector_money_flow_confirmed`

These now support `leading_cluster_evidence` even when theme diffusion or full ladder detail is unavailable.

### 13.3 Strategy implication

- CP exemption no longer waits for full ladder detail before becoming evaluable
- `crowded_observe` and later trend shadow mode can rely on:
  - sector strength
  - sector breadth
  - sector money flow
  - existing relative-strength checks
- full ladder remains useful for:
  - core-member confirmation
  - detailed theme diffusion
  - higher-confidence exemptions

### 13.4 Next order of work

1. keep `sector_breadth_ready` as the main replay-valid state
2. rerun CP exemption evaluation on dated sector-breadth snapshots
3. enter `P1.1A` trend triple gate in shadow mode
4. treat full limit-up ladder as `P1.0D` optional enhancement, not a blocker

### 13.5 20260616 rebuild result

- `P1.0C-R2B` has now been validated on `20260616`
- we rebuilt a dated sector snapshot with:
  - `pct`
  - `turnover_rate`
  - `limitup_count`
  - `dde_net_buy_yuan`
  - `member_count`
  - `amount_yuan`
- current outcome:
  - `snapshot_status = sector_breadth_ready`
  - `real_snapshot_missing = false`
  - `full_snapshot_missing = true`
  - `leading_cluster_market_structure_hit_rate = 2.88%`
  - `CP decision distribution = hard_trap 18 / crowded_observe 5 / leading_cluster_exempt 0`
- interpretation:
  - the blocker has moved from "snapshot unavailable" to "evidence still not strong enough for full exemption"
  - this is sufficient to begin `P1.1A` in shadow mode because the replay path now has sector-breadth evidence and non-zero market-structure hit rate

### 13.6 P1.0C-R2C Cluster Matching And Stale Overlay Guard

- update date: `2026-06-20`
- status: completed in current working tree

#### What changed

1. added `sector_alias_map` into `reports/analysis/configs/leading_cluster_config.json`
2. expanded `LeadingClusterEvidenceBuilder` matching so structural groups can hit dated sector breadth through aliases
3. added stale-overlay guard:
   - stale overlay concepts are deprioritized
   - `group` / `theme_cluster` matches with dated market-structure evidence are preferred
4. adjusted stale handling semantics:
   - keep `stale_ifind_snapshot` when no dated market-structure hit exists
   - allow `active` / `partial` when stale overlay is overridden by dated sector breadth
   - preserve `stale_ifind_snapshot` as a risk flag for auditability

#### Why this mattered

- the main blocker was no longer missing sector breadth
- it was mismatched naming and stale overlay hijacking primary-cluster selection
- the representative bad case was:
  - `603986.SH 兆易创新`
  - `group = 数字芯片设计`
  - previously resolved to `leading_cluster_name = 机器人`
  - now correctly resolves to `leading_cluster_name = 半导体`

#### 20260616 re-evaluation result

- `snapshot_status = sector_breadth_ready`
- `leading_cluster_status_distribution` now includes:
  - `active = 4`
  - `stale_ifind_snapshot = 1`
- `CP decision distribution` is now:
  - `hard_trap = 18`
  - `crowded_observe = 4`
  - `leading_cluster_exempt = 1`

#### Interpretation

- this is the first real sign that sector-breadth evidence is strong enough to support leading-cluster exemption without full ladder detail
- the system has now moved from "data unavailable" into "evidence quality and threshold calibration"
- next safest step remains:
  - `P1.1A: Trend Triple Gate shadow mode`
  - do not switch trend gate to active mode yet

### 13.7 P1.1A Trend Triple Gate Shadow Mode

- update date: `2026-06-20`
- status: completed in current working tree

#### What changed

1. added `analyzers/evaluators/trend_triple_gate.py`
2. added `reports/analysis/configs/trend_triple_gate_config.json`
3. added `reports/analysis/schemas/trend_triple_gate.schema.json`
4. `SignalShortlistBuilder` now appends shadow-only fields on trend candidates:
   - `trend_gate_decision_shadow`
   - `trend_gate_score_shadow`
   - `trend_gate_reasons`
   - `trend_gate_missing_fields`
   - `trend_gate_risk_flags`
   - `trend_gate_context`
5. current active routing is unchanged:
   - `trend_filter_decision`
   - `shortlist["trend"]`
   - `shortlist["trend_observation"]`
   are all preserved

#### 20260616 shadow result

- trend candidate total: `108`
- existing `TrendCandidateFilter` distribution: `keep = 108`
- shadow distribution:
  - `main = 0`
  - `observe = 107`
  - `drop = 1`
- consistency ratio against current active filter: `0.0`

#### Interpretation

- this is not a shadow failure; it is a data-status finding
- `20260616` trend candidates are dominated by:
  - missing `09:35` relative-strength fields
  - missing benchmark ETF/index mapping
  - partial leading-cluster coverage outside the small iFinD overlay subset
- the current shadow output is therefore best read as:
  - active trend filter is still permissive under `degraded_global_missing`
  - triple gate is correctly surfacing that most candidates do not yet have enough confirmation to be promoted to `main`

#### Next recommendation

- do **not** move into `P1.1B active mode` yet
- next most valuable step is:
  - improve benchmark ETF / index mapping and post-open relative-strength coverage
  - then rerun the same shadow audit on dates like `20260616`, `20260618`, `20260609`

### 13.8 P1.1A-R1 Trend Gate Coverage Audit And Confirmation Repair

- update date: `2026-06-20`
- status: completed in current working tree

#### What changed

1. added `scripts/diagnose_trend_gate_coverage.py`
2. added a small benchmark fallback writeback in `AuctionAnalyzer`:
   - when `stock_confirmation_latest.csv` is unavailable,
   - stock trend signals now still inherit `benchmark_etf_code / benchmark_index_code`
   - from `watchlists/group_benchmark_map.csv`
3. added focused tests for:
   - trend-gate coverage blocker classification
   - benchmark fallback writeback without confirmation data

#### 20260616 diagnosis result

- `trend_total = 108`
- `target_type_distribution = {'stock': 101, 'industry': 5, 'index': 1, 'ETF': 1}`
- `intraday_dir_exists = false`
- `confirmation_available = false`
- `signal_enriched_count = 0`
- `benchmark_fallback_attached_count = 19`
- overall coverage:
  - `rs_vs_etf_coverage = 0.0`
  - `rs_vs_index_coverage = 0.0`
  - `amount_1m_ratio_coverage = 0.0`
  - `benchmark_etf_coverage = 0.1759`
  - `benchmark_index_coverage = 0.1759`
  - `mapped_benchmark_etf_potential = 0.1944`
  - `mapped_benchmark_index_potential = 0.1944`
- shadow still shows:
  - `main = 0`
  - `observe = 107`
  - `drop = 1`

#### Interpretation

- the benchmark layer was part of the blindness, but not the primary blocker
- after fallback writeback, mapped stock groups such as:
  - `数字芯片设计`
  - `印制电路板`
  - `消费电子零部件及组装`
  - `证券`
  now carry benchmark codes even without confirmation cache
- however, `shadow main` is still zero because the true bottleneck is unchanged:
  - `rs_vs_etf_pct`
  - `rs_vs_index_pct`
  - `amount_1m_ratio`
  are all missing on `20260616`
- the new blocker distribution confirms this directly:
  - `relative_strength_unverified = 108`

#### Main conclusion

- `P1.1A` has now moved from “shadow gate is too strict?” to a much clearer answer:
  - the triple gate is behaving as intended
  - the confirmation layer is missing for the replay date
  - benchmark mapping is no longer the first-order explanation

#### Next safest step

- do **not** enter `P1.1B active mode`
- next step should be:
  - `P1.1A-R2: benchmark / confirmation coverage repair`
  - with priority on rebuilding or backfilling the `09:35` relative-strength inputs
  - not on relaxing trend-gate thresholds

## 13.9 P1.1A-R2 Intraday Confirmation Backfill And Join Repair

- update date: `2026-06-21`
- status: in progress

### What changed

1. added `scripts/diagnose_intraday_confirmation_backfill.py`
2. added `scripts/backfill_intraday_confirmation.py`
3. added board-index fallback into `IntradayConfirmationBuilder`
4. benchmark fallback now distinguishes:
   - `group_benchmark_map`
   - `board_index_fallback`
   - `default_index_fallback`
5. board-index fallback now carries:
   - `benchmark_source`
   - `benchmark_fallback_level`
   - `board_index_code`
   - `board_index_name`
   - `board_index_fallback_used`
   - `benchmark_fallback_reason`

### Board-Index Fallback Rule

- fallback only writes `benchmark_index_code`
- fallback never writes `benchmark_etf_code`
- current code-prefix mapping:
  - `60xxxx.SH -> 000001.SH`
  - `000/001/002xxxx.SZ -> 399001.SZ`
  - `300xxxx.SZ -> 399006.SZ`
  - `688xxxx.SH -> 000688.SH`
  - `8/4xxxxx.BJ -> 899050.BJ`

### 20260616 Current Diagnosis

- `trend_total = 108`
- `stock_trend_total = 101`
- `intraday_dir_exists = false`
- `confirmation_available = false`
- `signal_enriched_count = 0`
- `missing_stock_intraday_count = 101`
- `missing_benchmark_etf_intraday_count = 3`
- `missing_benchmark_index_intraday_count = 4`
- `benchmark_index_coverage = 0.9352`
- `board_index_fallback_coverage = 0.7407`
- `rs_vs_index_coverage = 0.0`
- `amount_1m_ratio_coverage = 0.0`

### Interpretation

- benchmark fallback is no longer the main blocker
- board-index fallback now gives most stock trend candidates a reasonable index reference
- but `shadow main` still cannot rise because the replay date still lacks real `09:35` confirmation cache
- current blocker remains:
  - no `intraday/` cache
  - no `stock_confirmation_latest.csv`
  - no `rs_vs_etf_pct / rs_vs_index_pct / amount_1m_ratio`

### Next Step

- run `scripts/backfill_intraday_confirmation.py --date 20260616 --execute`
- then rerun:
  - `scripts/diagnose_trend_gate_coverage.py --date 20260616`
  - `scripts/evaluate_trend_triple_gate.py --date 20260616`
- do **not** enable active trend gate before:
  - `confirmation_available = true`
  - `signal_enriched_count > 0`
  - `rs_vs_index_coverage > 0`
  - `amount_1m_ratio_coverage > 0`

## 13.10 P1.1A-R2B Intraday Backfill Narrow Execute And Stage Isolation

- update date: `2026-06-21`
- status: base isolation complete, execute still blocked at `index_min1`

### What changed

1. `scripts/backfill_intraday_confirmation.py` now supports:
   - `--stage index|etf|stock|confirmation|all`
   - `--max-stocks`
   - `--only-codes`
   - `--begin-time`
   - `--end-time`
   - `--batch-size`
   - `--skip-existing`
2. `DataManager.rebuild_intraday_confirmation_from_snapshot(...)` now passes through stage-isolation arguments.
3. `IntradayMonitor.rebuild_opening_session_from_snapshot(...)` now supports:
   - stage-isolated execution
   - narrowed stock universe
   - server-side minute-window query
   - per-stage / per-batch progress logging
4. minute replay now prefers server-side time slicing:
   - `begin_time=930`
   - `end_time=935`
   instead of pulling full-day `min1` first and trimming locally.

### 20260616 Dry-Run Result

- `index` dry-run: success
- `stock` dry-run with `--max-stocks 10`: success
- evaluation artifacts generated:
  - `reports/analysis/evaluations/intraday_confirmation_backfill_20260616_index_dry_run.json`
  - `reports/analysis/evaluations/intraday_confirmation_backfill_20260616_stock_dry_run.json`

### 20260616 Execute Result

- `index` stage execute with all 4 replay indices still timed out
- single-code execute attempts also timed out:
  - `000001.SH`
  - `000688.SH`
  - `399001.SZ`
  - `399006.SZ`
- no `indices_1min.csv` or `stock_confirmation_latest.csv` was written

### Current Interpretation

- the execute blocker is now much narrower:
  - not the full replay universe
  - not stock breadth
  - not benchmark mapping
- the blocker is now the `AmazingData historical index min1 query` shape itself under replay backfill
- because all four replay indices timed out even when isolated one-by-one, the next debugging target is:
  - query lifecycle before the first batch returns
  - whether index `query_kline(min1)` hangs before any rows are emitted

### What we improved for the next round

- batch-start events are now logged **before** `query_kline(...)` is called
- this means that even if the external query hangs, progress logs now preserve:
  - stage
  - batch code list
  - requested time window
- next replay attempt can therefore identify the last in-flight batch without inference

### Next Safest Step

- keep `P1.1B active mode` disabled
- next step should remain:
  - isolate `index_min1` replay from the rest of the chain
  - verify whether ETF/stock stages can execute independently once index is skipped or prefilled
  - only after confirmation cache exists, rerun trend-gate coverage and shadow evaluation

## 13.11 P1.1A-R2C Fix query_kline Time Parameter Encoding

- update date: `2026-06-21`
- status: completed

### New diagnosis

- `index_min1` timeout is no longer best explained by replay universe size
- the stronger candidate root cause is now:
  - `query_kline(begin_time/end_time)` was using snapshot-style time encoding
  - example:
    - `930 -> 93000000`
    - `935 -> 93500000`
- this format matches `query_snapshot` millisecond windows, but is likely wrong for historical `query_kline`
- replay should first validate:
  - `query_kline(begin_time=930, end_time=935)`
  - before considering index replay bypass or synthetic fallback

### Required code split

- snapshot time encoding:
  - `HHMMSS * 1000`
- kline time encoding:
  - `HHMM`

### Verification path

1. keep `query_snapshot` encoding unchanged
2. fix `query_kline` to pass:
   - `begin_time=930`
   - `end_time=935`
3. add a dedicated probe comparing:
   - no window
   - HHMM window
   - snapshot-like window
4. rerun:
   - index single-code backfill
   - full replay index stage
   - then stock / confirmation chain

### Guardrail

- do **not** jump to `skip index replay` until HHMM-style `query_kline` has been tested

### 20260616 Probe Result

- probe target:
  - `000001.SH`
- observed from progress log:
  - `no_window` query returned `240` rows
  - `hhmm` query with `begin_time=930, end_time=935` returned `6` rows
  - `snapshot_like` query with `93000000 / 93500000` timed out

### Updated interpretation

- the original `query_kline` time-encoding bug was real
- `HHMM` is the correct direction for `query_kline`
- but after fixing time encoding, `backfill_intraday_confirmation.py --stage index --only-codes 000001.SH` still hangs inside:
  - `index_min1_batch start`
- this means the remaining blocker is no longer just parameter shape
- next suspicion should move to:
  - replay backfill bootstrap / client lifecycle path
  - differences between the successful probe path and the hanging backfill path

## 13.12 P1.1A-R2D Unify AmazingData Bootstrap Path for Intraday Backfill

- update date: `2026-06-21`
- status: completed

### What changed

1. added a shared helper:
   - `core/amazing_kline_query.py::query_min1_kline_once(...)`
2. the helper now uses the same bootstrap lifecycle as the successful probe path:
   - `bootstrap_amazingdata_client()`
   - `CalendarHelper.generate_workday_calendar(...)`
   - `ad.MarketData(calendar)`
   - `query_kline(..., begin_time=930, end_time=935)`
3. `IntradayMonitor` and `DataManager` now support:
   - `isolated_query=True`
4. `scripts/backfill_intraday_confirmation.py` now supports:
   - `--isolated-query`
5. isolated-query replay keeps query bootstrap close to probe behavior instead of relying on the long-lived shared client path

### 20260616 empirical result

- isolated-query fixed the replay `index_min1` blocker
- index single-code replay succeeded:
  - `000001.SH`
  - `row_count = 6`
- full replay index stage also succeeded for the four board / market benchmarks:
  - `000001.SH`
  - `000688.SH`
  - `399001.SZ`
  - `399006.SZ`
- stock small-universe replay with `--max-stocks 10` succeeded
- replay generated:
  - `indices_1min.csv`
  - `stocks_1min.csv`
  - `stock_confirmation_latest.csv`
  - `stock_confirmation_history.csv`

### 20260616 confirmation coverage after isolated-query replay

- `intraday_dir_exists = true`
- `confirmation_available = true`
- `signal_enriched_count = 10`
- `rs_vs_index_coverage = 0.0926`
- `amount_1m_ratio_coverage = 0.0926`
- `rs_vs_etf_coverage = 0.0`
- `benchmark_index_coverage = 0.9352`
- `benchmark_etf_coverage = 0.1759`
- `board_index_fallback_coverage = 0.6574`

### 20260616 trend shadow result after replay

- `TrendTripleGate shadow distribution`:
  - `observe = 102`
  - `drop = 6`
  - `main = 0`
- the bottleneck has moved:
  - from `no confirmation cache`
  - to `partial confirmation coverage`
- current blocking reasons are now dominated by:
  - `relative_strength_unverified`
  - plus a small set of `weak_vs_index`

### Updated interpretation

- the `query_kline` time-encoding bug is fixed
- the replay backfill path can work when it uses the same isolated bootstrap lifecycle as the successful probe path
- the remaining issue is no longer `AmazingData historical index min1 unavailable`
- the remaining issue is replay coverage breadth:
  - too few stock confirmations written
  - no ETF-relative strength yet
  - shadow `main` still cannot lift above zero

### Guardrail

- keep `P1.1B active mode` disabled
- do **not** loosen trend thresholds to compensate for missing coverage
- next work should focus on expanding confirmation coverage, not changing strategy rules

## 13.13 P1.1A-R2E Expand Isolated Intraday Confirmation Coverage

- update date: `2026-06-24`
- status: completed

### What changed

1. `scripts/backfill_intraday_confirmation.py` now supports:
   - `--selection-priority original|leading_cluster|sector_positive|trend_score`
2. replay stock selection can now prefer:
   - `leading_cluster_status = active / partial`
   - sector-positive leading-cluster evidence
   - higher `action_score`
3. local expansion tracking is now written to:
   - `reports/analysis/evaluations/intraday_confirmation_expansion_20260616.json`
   - `reports/analysis/evaluations/intraday_confirmation_expansion_20260616.md`

### 20260616 expansion runs

- `30` stocks with `--selection-priority leading_cluster`
  - stock replay succeeded
  - confirmation rebuild succeeded
  - no slow batches
  - no failed batches
- `60` stocks with `--selection-priority leading_cluster`
  - stock replay succeeded
  - confirmation rebuild succeeded
  - no slow batches
  - no failed batches

### Coverage progression

- baseline isolated-query small set:
  - `signal_enriched_count = 10`
  - `rs_vs_index_coverage = 0.0926`
  - `amount_1m_ratio_coverage = 0.0926`
- after `30` prioritized stocks:
  - `signal_enriched_count = 30`
  - `rs_vs_index_coverage = 0.2778`
  - `amount_1m_ratio_coverage = 0.2778`
  - `rs_vs_etf_coverage = 0.0`
- after `60` prioritized stocks:
  - `signal_enriched_count = 60`
  - `rs_vs_index_coverage = 0.5556`
  - `amount_1m_ratio_coverage = 0.5556`
  - `rs_vs_etf_coverage = 0.0`

### Trend shadow progression

- baseline:
  - `observe = 102`
  - `drop = 6`
  - `main = 0`
- after `30` prioritized stocks:
  - `observe = 84`
  - `drop = 23`
  - `main = 1`
- after `60` prioritized stocks:
  - `observe = 77`
  - `drop = 30`
  - `main = 1`

### What the new result means

- the system has crossed an important boundary:
  - from `shadow main = 0`
  - to `shadow main > 0`
- this means `TrendTripleGate` is no longer blocked purely by missing confirmation cache
- the dominant remaining blocker is still:
  - `relative_strength_unverified`
- a second blocker is now becoming visible:
  - real `weak_vs_index` outcomes

### Updated interpretation

- `isolated_query` should be treated as the recommended replay backfill mode
- coverage expansion, not rule loosening, is the correct next lever
- board-index fallback is doing its job for index-side comparison
- ETF-relative strength remains the largest missing layer

### Guardrail

- keep `P1.1B active mode` disabled
- do **not** relax `TrendTripleGate` thresholds just because `rs_vs_etf_coverage` is still `0.0`
- next work should focus on:
  - expanding confirmation coverage further only if stability holds
  - or improving ETF-benchmark enrichment before any active gate decision
