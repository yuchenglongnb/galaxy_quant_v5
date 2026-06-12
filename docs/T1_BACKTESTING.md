# T+1 交易回测层

## 1. 定位

竞价验证层使用当日 `body_pct` 衡量信号质量。T+1 交易回测层单独评估现金股票和境内权益 ETF 在 A 股交易机制下可实现的持有收益。

两层不要混用：

```text
竞价验证
  -> body_pct
  -> 判断 CP / 反核 / 趋势的竞价表征是否准确

T+1 交易回测
  -> T 日入场
  -> T+1 日开盘或收盘退出
  -> 判断策略是否具备可实现收益
```

## 2. 命令

默认使用日线开盘价作为入场代理：

```powershell
python main.py t1backtest
python main.py t1backtest 20260310 20260529
```

使用盘中监控保存的 09:35 或 09:45 快照：

```powershell
python main.py t1backtest 20260310 20260529 --entry=intraday_0935
python main.py t1backtest 20260310 20260529 --entry=intraday_0945
```

默认仅回测竞价短名单。研究全部候选时使用：

```powershell
python main.py t1backtest 20260310 20260529 --all-candidates
```

## 3. 入场口径

| 模式 | 字段 | 含义 |
| --- | --- | --- |
| `open_proxy` | 日线 `open` | 竞价入场代理，偏乐观，不等于保证成交 |
| `intraday_0935` | 09:35 或之后第一条 `last` | 盘中确认后的模拟入场 |
| `intraday_0945` | 09:45 或之后第一条 `last` | 更严格的盘中确认后模拟入场 |

分钟模式缺失历史快照时直接排除该条样本，不回退到日线 `open`。

## 4. 输出

```text
reports/t1_backtest/YYYYMMDD_YYYYMMDD/ENTRY_MODE/
  t1_signal_outcomes.csv
  t1_trade_samples.csv
  t1_trade_summary.csv
  t1_trade_by_scenario.csv
  t1_trade_by_regime.csv
  t1_trade_by_layer.csv
  t1_trade_monthly.csv
  t1_data_coverage.csv
  t1_backtest_metadata.json
```

核心字段：

| 字段 | 含义 |
| --- | --- |
| `t_close_return_pct` | T 日收盘相对入场价收益 |
| `t1_open_return_pct` | T+1 开盘可退出收益 |
| `t1_close_return_pct` | T+1 收盘收益 |
| `t1_gap_vs_t_close_pct` | T+1 跳空收益 |
| `holding_mae_pct` | T 至 T+1 最大不利波动 |
| `holding_mfe_pct` | T 至 T+1 最大有利波动 |
| `trade_eligible` | 是否属于可做多交易样本 |
| `trade_role` | `long_candidate`、`avoidance_diagnostic` 或 `market_diagnostic` |

CP、指数和行业信号保留用于诊断，但不会被计入多头交易收益。

## 5. 分钟数据

银河/AmazingData 接口使用：

```python
ad_market.query_kline(
    code_list,
    begin_date,
    end_date,
    ad.constant.Period.min1.value,
)

ad_market.query_snapshot(
    code_list=code_list,
    begin_date=target_date,
    end_date=target_date,
    begin_time=93500000,
    end_time=93500000,
)
```

项目盘中监控使用快照接口，每分钟落盘：

```text
AmazingData_Store/YYYYMMDD/intraday/
  indices_1min.csv
  etf_1min.csv
  stocks_1min.csv
  stock_confirmation_latest.csv
  stock_confirmation_history.csv
```

运行：

```powershell
python main.py monitor --summary
```

分钟确认层需要持续积累历史数据。没有真实快照时，不做伪回测。
