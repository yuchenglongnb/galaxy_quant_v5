# 操作手册

本文档整合日常命令、日志、盘中监测和常见排障。

## 1. 常用命令

同步最近 5 个交易日：

```powershell
python main.py sync 5
python main.py sync --date=20260602 --force --minute=all
```

当交易日缓存尚未识别最新交易日时，使用 `--date=YYYYMMDD` 显式刷新指定日期。

竞价复盘：

```powershell
python main.py auction
python main.py auction 20260527
```

T+1 交易回测：

```powershell
python main.py t1backtest 20260310 20260529
python main.py t1backtest 20260310 20260529 --entry=intraday_0935
```

盘后复盘：

```powershell
python main.py review
python main.py review --no-sync
```

盘中监测：

```powershell
python main.py monitor --summary
python main.py monitor -d --summary
python main.py monitor --no-auction
```

推荐在盘前启动守护模式：

```powershell
python main.py monitor -d --summary
```

竞价复盘会将疑似除权除息或昨收价失真的价格断点从个股、行业 CP/SA
计算中剔除，并保存到：

```text
reports/validation/daily/YYYYMMDD/excluded_price_discontinuities.csv
```

程序会等待到交易日 `09:25`，自动同步竞价数据并开始逐分钟采集。分钟快照中的成交量和成交额为累计值，系统落盘时保存相邻快照差分 `volume_1min`、`amount_1min`。中途重启会从当日 CSV 恢复上一条累计值。

09:25 实时竞价决策推荐保持订阅模式开启。系统会优先保存纯竞价快照；如果只能拿到 09:30 第一根分钟 K，会将来源标记为 `minute_930_includes_first_minute`，提示该成交额包含开盘后第一分钟，只适合观察。

下一个交易日可在 `09:25` 使用接口探针核对快照字段：

```powershell
python test_api.py snapshot
```

重点检查 `trade_time`、`open`、`last`、`volume` 和 `amount`。

当前守护等待逻辑会自动跳过周末；法定节假日仍按工作日候选唤醒。若当天休市，接口不会产生有效快照，后续可再接入正式交易日历增强。

市场状态：

```powershell
python main.py status
```

测试 AI API：

```powershell
python scripts/test_ai_api.py
python scripts/test_ai_api.py --models
```

## 2. Conda 环境

本地常用环境：

```powershell
conda activate amazing
C:\Users\40857\.conda\envs\amazing\python.exe main.py auction
```

如果在 Codex 沙箱内 AmazingData/TGW 不稳定，需要用非沙箱/提升权限执行。

## 3. 日志目录

```text
logs/
  sync/
  reports/YYYY/MM/DD/
```

竞价报告示例：

```text
logs/reports/2026/05/27/20260527_185425_AuctionRunner.log
```

## 4. 验证输出

```text
reports/validation/
  auction_signal_validation.csv
  auction_signal_daily_summary.csv
  auction_signal_metrics.csv
  daily/YYYYMMDD/
```

每日目录下会保存：

```text
signal_detail.csv
signal_summary.csv
signal_metrics.csv
factor_snapshot_index.csv
factor_snapshot_etf.csv
factor_snapshot_stock.csv
factor_snapshot_industry_topk.csv
```

T+1 回测结果保存在：

```text
reports/t1_backtest/YYYYMMDD_YYYYMMDD/ENTRY_MODE/
```

详细口径见 [T1_BACKTESTING.md](T1_BACKTESTING.md)。

## 5. 盘中监测阶段

```text
9:25
  竞价数据采集
  竞价分析

9:30 - 11:30
  指数、ETF、自选股监测

11:30 - 13:00
  午休低频采集

13:00 - 15:00
  午后监测

15:00 后
  退出或进入下一个交易日等待
```

## 6. 常见问题

### 竞价复盘数据不对

优先检查：

- `AmazingData_Store/YYYYMMDD/*.meta.json` 是否为 `closed`。
- 是否在盘中同步过当天日线。
- 是否触发了 `ensure_daily_cache_for_analysis()` 自动刷新。

### qstock 无法访问

qstock 可能在导入或请求阶段访问东方财富等公开网页源。

如果代理或网络阻断，建议不要让 qstock 进入主链路。同花顺概念优先使用轻量 Provider 或离线 CSV。

### AI 调用太慢

可降低等待时间：

```powershell
$env:AI_MODEL_TIMEOUT_SECONDS="8"
$env:AI_MODEL_MAX_CALLS_PER_RUN="3"
```

或关闭外部模型：

```powershell
Remove-Item Env:\AI_MODEL_API_KEY
```

### 终端中文乱码

项目入口会调用：

```text
utils.encoding.configure_utf8_console
```

如果 PowerShell 仍乱码，可手动执行：

```powershell
chcp 65001
```
