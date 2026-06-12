# GalaxyQuant 整体架构

本文档用于说明项目的分层设计、模块边界和数据流。它是阅读其他专题文档的总入口。

## 1. 项目定位

GalaxyQuant 当前是一套围绕 A 股早盘竞价、盘中监控和盘后复盘的本地量化分析系统。

核心目标不是替代交易员判断，而是把每天的市场事实结构化：

- 竞价阶段：识别高开兑现风险、低开承接机会、强趋势机会。
- 盘中阶段：监控指数、ETF、重点股票池和概念方向的量价变化。
- 盘后阶段：验证信号成败，积累可用于调参和 AI 复盘的结构化样本。
- 长期阶段：让硬规则、AI解释和历史反馈形成闭环。

## 2. 总体分层

```text
命令入口层
  main.py
    -> sync / auction / review / monitor / qstock / status

运行编排层
  runners/
    sync.py      数据同步
    auction.py   竞价复盘与信号验证
    review.py    盘后全景复盘
    monitor.py   盘中实时监测
    qstock.py    辅助外部数据源命令

数据层
  core/
    data_manager.py      AmazingData 主数据链路、缓存、刷新判断
    data_processor.py    基础清洗与指标加工
    calendar_helper.py   交易日/工作日辅助
    intraday_monitor.py  盘中数据采集和状态管理
    realtime_fetcher.py  实时行情获取
  providers/
    ths_concept_provider.py  同花顺概念轻量数据源
    qstock_provider.py       qstock 辅助数据源，非主链路

分析与因子层
  analyzers/
    auction.py     竞价 CP/SA/趋势分析主流程
    factors.py     CP、SA、场景识别、报告解释模板
    strategy.py    盘后全景策略分析
    technical.py   技术形态辅助

AI 优化层
  ai/
    local_interpreter.py       本地规则解释器
    model_client.py            外部模型 API 客户端
    signal_interpreter.py      信号解释调度
    signal_feature_builder.py  AI 输入特征构造
    signal_labels.py           信号标签和子类型
    validator.py               AI 输出校验
    trace_logger.py            AI 调用轨迹

报告与验证层
  reports/
    formatters.py
    ai_traces/
    validation/
      auction_signal_validation.csv
      auction_signal_daily_summary.csv
      auction_signal_metrics.csv
      daily/YYYYMMDD/

配置层
  config/settings.py
    DBConfig / UniverseConfig / MarketConfig / AuctionConfig / AIReportConfig / MonitorConfig

自选池与本地数据
  watchlists/stock_pool.csv
  AmazingData_Store/YYYYMMDD/
  logs/
```

## 3. 核心数据流

### 3.1 同步数据流

```text
python main.py sync 5
  -> runners.sync.SyncRunner
  -> core.data_manager.DataManager
  -> AmazingData API
  -> AmazingData_Store/YYYYMMDD/
       stocks.csv
       indices.csv
       *.meta.json
       stocks_auction.csv / indices_auction.csv 可选
```

当前同步策略已经从“全市场全量分钟数据”转向“决策宇宙优先”：

- 股票日线默认以 `watchlists/stock_pool.csv` 为主。
- ETF 和主要指数作为板块与市场状态表达。
- 行业日线默认不再作为主链路同步。
- 分钟数据只建议拉取自选股、ETF、主要指数。

### 3.2 竞价复盘数据流

```text
python main.py auction
  -> runners.auction.AuctionRunner
  -> DataManager.ensure_daily_cache_for_analysis()
  -> analyzers.auction.AuctionAnalyzer.analyze()
       1. 加载股票和指数历史数据
       2. 计算 auction_pct / close_pct / body_pct / pos_5d / OAR
       3. 计算指数、ETF、自选股、板块 CP/SA
       4. 生成 trap / reversal / trend 信号
       5. 打印报告
       6. 保存验证记录和因子快照
```

复盘模式中，竞价价口径主要来自日线 `open`，盘后结果使用 `close`，实体涨跌幅使用：

```text
body_pct = (close - open) / prev_close * 100
```

这使得信号验证可以围绕“竞价后真实承接/兑现”展开。

### 3.3 盘中监测数据流

```text
python main.py monitor --summary
  -> runners.monitor.MonitorRunner
  -> core.intraday_monitor
  -> core.realtime_fetcher
  -> 盘中定时采集指数、ETF、重点标的
  -> logs/reports/YYYY/MM/DD/
```

盘中监测和竞价复盘共享部分标的池，但目标不同：

- 竞价复盘关注 9:25 开盘后的成败验证。
- 盘中监测关注交易时段内的异动、扩散、回落和风险提示。

## 4. 因子设计层

当前核心信号分三类：

| 类型 | 机器分类 | 主要含义 | 当前验证口径 |
|---|---|---|---|
| CP风险 | `trap` | 高开诱多、强势后兑现、拥挤兑现风险 | `body_pct < 0` |
| 反核机会 | `reversal` | 低开后被资金承接并修复 | `body_pct > 0` |
| 趋势机会 | `trend` | 非低开反核，而是强趋势延续 | `body_pct > 0` |

CP 和 SA 的完整设计见 [INDICATOR_DESIGN.md](INDICATOR_DESIGN.md)。

### 4.1 CP 风险

CP 用于刻画“竞价阶段已经显著消耗买盘、短线拥挤、后续容易兑现”的风险。

典型输入：

- 竞价涨幅 `auction_pct`
- 昨日涨幅 `prev_pct`
- 昨日实体 `prev_body_pct`
- 昨日量比 `prev_vol_ratio`
- 5 日位置 `pos_5d`
- 排名权重 `amt_rank`
- 市场 OAR `market_oar`

### 4.2 SA 反核

SA 用于刻画“低开后可能出现承接修复”的机会。

典型输入：

- 竞价低开幅度
- 竞价额或替代强度
- 排名权重
- 恐慌/低位系数
- 市场 OAR

### 4.3 趋势机会

趋势机会不是反核。它更关注高位或强势结构中，盘中继续走强的情况。

目前趋势机会仍以硬规则识别为主，后续更适合结合：

- 概念热度
- ETF/指数共振
- 个股在板块内的成交额排名
- 历史验证胜率
- AI 对结构语义的判断

## 5. 数据层

主数据源是 AmazingData，辅助数据源包括同花顺概念轻量接口和 qstock。

### 5.1 AmazingData 主链路

主链路负责：

- 交易日历
- 股票日线
- 指数和 ETF 日线
- 竞价/分钟数据
- 盘中实时数据

缓存目录：

```text
AmazingData_Store/YYYYMMDD/
  stocks.csv
  stocks.meta.json
  indices.csv
  indices.meta.json
  stocks_auction.csv
  indices_auction.csv
  ths/
```

`*.meta.json` 用于判断缓存是盘中态还是收盘态，避免盘中同步数据在盘后被误用。

### 5.2 股票池

股票池入口：

```text
watchlists/stock_pool.csv
```

当前设计倾向：

- 不再对全市场 5000 多只股票做重分钟同步。
- 维护约 100 到 200 只重点自选股。
- 结合 ETF、指数和同花顺概念表达板块状态。

### 5.3 ETF 和指数

ETF 和指数承担两个职责：

- 表征大类方向：宽基、科技、资源、消费、医药、金融等。
- 作为个股信号的外部环境参照。

配置入口：

```text
config/settings.py
  MarketConfig.MAIN_INDICES
  MarketConfig.THEME_ETFS
```

### 5.4 同花顺概念

同花顺概念主要用于增强股票池的主题归因。

当前项目不把“同花顺出海50、同花顺果指数、同花顺新质50”等宽泛指数型概念作为有效主题标签，而是更偏向：

- 人形机器人
- 新型工业化
- 算力
- 存储芯片
- 消费电子
- 固态电池

过滤规则见：

```text
config/settings.py
  ConceptConfig
```

## 6. AI 优化层

AI 不是直接替代数值计算，而是替代硬编码语义解释和复杂场景归纳。

当前边界：

- 数值事实仍由程序计算。
- AI 负责解释、归类、风险提示、复盘总结。
- AI 输出必须经过 `validator.py` 校验。
- API 慢或不可用时，本地解释器兜底。

运行模式：

```text
AI_REPORT_MODE=off      # 关闭 AI，只用模板
AI_REPORT_MODE=shadow   # 只记录 trace，不写入报告
AI_REPORT_MODE=assist   # AI/本地解释器参与报告
AI_REPORT_MODE=replace  # 预留，未来更强替代模式
```

AI 相关设计见：

- [AI_REPORTING_DESIGN.md](AI_REPORTING_DESIGN.md)
- [AI_HARD_CODE_EVOLUTION.md](AI_HARD_CODE_EVOLUTION.md)

## 7. 回测与验证层

验证层当前围绕每日竞价信号展开，目标是沉淀样本，后续优化阈值。

输出目录：

```text
reports/validation/
  auction_signal_validation.csv
  auction_signal_daily_summary.csv
  auction_signal_metrics.csv
  daily/YYYYMMDD/
    signal_detail.csv
    signal_summary.csv
    signal_metrics.csv
    factor_snapshot_index.csv
    factor_snapshot_etf.csv
    factor_snapshot_stock.csv
    factor_snapshot_industry_topk.csv
```

其中：

- `signal_detail.csv` 记录当天触发的信号。
- `signal_metrics.csv` 记录 CP风险、反核机会、趋势机会三类胜率。
- `factor_snapshot_*.csv` 记录全量因子快照，包含未触发样本。

完整设计见 [BACKTESTING_VALIDATION.md](BACKTESTING_VALIDATION.md)。

## 8. 盘中实时监测层

盘中监测负责在交易时间内持续采集市场状态。

入口：

```text
python main.py monitor --summary
python main.py monitor -d --summary
python main.py monitor --no-auction
```

当前适合监控：

- 四大指数
- 主题 ETF
- 自选股池
- 竞价信号标的后续走势
- 概念方向异动

详细说明见 [INTRADAY_MONITORING.md](INTRADAY_MONITORING.md)。

## 9. 推荐演进路径

### 阶段一：稳定数据与验证

- 保证日线缓存不会误用盘中态。
- 每天稳定生成 `factor_snapshot_*.csv`。
- 持续积累 CP/SA/趋势信号验证结果。

### 阶段二：阈值调优

- 用 `auction_signal_metrics.csv` 看整体胜率。
- 用 `factor_snapshot_stock.csv` 和 `factor_snapshot_etf.csv` 回看未触发样本。
- 对 CP/SA 阈值按市场环境、标的类型、5日位置分层调参。

### 阶段三：AI 语义替代

- 先让 AI 替代标题、文案、场景解释。
- 再让 AI 参与场景分类建议。
- 最后用历史验证数据反哺方法论和 skill。

### 阶段四：实时闭环

- 盘中记录竞价信号后续路径。
- 盘后自动把路径归档为案例。
- 用案例库增强 AI/RAG 的解释质量。

