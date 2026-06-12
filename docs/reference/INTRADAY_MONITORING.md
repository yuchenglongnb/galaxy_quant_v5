# 盘中监测

本文说明盘中监测功能的运行方式、数据存储和排障。指标含义见 [指标设计](INDICATOR_DESIGN.md)。

## 功能范围

盘中监测模块负责在交易时段采集：

- 四大指数。
- 主题 ETF 池。
- 分钟级快照。
- 可选的 9:25 竞价分析。

监测对象来自 `config/settings.py::MarketConfig`：

- `MAIN_INDICES`
- `THEME_ETFS`

## 市场阶段

由 `core/intraday_monitor.py::MarketState` 判断。

| 阶段 | 时间 | 采集策略 |
| --- | --- | --- |
| 盘前 | `< 09:15` | 不采集 |
| 集合竞价 | `09:15-09:25` | 等待竞价结束 |
| 竞价结束 | `09:25-09:30` | 可执行竞价分析，可采集 |
| 上午连续竞价 | `09:30-11:30` | 正常采集 |
| 午休 | `11:30-13:00` | 可降低频率 |
| 下午连续竞价 | `13:00-14:57` | 正常采集 |
| 收盘集合竞价 | `14:57-15:00` | 正常采集 |
| 收盘后 | `>= 15:00` | 停止或等待下一交易日 |

## 快速命令

查看状态：

```powershell
python main.py status
```

启动监测：

```powershell
python main.py monitor --summary
```

守护模式：

```powershell
python main.py monitor -d --summary
```

跳过竞价分析，仅做盘中监测：

```powershell
python main.py monitor --no-auction --summary
```

测试采集一次：

```powershell
python main.py monitor --test --summary
```

## 数据存储

```text
AmazingData_Store/
└── YYYYMMDD/
    └── intraday/
        ├── indices_1min.csv
        └── etf_1min.csv
```

常见字段：

| 字段 | 含义 |
| --- | --- |
| `code` | 证券代码 |
| `name` | 名称 |
| `type` | `index` 或 `etf` |
| `last` / `close` | 最新价 |
| `open` | 开盘价 |
| `pre_close` | 昨收价 |
| `pct` | 涨跌幅 |
| `volume` | 累计成交量 |
| `amount` | 累计成交额 |
| `volume_1min` | 当前累计成交量减上一分钟累计成交量 |
| `amount_1min` | 当前累计成交额减上一分钟累计成交额 |
| `increment_source` | `first_snapshot`、`previous_snapshot`、`restored_previous_snapshot` 或 `counter_reset` |
| `counter_reset` | 累计值异常回退时为 `true`，该分钟增量按 `0` 处理 |
| `collect_time` | 采集时间 |

## 与竞价分析的关系

`monitor` 在 9:25 后可以先执行竞价分析，再进入盘中监测循环。

推荐盘前实时竞价决策单独运行：

```powershell
python main.py auction -r -s --sync
```

随后再启动监测：

```powershell
python main.py monitor --summary
```

如果只需要盘中指数和 ETF 快照，使用：

```powershell
python main.py monitor --no-auction --summary
```

## 断点续传

监测数据追加写入 CSV。程序重启后会读取当日已有文件，继续从后续时间采集。

恢复时会读取各标的最后一条 `volume` 和 `amount` 累计值，因此重启后的第一条新快照仍能计算有效分钟增量。相同标的同一分钟的重复快照会跳过，避免 CSV 重复记录。

这适合：

- 终端意外断开。
- 网络短暂波动。
- 午间重启。

## 日志

Runner 输出会写入：

```text
logs/YYYYMMDD_HHMMSS_MonitorRunner.log
```

盘中排障时优先看这个日志。

## 常见问题

### 已收盘，无法启动监测

普通模式只允许交易时段启动。收盘后可使用守护模式：

```powershell
python main.py monitor -d --summary
```

### 数据采集不完整

可能原因：

- SDK 快照接口短暂无数据。
- 网络连接不稳定。
- ETF 池中个别代码停牌或无成交。

处理：

- 查看 `logs/`。
- 确认 `AmazingData_Store/YYYYMMDD/intraday/` 是否持续更新。
- 必要时重启监测。

### 午休期间采集频率

午休期间 `MarketState.should_collect()` 仍允许采集，但可通过 `MonitorConfig.NOON_INTERVAL_MULT` 降低频率。

### 竞价分析卡住

全市场分钟 K 很慢。日常建议：

- 竞价复盘用日线 `open`。
- 实时盘前用订阅模式。
- 不要在盘中监测里默认拉全量分钟 K。

## 扩展方向

- 增加 ETF 异动告警。
- 增加分钟量能突增检测。
- 增加盘中图表输出。
- 增加 WebSocket 或桌面通知。
- 增加历史回放。
