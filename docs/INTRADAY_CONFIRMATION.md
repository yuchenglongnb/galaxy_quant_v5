# 盘中量价确认层

## 1. 目标

竞价短名单只使用 9:25 可见数据。开盘后执行确认层使用逐分钟快照继续筛选，避免把盘中或收盘结果泄漏到竞价候选生成阶段。

流程分为两段：

```text
9:25 竞价短名单
  -> CP 风险 / 反核机会 / 趋势机会
  -> 只使用 auction_pct、CP、SA、前一交易日量价、成交额排名

9:30-9:45 执行确认
  -> 个股相对 ETF 强弱
  -> 个股相对指数强弱
  -> 分钟成交额放大
  -> 量价方向一致性
```

## 2. 数据落盘

运行：

```powershell
python main.py monitor --summary
```

实时监控每分钟写入：

```text
AmazingData_Store/YYYYMMDD/intraday/
  indices_1min.csv
  etf_1min.csv
  stocks_1min.csv
  stock_confirmation_latest.csv
  stock_confirmation_history.csv
```

股票池来自 `watchlists/stock_pool.csv`。股票分组到 ETF、指数基准的显式映射来自 `watchlists/group_benchmark_map.csv`。

快照接口中的 `volume` 和 `amount` 是当日累计值。落盘前会计算：

```text
volume_1min = 当前累计成交量 - 上一分钟累计成交量
amount_1min = 当前累计成交额 - 上一分钟累计成交额
```

程序重启后会读取当日 CSV 的最后一条累计值继续差分。相同 `code + time_int` 的重复快照不会重复写入。若接口累计值异常回退，增量记为 `0`，并通过 `counter_reset=true` 标记，避免负成交额污染量价特征。

## 3. 相对强弱

```text
rs_vs_etf_pct        = stock_pct - benchmark_etf_pct
rs_vs_index_pct      = stock_pct - benchmark_index_pct
rs_open_vs_etf_pct   = stock_price_vs_open_pct - benchmark_etf_price_vs_open_pct
rs_open_vs_index_pct = stock_price_vs_open_pct - benchmark_index_price_vs_open_pct
```

未配置 ETF 映射时，ETF 相对强弱留空；指数相对强弱默认回退到上证指数。不要用名称模糊匹配自动选择 ETF。

## 4. 分钟成交额

优先使用成交额，不直接跨股票比较成交量：

```text
amount_1m
amount_3m
amount_5m
amount_baseline_1m
amount_1m_ratio        = amount_1m / 当日此前分钟成交额中位数
amount_acceleration_3m = 最近 3 分钟成交额 / 前 3 分钟成交额
```

当前基线是当日此前分钟中位数，适用于实时冷启动。积累足够分钟数据后，应升级为“过去 N 个交易日同一时间窗口均值或中位数”，减少早盘自然放量造成的偏差。

## 5. 量价状态

```text
up_with_amount       上涨且分钟成交额放大
down_with_amount     下跌且分钟成交额放大
up_without_amount    上涨但成交额未放大
down_without_amount  下跌但成交额未放大
flat                 相对开盘基本持平
```

初步执行偏向：

```text
confirmed_strength   放量上涨，且相对 ETF 或指数更强
confirmed_weakness   放量下跌，且相对 ETF 或指数更弱
observe              条件不足，继续观察
```

## 6. 后续验证

执行确认层需要连续分钟快照。历史目录没有完整分钟快照时，不做伪回测。建议先积累至少 20 个交易日，再按 9:35、9:45 两个固定截面验证：

- CP 风险：`confirmed_weakness` 是否提高 `body_pct < 0` 命中率。
- 反核机会：`confirmed_strength` 是否提高 `body_pct > 0` 命中率。
- 趋势机会：`confirmed_strength` 是否提高 `body_pct > 0` 命中率。
