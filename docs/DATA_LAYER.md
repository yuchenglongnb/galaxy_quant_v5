# 数据层

本文档整合数据范围、同步策略、接口说明和辅助数据源。更细的历史调研放在 `reference/`。

## 1. 数据层目标

数据层要解决三个问题：

- 保证竞价和复盘使用的数据状态正确，避免盘中缓存污染盘后分析。
- 降低同步耗时，避免全市场分钟数据成为瓶颈。
- 用指数、ETF、概念和自选股池表达市场结构，而不是盲目拉取全市场所有数据。

## 2. 主数据源

主链路是 AmazingData。

主要职责：

- 股票日线
- 指数和 ETF 日线
- 竞价/分钟数据
- 实时订阅和快照
- 交易日缓存

核心代码：

```text
core/data_manager.py
core/data_processor.py
core/realtime_fetcher.py
core/calendar_helper.py
```

## 3. 本地缓存

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

`*.meta.json` 会记录：

```text
date_int
row_count
session_state   # intraday / closed
fetched_at
```

复盘时如果当天数据不是收盘态，会自动尝试刷新，避免盘中同步结果在盘后继续被误用。

## 4. 决策宇宙

当前不建议继续全市场分钟同步。

推荐宇宙：

- 自选股池：约 100 到 200 只重点股票。
- 主题 ETF：表达板块资金走势。
- 宽基指数：表达市场环境。
- 同花顺概念：表达热门主题归因。

配置入口：

```text
config/settings.py
  UniverseConfig
  MarketConfig
  ConceptConfig
```

股票池：

```text
watchlists/stock_pool.csv
```

## 5. 同步命令

日常同步：

```powershell
python main.py sync 5
```

只在明确需要时同步分钟数据：

```powershell
python main.py sync 5 --minute=auction
python main.py sync 5 --minute=noon
python main.py sync 5 --minute=close
python main.py sync 5 --minute=all
```

竞价复盘通常不需要分钟数据，因为可以使用日线 `open` 还原竞价价。

实时竞价决策需要严格区分成交额口径：

```text
09:25 订阅快照
  -> 纯竞价成交额，可用于 09:30 前决策

09:25 历史快照
  -> 纯竞价成交额，作为订阅降级

09:30 第一根分钟 K
  -> 竞价成交额 + 开盘后第一分钟成交额
  -> 只能用于观察，不能冒充纯竞价成交额
```

`stocks_auction.csv` 会写入 `auction_source`、`auction_amount_exact` 和 `auction_asof`，并生成 `stocks_auction.meta.json`。

## 6. ETF 和指数

配置位置：

```text
config/settings.py
  MarketConfig.THEME_ETFS
  MarketConfig.MAIN_INDICES
```

ETF 的作用：

- 替代粗粒度行业指数。
- 表征真实可交易板块方向。
- 为个股信号提供外部环境。

指数的作用：

- 判断市场状态。
- 判断信号是否处于强势、震荡或恶劣环境。

## 7. 同花顺概念

同花顺概念通过轻量 Provider 接入：

```text
providers/ths_concept_provider.py
```

用途：

- 给自选股增加主题归因。
- 过滤无效或过宽泛概念。
- 后续可参与 ETF/概念共振分析。

过滤配置：

```text
config/settings.py
  ConceptConfig.THS_EXCLUDE_EXACT
  ConceptConfig.THS_EXCLUDE_KEYWORDS
  ConceptConfig.THS_EXCLUDE_REGEX
```

## 8. qstock 定位

qstock 当前定位为辅助数据源，不进入主链路。

原因：

- 导入和请求阶段依赖公开网页源，网络和代理不稳定。
- 和 AmazingData 主链路耦合会影响核心复盘稳定性。

适合做：

- 实时行情降级。
- 问财股票池候选。
- 异动数据参考。
- 概念或辅助信息补充。

详细调研见 [qstock 调研](reference/QSTOCK_RESEARCH.md)。

## 9. 数据层后续优化

优先级从高到低：

1. 保证所有复盘数据都有收盘态 meta。
2. 把分钟数据范围限制在自选股、ETF、指数。
3. 给概念数据增加稳定的离线 CSV 导入。
4. 给个股增加 ETF/概念上下文字段。
5. 盘中监测结果和盘后验证结果打通。
