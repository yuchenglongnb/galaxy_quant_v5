# 数据接口指南

本文根据 `docs/legacy/开发手册.pdf`、`test_api.py` 和当前代码整理 AmazingData SDK 的项目内使用方式。原始接口定义以 PDF 开发手册为准。

## 环境

推荐环境：

```powershell
C:\Users\40857\.conda\envs\amazing\python.exe
```

项目依赖：

- `AmazingData`
- `pandas`
- `numpy`
- `scipy`
- `tgw`

不要使用当前 base 环境直接跑项目；base 环境曾出现 pandas/numpy/scipy 二进制版本不一致。

## 登录和登出

代码位置：

- `runners/base.py`
- `config/settings.py::DBConfig`

用法：

```python
import AmazingData as ad

ad.login(
    username=DBConfig.USERNAME,
    password=DBConfig.PASSWORD,
    host=DBConfig.IP,
    port=DBConfig.PORT,
)

ad.logout(DBConfig.USERNAME)
```

所有 Runner 都通过 `BaseRunner.__enter__()` 自动登录，通过 `__exit__()` 自动登出。

## 基础数据接口

代码位置：

- `core/data_manager.py::get_stock_list`
- `core/data_manager.py::get_name_map`

用途：

| 接口 | 用途 |
| --- | --- |
| `ad.BaseData().get_code_list(security_type='EXTRA_STOCK_A')` | 获取 A 股代码列表 |
| `ad.InfoData().get_stock_basic(codes)` | 获取股票名称等基础信息 |
| `ad.InfoData().get_history_stock_status(...)` | 获取历史涨跌停价和昨收价 |

注意：

- 不建议用实时 `get_code_info()` 给历史日期补 `pre_close`。
- 历史日期应优先使用历史状态接口或多日 `close.shift(1)`。

## 行业数据接口

代码位置：

- `core/data_manager.py::get_industry_codes`
- `core/data_manager.py::get_industry_map`
- `core/data_manager.py::fetch_industry_daily`

用途：

| 接口 | 用途 |
| --- | --- |
| `ad.InfoData().get_industry_base_info(is_local=False)` | 获取行业指数和层级 |
| `ad.InfoData().get_industry_constituent(index_codes, is_local=False)` | 获取行业成分股 |
| `ad.InfoData().get_industry_daily(index_codes, begin_date, end_date)` | 获取行业指数日行情 |

项目约定：

- 行业成分用于构建 `stock -> industry` 映射。
- `industry_daily.csv` 是可选增强数据，不阻塞日常同步主流程。
- 自定义概念可通过 `custom_concepts.csv` 覆盖行业映射。

## K 线接口

代码位置：

- `core/data_manager.py::_fetch_batch_kline`
- `core/data_manager.py::_fetch_batch_minute_kline`
- `core/data_manager.py::_fetch_indices_with_preclose`

日线：

```python
ad_market.query_kline(
    code_list,
    begin_date,
    end_date,
    ad.constant.Period.day.value,
)
```

分钟 K：

```python
ad_market.query_kline(
    code_list,
    begin_date,
    end_date,
    ad.constant.Period.min1.value,
)
```

项目内字段：

| 字段 | 含义 |
| --- | --- |
| `open` | 开盘价，复盘竞价口径下等同集合竞价价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价或分钟结束价 |
| `volume` | 成交量 |
| `amount` | 成交额 |
| `kline_time` | K 线日期或分钟时间 |

分钟 K 注意事项：

- 9:25 集合竞价可能没有独立分钟 K。
- 开盘集合竞价成交量通常包含在 9:30 第一根分钟 K 中。
- 收盘集合竞价成交量通常包含在最后一根分钟 K 中。
- 分钟 K 获取全市场股票很慢，默认不在日常同步中拉取。
- 9:30 第一根分钟 K 的 `amount` 不是纯竞价成交额，只能作为降级数据。

## 快照接口

代码位置：

- `core/data_manager.py::_fetch_batch_snapshot`
- `test_api.py::test_query_snapshot`

用法：

```python
ad_market.query_snapshot(
    code_list=code_list,
    begin_date=target_date,
    end_date=target_date,
    begin_time=92500000,
    end_time=92500000,
)
```

时间格式：

| 场景 | 格式 | 示例 |
| --- | --- | --- |
| 快照 | `HHMMSS000` | `92500000` 表示 09:25:00.000 |
| 分钟 K 筛选 | `HHMM` | `930` 表示 09:30 |

适用：

- 查询历史某一时点快照。
- 9:25 后若快照已入库，可用于竞价数据。

风险：

- 当天 9:25 刚结束时，历史快照可能未入库。
- 实时盘前更推荐订阅模式。

竞价成交额口径必须区分：

| `auction_source` | 是否精确 | 用途 |
| --- | --- | --- |
| `subscription_925` | 是 | 09:25 实时决策 |
| `historical_snapshot_925` | 是 | 历史复盘或订阅降级 |
| `minute_930_includes_first_minute` | 否 | 09:30 后观察，不用于严格 09:25 决策 |
| `daily_amount_estimated` | 否 | 最后兜底，仅用于观察 |

## 实时订阅接口

代码位置：

- `core/realtime_fetcher.py`
- `core/data_manager.py::_fetch_auction_subscribe`
- `test_api.py::test_subscribe`

用法概要：

```python
sub_data = ad.SubscribeData()
sub_data.subscribe_snapshot(code_list, callback=on_snapshot)
```

适用：

- 9:25 盘前实时竞价决策。
- 需要实时拿到最新快照，避免历史快照入库延迟。

项目入口：

```powershell
python main.py auction -r -s --sync
```

## 项目数据获取策略

竞价数据优先级：

```text
实时订阅
  -> 历史快照
  -> 分钟 K 第一根
  -> 日线 open / 日线估算
```

复盘模式：

- 默认使用日线 `open` 作为竞价价。
- 只有明确需要更细口径时才拉 `stocks_auction.csv`。

实时模式：

- 推荐 `auction -r -s --sync`。
- 如果订阅不可用，优先尝试 09:25 历史快照。
- 9:30 第一根分钟 K 和日线估算只作为显式降级数据。

## 常见接口问题

| 问题 | 可能原因 | 处理 |
| --- | --- | --- |
| `login fail` | 网络、服务端、IP/端口不可达 | 检查网络和 `DBConfig.IP/PORT` |
| `PushImpl wss client connect fail` | TGW 推送服务连接失败 | 重试或切换网络 |
| 快照为空 | 当天数据未入库 | 用订阅模式或稍后重试 |
| 分钟 K 卡住 | 全市场分钟接口慢 | 只拉 `--minute=auction`，不要默认全拉 |
| `pre_close` 异常 | 用了实时昨收补历史数据 | 使用历史状态接口或 shift |
| pandas/numpy ABI 错误 | Python 环境混装 | 使用 `amazing` conda 环境 |

## API 测试脚本

`test_api.py` 是接口探针脚本，不是单元测试。它覆盖：

- 登录。
- `get_code_list` / `get_stock_basic`。
- `query_snapshot`。
- `query_kline`。
- `SubscribeData`。

运行前确认使用 `amazing` 环境。
