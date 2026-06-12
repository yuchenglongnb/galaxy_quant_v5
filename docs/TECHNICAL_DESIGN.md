# 技术设计总览

本文档是 GalaxyQuant 的主架构文档。其他文档只保留专题细节，避免同一套逻辑散落在多处。

## 1. 项目目标

GalaxyQuant 是一套围绕 A 股早盘竞价、盘中监测和盘后复盘的本地量化分析系统。

当前核心目标：

- 用结构化数据描述每天的指数、ETF、自选股和板块状态。
- 用 CP/SA/趋势机会识别竞价后的风险与机会。
- 用每日验证和因子快照沉淀样本，后续用于阈值优化和 AI 解释进化。
- 用 AI 替代部分硬编码文案和复杂场景归纳，但不让 AI 替代底层数值计算。

## 2. 总体分层

```text
入口层
  main.py
    sync / auction / review / monitor / qstock / status

运行编排层
  runners/
    sync.py      数据同步
    auction.py   竞价复盘、报告输出、验证记录
    review.py    盘后全景复盘
    monitor.py   盘中实时监测
    qstock.py    辅助数据源命令

数据层
  core/
    data_manager.py      AmazingData 主链路、缓存、刷新判断
    data_processor.py    数据清洗和基础加工
    calendar_helper.py   日期和交易日辅助
    intraday_monitor.py  盘中采集流程
    intraday_confirmation.py  个股相对 ETF/指数强弱和分钟量价确认
    realtime_fetcher.py  实时数据获取
  providers/
    ths_concept_provider.py  同花顺概念轻量接口
    qstock_provider.py       qstock 辅助接口

因子分析层
  analyzers/
    auction.py     竞价分析主流程
    factors.py     CP、SA、场景识别、解释模板
    strategy.py    盘后全景策略
    technical.py   技术形态辅助

AI 优化层
  ai/
    local_interpreter.py
    model_client.py
    signal_interpreter.py
    signal_feature_builder.py
    signal_labels.py
    validator.py
    trace_logger.py

报告和验证层
  reports/
    validation/
    ai_traces/
  logs/

配置层
  config/settings.py
```

## 3. 核心运行链路

### 3.1 数据同步

```text
python main.py sync 5
  -> runners.sync.SyncRunner
  -> core.data_manager.DataManager
  -> AmazingData
  -> AmazingData_Store/YYYYMMDD/
```

当前同步策略已经从“全市场全量拉取”收敛为“决策宇宙优先”：

- 自选股池：`watchlists/stock_pool.csv`
- 主题 ETF 和宽基 ETF：`MarketConfig.THEME_ETFS`
- 主要指数：`MarketConfig.MAIN_INDICES`
- 同花顺概念：作为主题归因和后续增强数据

详细说明见 [DATA_LAYER.md](DATA_LAYER.md)。

### 3.2 竞价复盘

```text
python main.py auction
  -> AuctionRunner
  -> AuctionAnalyzer
  -> 指数/ETF/自选股/板块 CP-SA 因子
  -> 信号汇总
  -> 验证统计
  -> 因子快照 CSV
```

竞价复盘主要使用日线 `open` 作为竞价价口径，使用 `close` 做盘后验证。

关键字段：

```text
auction_pct = (open - prev_close) / prev_close * 100
close_pct   = pct
body_pct    = (close - open) / prev_close * 100
```

### 3.3 盘后复盘

```text
python main.py review
  -> ReviewRunner
  -> strategy.py
  -> A 股全景策略报告
```

盘后复盘偏“全景判断”，竞价复盘偏“早盘信号成败验证”。两者结论可能不同，原因是前者纳入了更完整的盘后信息。

### 3.4 盘中监测

```text
python main.py monitor --summary
python main.py monitor -d --summary
```

盘中监测关注交易时段内指数、ETF、自选股和信号标的的动态变化。

详细说明见 [OPERATIONS.md](OPERATIONS.md)。
量价确认层说明见 [INTRADAY_CONFIRMATION.md](INTRADAY_CONFIRMATION.md)。

## 4. 核心信号

当前竞价信号分三类：

| 类型 | 机器分类 | 含义 | 当前验证口径 |
|---|---|---|---|
| CP风险 | `trap` | 高开诱多、强势后兑现、拥挤兑现风险 | `body_pct < 0` |
| 反核机会 | `reversal` | 低开后承接修复 | `body_pct > 0` |
| 趋势机会 | `trend` | 强趋势延续 | `body_pct > 0` |

完整因子设计和验证文件见 [FACTOR_BACKTESTING.md](FACTOR_BACKTESTING.md)。

特征工程、机器学习和排序模型的演进方案见 [FEATURE_MODELING_ROADMAP.md](FEATURE_MODELING_ROADMAP.md)。
特征、环境和 TopK 的对照实验方案见 [ABLATION_STUDY_PLAN.md](ABLATION_STUDY_PLAN.md)。

## 5. 数据落盘

主数据：

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

日志：

```text
logs/
  sync/
  reports/YYYY/MM/DD/
```

验证和因子快照：

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

## 6. AI 边界

AI 层只负责解释、归类建议和方法论沉淀，不负责改写事实数据。

原则：

- 数值计算由程序完成。
- AI 输出必须经过校验。
- API 慢或失败时，本地解释器兜底。
- 关键结论要能回溯到输入特征和历史验证结果。

详细说明见 [AI_LAYER.md](AI_LAYER.md)。

## 7. 配置入口

主要配置集中在：

```text
config/settings.py
```

重要配置：

- `DBConfig`: AmazingData 登录、数据目录、批处理超时。
- `UniverseConfig`: 股票池、行业同步、分钟数据范围。
- `ConceptConfig`: 同花顺概念过滤。
- `MarketConfig`: ETF 和指数池。
- `AuctionConfig`: CP/SA 阈值。
- `AIReportConfig`: AI 模式、模型、超时、最大调用次数。
- `MonitorConfig`: 盘中监测频率和告警阈值。

## 8. 文档分工

当前根目录只保留主线文档：

```text
README.md                 文档入口
TECHNICAL_DESIGN.md       技术设计总览
DATA_LAYER.md             数据层和同步策略
FACTOR_BACKTESTING.md     因子设计与验证框架
AI_LAYER.md               AI 优化层
OPERATIONS.md             命令、日志、盘中监测和日常操作
```

历史调研、旧设计和资料放在：

```text
docs/reference/
docs/legacy/
```
