# 数据范围与同步策略

本文记录 GalaxyQuant 的数据拉取范围设计。核心原则是：全市场用于基准判断，交易决策用股票池、宽基指数和主题 ETF 表征，分钟数据只拉真正需要观察的标的。

## 目标

原同步链路的主要耗时来自三类数据：

- 全 A 个股日线：约 5523 只股票，分 10 批，每批约 5-6 秒，单日约 55 秒。
- 行业指数日线：约 511 个行业指数，单日同步明显偏慢。
- 全 A 分钟线：最新交易日串行拉 auction/noon/close，每组约 19 批，是最大卡点。

新的策略是：

- 个股日线只维护自选股票池，默认读取 `watchlists/stock_pool.csv`。
- 市场环境由主指数和宽基 ETF 表征。
- 板块资金由主题 ETF 表征，弱化行业指数日线依赖。
- 分钟数据只拉股票池、主题 ETF 和主指数，不再默认拉全市场。

## 配置入口

在 `config/settings.py::UniverseConfig`：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `STOCK_POOL_PATH` | `./watchlists/stock_pool.csv` | 自选股票池 |
| `USE_ALL_STOCKS_DAILY` | `False` | 是否恢复全市场个股日线 |
| `SYNC_INDUSTRY_DAILY` | `False` | 是否同步 511 个行业指数 |
| `MINUTE_INCLUDE_STOCK_POOL` | `True` | 分钟线包含股票池 |
| `MINUTE_INCLUDE_ETFS` | `True` | 分钟线包含主题 ETF |
| `MINUTE_INCLUDE_MAIN_INDICES` | `True` | 分钟线包含主指数 |

股票池 CSV 至少需要一列 `code`。支持 `000001.SZ`、`600519.SH` 这类完整代码，也支持 `000001`、`600519`，程序会自动补交易所后缀。

## 文件变化

日线：

- `stocks.csv`：股票池日线，不再必然是全 A。
- `indices.csv`：主指数 + 主题 ETF 日线。
- `industry_daily.csv`：默认不拉；需要时手动开启 `SYNC_INDUSTRY_DAILY`。

分钟：

- `stocks_auction.csv` / `stocks_noon.csv` / `stocks_close.csv`：股票池分钟数据。
- `indices_auction.csv` / `indices_noon.csv` / `indices_close.csv`：主指数和主题 ETF 分钟数据。

## 报告含义变化

开启股票池模式后，个股聚合类统计不再代表全市场，而代表“关注池”。因此：

- ETF 监控是板块方向的主要表达。
- 指数监控是市场环境的主要表达。
- 行业排行榜如果没有开启行业日线或没有全市场股票，不应被理解为全市场行业强弱。

后续建议把报告中的“行业竞价排行”逐步改名为“股票池概念/分组排行”，并用 `stock_pool.csv` 中的 `group` 字段做自定义分组。

## 超时与降级

批量拉取新增了 `DBConfig.BATCH_TASK_TIMEOUT_SECONDS`。如果某组分钟接口长时间没有任何批次完成，会取消剩余批次并继续后续流程，避免卡死在 `stocks_auction 0/19`。

## 外部实践参考

调研到的开源项目也多采用“按市场或标的列表拉取”的思路：

- qstock 的实时行情接口支持市场维度，也支持单个或多个证券代码列表，并区分 ETF、指数、行业板块、概念板块等市场入口。
- qstock 还提供同花顺概念板块、概念成分和概念指数行情，说明“概念/主题”经常比传统行业更贴近热点表达。
- Ashare 强调轻量接口、DataFrame 输出，以及新浪/腾讯双源自动切换，适合作为分钟/实时数据的降级思路参考。
- AKShare 的定位是统一金融数据接口，适合作为后续补充数据源或交叉校验源，而不是日常全量分钟同步的唯一依赖。
