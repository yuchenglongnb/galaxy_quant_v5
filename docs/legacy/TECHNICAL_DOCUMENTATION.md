# 📚 GalaxyQuant 技术文档 v5.0

> **文档目的**: 为后续维护、扩展和新对话提供完整的上下文信息
> **最后更新**: 2026年1月21日

---

## 目录

1. [项目概述](#1-项目概述)
2. [架构设计](#2-架构设计)
3. [模块详解](#3-模块详解)
4. [数据流程](#4-数据流程)
5. [核心算法](#5-核心算法)
6. [API接口](#6-api接口)
7. [配置说明](#7-配置说明)
8. [使用指南](#8-使用指南)
9. [扩展指南](#9-扩展指南)
10. [常见问题](#10-常见问题)

---

## 1. 项目概述

### 1.1 项目简介

GalaxyQuant 是一套基于银河证券 AmazingData SDK 的 A股量化分析系统，专注于：

- **竞价分析**: 9:25盘前实时决策，捕捉诱多陷阱(CP)和反核机会(SA)
- **盘后复盘**: 多层级市场分析，识别主线行业和核心龙头

### 1.2 核心功能

| 功能 | 命令 | 说明 |
|------|------|------|
| 数据同步 | `python main.py sync [天数]` | 同步日线和分钟数据 |
| 竞价分析(复盘) | `python main.py auction` | 使用历史数据复盘分析 |
| 竞价分析(实时) | `python main.py auction -r -s --sync` | 9:25盘前实时决策 |
| 盘后复盘 | `python main.py review` | 全景策略分析 |
| 完整流程 | `python main.py all` | 同步+复盘+竞价 |

### 1.3 目录结构

```
galaxy_quant-v5/
├── main.py                 # 主入口，命令行路由
├── config/
│   └── settings.py         # 配置中心（DB、策略参数、阈值）
├── core/
│   ├── data_manager.py     # 数据管理器（获取/存储/加载）
│   ├── data_processor.py   # 数据处理器（指标计算）
│   ├── calendar_helper.py  # 交易日历工具
│   └── realtime_fetcher.py # 实时订阅数据获取
├── analyzers/
│   ├── base.py             # 分析器基类
│   ├── auction.py          # 竞价分析器（1529行，核心）
│   ├── factors.py          # 因子计算（CP/SA公式）
│   ├── strategy.py         # 策略分析器（复盘）
│   └── technical.py        # 技术分析（趋势标签）
├── runners/
│   ├── base.py             # 运行器基类（登录/登出）
│   ├── auction.py          # 竞价运行器（报告输出）
│   ├── review.py           # 复盘运行器
│   └── sync.py             # 同步运行器
├── reports/
│   └── formatters.py       # 报告格式化（预留）
├── AmazingData_Store/      # 本地数据仓库
│   └── {YYYYMMDD}/         # 按日期存储
│       ├── stocks.csv      # 个股日线
│       ├── indices.csv     # 指数/ETF日线
│       ├── industry_daily.csv
│       ├── stocks_auction.csv  # 竞价数据
│       ├── stocks_noon.csv     # 午盘数据
│       └── stocks_close.csv    # 收盘数据
└── INDICATORS.md           # 指标说明文档
```

---

## 2. 架构设计

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      main.py (CLI入口)                       │
├─────────────────────────────────────────────────────────────┤
│                     runners/ (运行器层)                       │
│   AuctionRunner | ReviewRunner | SyncRunner                 │
├─────────────────────────────────────────────────────────────┤
│                    analyzers/ (分析器层)                      │
│   AuctionAnalyzer | StrategyAnalyzer | TechnicalAnalyzer    │
│   AuctionFactors | ScenarioIdentifier | CommentaryGenerator │
├─────────────────────────────────────────────────────────────┤
│                       core/ (核心层)                          │
│   DataManager | DataProcessor | CalendarHelper              │
│   RealtimeFetcher                                           │
├─────────────────────────────────────────────────────────────┤
│                   config/settings.py (配置层)                 │
│   DBConfig | MarketConfig | TechConfig | StrategyConfig     │
├─────────────────────────────────────────────────────────────┤
│                AmazingData SDK (外部依赖)                     │
│   ad.BaseData | ad.MarketData | ad.InfoData | ad.Subscribe  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 数据流向

```
[AmazingData API]
       │
       ▼
[DataManager] ──fetch──> [本地CSV存储]
       │                      │
       ▼                      ▼
[DataProcessor] ◄──load──────┘
       │
       ▼ (计算指标: pct, vol_ratio, is_limit_up...)
       │
       ▼
[Analyzer] ──analyze──> [Result Dict]
       │
       ▼
[Runner] ──print_report──> [Console输出]
```

---

## 3. 模块详解

### 3.1 core/data_manager.py (954行)

**职责**: 数据获取、存储、加载的统一管理器

**核心类**: `DataManager`

**关键方法**:

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `get_stock_list()` | 获取A股代码列表 | list[str] |
| `get_industry_map()` | 获取 股票→行业 映射 | dict |
| `get_valid_trading_days(lookback)` | 获取最近N个有效交易日 | list[int] |
| `fetch_daily_all(date, with_minute)` | 同步指定日期全部数据 | bool |
| `sync_realtime(date, use_subscribe)` | 轻量级实时同步(盘前) | int |
| `load_stocks(date_list)` | 加载个股日线 | DataFrame |
| `load_auction(date_list)` | 加载竞价数据 | DataFrame |

**数据获取策略（竞价数据）**:

```python
# 优先级从高到低:
1. use_subscribe=True → _fetch_auction_subscribe()    # 实时订阅（9:25可用）
2. 9:30后 → _fetch_auction_from_minute()              # 分钟K线第一根
3. 回退 → _fetch_auction_from_daily_estimated()       # 日K线×3%估算
```

**重要说明**:
- K线时间戳代表该分钟**结束**时间（如930=9:30:00~9:30:59的K线）
- 开盘集合竞价数据包含在当日**第一根**K线（9:30）
- `pre_close` 优先使用API返回值，缺失时用shift(1)计算

### 3.2 analyzers/auction.py (1529行)

**职责**: 竞价分析核心逻辑，计算CP/SA指标，识别诱多/反核信号

**核心类**: `AuctionAnalyzer`

**入口方法**: `analyze(target_date, realtime=False)`

**分析流程**:

```python
def analyze(target_date, realtime):
    # 1. 加载数据
    if realtime:
        df_stocks, df_today = _load_realtime_data()  # 从auction+历史构建
    else:
        df_stocks = load_stocks(date_list)            # 完整日线
    
    # 2. 计算指标
    df_stocks = DataProcessor.calc_indicators(df_stocks)
    df_indices = _calc_position_5d(df_indices)        # 5日位置
    df_today = _calc_auction_metrics(df_today, df_auction, df_noon)
    
    # 3. 分析
    indices_monitor = _analyze_main_indices()         # 四大指数
    etf_result = _analyze_etf_auction_v2()            # ETF含CP/SA
    industry_result = _calc_industry_auction_v2()     # 行业含CP/SA
    signals = _generate_signals()                     # 信号汇总
    
    return {
        'date': target_date,
        'market_oar': market_oar,
        'indices_monitor': indices_monitor,
        'etf_auction': etf_result,
        'industry_report': industry_result,
        'signals': signals,  # {trap: [], reversal: [], trend: []}
        ...
    }
```

**关键指标计算** (在 `_calc_auction_metrics` 中):

```python
# 竞价涨幅
df['auction_pct'] = (open - pre_close) / pre_close * 100

# 实体涨幅
df['body_pct'] = (close - open) / pre_close * 100

# 竞价额排名
df['amt_rank'] = df['auction_amount'].rank(ascending=False)
```

### 3.3 analyzers/factors.py (601行)

**职责**: CP/SA因子计算、场景识别、评语生成

**核心类**:

#### AuctionFactors（因子计算器）

**CP指数 (Crowding Pump) - 拥挤诱多指数**:

```python
触发条件:
  - 竞价涨幅 > 高开阈值(主板0.3%/双创0.5%)
  - 或 昨日大涨(>2%)后今日不低开(>=0)
  - 或 昨日涨幅>3%且今日开盘>-0.3%

公式:
  CP = (排名权重 × 5日位置 / OAR) × (1 + 昨涨幅×10 × 昨量比/1.5) × 100

排名权重:
  Top1-3: 1.0
  Top4-5: 0.7
  Top6-10: 0.3
  其他: 0.1

信号阈值: CP >= 60 → 诱多警报
```

**SA指数 (Support Absorption) - 承接反核指数**:

```python
触发条件:
  - 竞价涨幅 < -0.3% (必须明确低开)

公式(行业):
  SA = 竞价额(亿) × 排名权重 × 低开系数 × 恐慌释放系数
  
  低开系数 = 1 + |跌幅| / 0.5
  恐慌释放系数 = 1 + |昨实体跌| / 2 × 昨量比/1.5  (仅昨阴线)

公式(ETF):
  SA = 20 × 低开系数 × 超跌系数 × 恐慌释放系数
  
  超跌系数 = 2 - 5日位/100

信号阈值: SA >= 50 → 反核机会
```

#### ScenarioIdentifier（场景识别器）

**诱多场景 (TRAP_*)**:
- `TRAP_HOT_SECTOR`: Top3热门板块+昨涨>1.5%
- `TRAP_MOMENTUM`: 连涨+5日位>80%
- `TRAP_VOLUME_FADE`: 昨放量+今缩量
- `TRAP_GENERIC`: 通用诱多

**反核场景 (REVERSAL_*)**:
- `REVERSAL_PANIC`: 昨阴线放量+今低开承接
- `REVERSAL_WASHOUT`: 趋势中洗盘拉升
- `REVERSAL_OVERSOLD`: 5日位<20%超跌反弹
- `REVERSAL_GENERIC`: 通用反核

**趋势场景 (TREND_*)**:
- `TREND_CONTINUE`: 趋势延续
- `TREND_ACCELERATE`: 放量突破加速

### 3.4 analyzers/strategy.py (266行)

**职责**: 盘后复盘四层分析

**分析层级**:

1. **Level 1 - 指数环境**
   - 分析上证/创业板/科创50/北证50
   - 计算环境评分 (-2~+2)
   - 输出趋势标签和操作建议

2. **Level 2 - ETF资金风向**
   - 监控主题ETF池(14只)
   - 输出领涨/领跌Top4

3. **Level 3 - 行业主线追踪**
   - 强度 = 成交额(亿) × 涨幅(%)
   - 筛选成交额>20亿的行业
   - 输出Top5强度行业

4. **Level 4 - 核心龙头矩阵**
   - 🚀龙头: 涨停/连板 + 主线行业 + 成交额>3亿
   - 🐘中军: 涨幅>3% + 主线行业 + 成交额>3亿

### 3.5 analyzers/technical.py (216行)

**职责**: 技术形态识别和趋势标签

**核心方法**:

- `get_advanced_trend_tag(curr, prev, hist)`: 个股趋势标签
- `get_sector_trend_tag(curr, prev, hist)`: 行业/ETF趋势标签
- `calc_env_score(pct, vol_ratio)`: 环境评分
- `get_strategy_advice(trend_tag, pct, vol_ratio)`: 操作建议

**趋势标签映射**:

| 标签 | 条件 | 优先级 |
|------|------|--------|
| 🚀 连板 | 今涨停+昨涨停 | 1 |
| 🚀 涨停 | 今涨停 | 2 |
| 💚 跌停 | 跌幅>9.5% | 3 |
| 🚀 放量新高 | 收盘>5日高×1.005 且 量比>1.5 | 4 |
| ⚠️ 顶部背离 | 收盘≈5日高 且 量比<0.7 | 5 |
| ⚡ 反包昨日 | 昨跌今涨 且 收盘>昨开 | 6 |
| 🔴 冲高回落 | 上影线>实体 | 7 |
| 🌊 二次探底 | 收盘≈5日低 且 今跌 | 8 |

### 3.6 core/data_processor.py (173行)

**职责**: 数据预处理和指标计算

**核心方法**: `calc_basic_indicators(df_window)`

**计算指标**:

```python
# 前日数据（shift计算）
df['prev_close'] = groupby('code')['close'].shift(1)  # 优先用API的pre_close
df['prev_amt'] = groupby('code')['amount'].shift(1)

# 涨跌幅
df['pct'] = (close - prev_close) / prev_close * 100

# 量比
df['vol_ratio'] = amount / prev_amt

# 涨停判断
if 'high_limit' in columns:
    df['is_limit_up'] = close >= high_limit - 0.01
else:
    # 根据代码推断涨跌停幅度
    主板: 9.9%
    创业板/科创板: 19.9%
    北交所: 29.9%
```

### 3.7 core/realtime_fetcher.py (283行)

**职责**: 使用SubscribeData实时订阅获取快照数据

**核心类**: `RealtimeFetcher`

**使用场景**: 9:25-9:30竞价时段，历史K线接口数据未入库

**工作原理**:

```python
class RealtimeFetcher:
    def fetch_auction_snapshot(code_list, save_path):
        # 1. 分批订阅（每批500个）
        for batch in batches:
            sub_data = ad.SubscribeData()
            
            @sub_data.register(code_list=batch, period=Period.snapshot.value)
            def on_snapshot(data, period):
                # 收集快照数据
                snapshot = {
                    'code': data.code,
                    'pre_close': data.pre_close,
                    'open': data.open,
                    'amount': data.amount,
                    ...
                }
                self._data_buffer[code] = snapshot
            
            # 在线程中运行订阅
            threading.Thread(target=sub_data.run).start()
            
            # 等待数据收集（最多30秒）
            wait_until(collected >= 95%)
        
        # 2. 转为DataFrame并保存
        return pd.DataFrame(self._data_buffer.values())
```

---

## 4. 数据流程

### 4.1 完整同步流程 (`sync 5`)

```
┌─────────────────────────────────────────────────────────────┐
│                    sync_recent_days(5)                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ get_valid_trading_days(5)   │
              │ 验证最近5个有效交易日         │
              └─────────────────────────────┘
                            │
              ▼             ▼             ▼
         [T-4日]       [T-3日]       ... [T日]
                            │
                            ▼
              ┌─────────────────────────────┐
              │    fetch_daily_all(date)    │
              └─────────────────────────────┘
                   │         │         │
                   ▼         ▼         ▼
           [stocks.csv] [indices.csv] [industry_daily.csv]
                   │
                   ▼ (if with_minute)
           [stocks_auction.csv] [stocks_noon.csv] [stocks_close.csv]
```

### 4.2 实时竞价分析流程 (`auction -r -s --sync`)

```
┌─────────────────────────────────────────────────────────────┐
│                  sync_realtime(use_subscribe=True)          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ 检查历史数据是否存在(T-4~T-1) │
              └─────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            │               │               │
    [9:25-9:30时段]   [9:30之后]      [无数据时]
            │               │               │
            ▼               ▼               ▼
    _fetch_auction   _fetch_auction   _fetch_auction
    _subscribe()     _from_minute()   _from_daily_estimated()
            │               │               │
            └───────────────┼───────────────┘
                            ▼
              ┌─────────────────────────────┐
              │    AuctionAnalyzer.analyze   │
              │    (realtime=True)           │
              └─────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ _load_realtime_data()        │
              │ 从auction+T-1构建今日数据     │
              └─────────────────────────────┘
                            │
                            ▼
              [计算CP/SA] → [识别场景] → [生成信号]
                            │
                            ▼
              ┌─────────────────────────────┐
              │ _print_realtime_report()    │
              │ 输出实时决策报告             │
              └─────────────────────────────┘
```

### 4.3 数据字段对照表

**stocks.csv 字段**:

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| code | str | API | 股票代码 |
| name | str | API | 股票名称 |
| open | float | K线 | 开盘价 |
| high | float | K线 | 最高价 |
| low | float | K线 | 最低价 |
| close | float | K线 | 收盘价 |
| volume | int | K线 | 成交量 |
| amount | float | K线 | 成交额 |
| pre_close | float | status | 昨收价(API) |
| high_limit | float | status | 涨停价 |
| low_limit | float | status | 跌停价 |
| industry | str | 映射 | 所属行业 |

**stocks_auction.csv 字段**:

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| code | str | - | 股票代码 |
| open | float | 分钟K线/订阅 | 开盘价=竞价价格 |
| amount | float | 分钟K线/订阅 | 竞价成交额(+第一分钟) |
| pre_close | float | code_info | 昨收价 |

---

## 5. 核心算法

### 5.1 CP指数计算详解

```python
def calc_cp(row, market_oar):
    """
    CP (Crowding Pump) 拥挤诱多指数
    
    设计理念：
    - 热门板块高开后，前日获利盘会在高位兑现
    - 缩量环境下高开更危险（跟风资金不足）
    - 昨日放量大涨后，获利盘压力更大
    """
    # 触发条件
    is_triggered = (
        auction_pct > 高开阈值 or          # 标准高开
        (prev_pct > 2.0 and auction_pct >= 0) or  # 昨涨后不低开
        (prev_pct > 3.0 and auction_pct > -0.3)   # 昨大涨后任何高于-0.3%的开盘
    )
    
    if not is_triggered:
        return None
    
    # 排名权重（Top3=1.0, Top5=0.7, Top10=0.3, 其他=0.1）
    rank_weight = RANK_WEIGHTS.get(amt_rank, 0.1)
    
    # 5日位置（0~1）
    pos_5d = row['pos_5d'] / 100.0
    
    # OAR修正（缩量时放大CP）
    oar = max(market_oar, 0.5)
    
    # 基础分
    base_cp = (rank_weight * pos_5d) / oar
    
    # 获利抛压系数（仅昨涨>1%时计入）
    if prev_pct > 1.0:
        profit_factor = 1.0 + prev_pct/100 * 10 * (prev_vol_ratio / 1.5)
    else:
        profit_factor = 1.0
    
    return base_cp * profit_factor * 100
```

### 5.2 SA指数计算详解

```python
def calc_sa(row, market_oar):
    """
    SA (Support Absorption) 承接反核指数
    
    设计理念：
    - 低开时有大资金承接，说明主力在吸筹
    - 昨日恐慌下跌后，今日低开承接更有价值
    - 跌幅越大，承接价值越高
    """
    # 触发条件：必须明确低开
    if auction_pct > -0.3:
        return None
    
    # 竞价额
    auction_amt = row['auction_amt']  # 亿
    if auction_amt <= 0:
        return None
    
    # 排名权重
    rank_weight = RANK_WEIGHTS.get(amt_rank, 0.1)
    
    # 低开系数（跌0.5%→2, 跌1%→3, 跌2%→5）
    low_open_factor = 1.0 + abs(auction_pct) / 0.5
    
    # 基础分
    base_sa = auction_amt * rank_weight * low_open_factor
    
    # 恐慌释放系数（仅昨阴线跌>1%时计入）
    if prev_body_pct < -1.0:
        panic_factor = 1.0 + abs(prev_body_pct) / 2.0 * (prev_vol_ratio / 1.5)
    else:
        panic_factor = 1.0
    
    return base_sa * panic_factor
```

### 5.3 5日位置计算

```python
def _calc_position_5d(df):
    """
    5日位置 = (当前价 - 5日最低) / (5日最高 - 5日最低) × 100
    
    含义：
    - 100% = 处于5日最高点
    - 0% = 处于5日最低点
    - 50% = 处于中间位置
    """
    df = df.sort_values(['code', 'date_int'])
    
    # 计算5日滚动高低点
    df['high_5d'] = df.groupby('code')['close'].transform(
        lambda x: x.rolling(5, min_periods=1).max()
    )
    df['low_5d'] = df.groupby('code')['close'].transform(
        lambda x: x.rolling(5, min_periods=1).min()
    )
    
    # 计算位置
    range_5d = df['high_5d'] - df['low_5d']
    df['pos_5d'] = np.where(
        range_5d > 0,
        (df['close'] - df['low_5d']) / range_5d * 100,
        50  # 无波动时默认50%
    )
    
    return df
```

---

## 6. API接口

### 6.1 AmazingData SDK 接口总结

**基础接口**:

```python
import AmazingData as ad

# 登录
ad.login(username, password, host, port)

# 登出
ad.logout(username)

# 基础数据
ad_base = ad.BaseData()
code_list = ad_base.get_code_list(security_type='EXTRA_STOCK_A')  # A股列表
code_info = ad_base.get_code_info(security_type='EXTRA_STOCK_A')  # 含pre_close
calendar = ad_base.get_calendar()                                  # 交易日历

# 市场数据
ad_market = ad.MarketData(calendar)
kline_dict = ad_market.query_kline(codes, begin_date, end_date, Period.day.value)
snapshot_dict = ad_market.query_snapshot(codes, begin_date, end_date, begin_time, end_time)

# 资讯数据
ad_info = ad.InfoData()
stock_basic = ad_info.get_stock_basic(code_list)
history_status = ad_info.get_history_stock_status(code_list, begin_date, end_date)
industry_base = ad_info.get_industry_base_info(is_local=False)
industry_const = ad_info.get_industry_constituent(index_codes, is_local=False)
industry_daily = ad_info.get_industry_daily(index_codes, begin_date, end_date)

# 实时订阅
sub_data = ad.SubscribeData()
@sub_data.register(code_list=codes, period=Period.snapshot.value)
def on_snapshot(data, period):
    print(data.code, data.last, data.amount)
sub_data.run()
```

**Period枚举**:

| 值 | 说明 |
|------|------|
| `Period.snapshot.value` | 快照 |
| `Period.min1.value` | 1分钟K线 |
| `Period.min5.value` | 5分钟K线 |
| `Period.day.value` | 日K线 |

**security_type枚举**:

| 值 | 说明 |
|------|------|
| `EXTRA_STOCK_A` | A股（沪深北） |
| `EXTRA_INDEX_A` | A股指数 |
| `EXTRA_ETF` | ETF |

### 6.2 关键API注意事项

**K线算法说明（摘自开发手册）**:

> - 开盘集合竞价数据的成交量包含在当日**第一根**K线
> - 收盘集合竞价数据的成交量包含在当日**最后一根**K线
> - 9:30的1分钟K线，计算的是 9:30:00.000~9:30:59.999 期间的K线

**时间戳格式**:

- query_snapshot的begin_time/end_time: 9位数 `HHMMSS000`（如 `92500000`）
- query_kline的begin_time/end_time: 4位数 `HHMM`（如 `930`）

---

## 7. 配置说明

### 7.1 config/settings.py 配置项

```python
class DBConfig:
    """数据库/API配置"""
    USERNAME = "your_username"
    PASSWORD = "your_password"
    IP = "101.230.159.234"
    PORT = 8600
    STORE_PATH = "./AmazingData_Store"      # 本地数据仓库路径
    CUSTOM_CONCEPT_PATH = "./custom_concepts.csv"  # 自定义概念映射
    MAX_WORKERS = 8                          # 并行线程数

class MarketConfig:
    """市场标的配置"""
    THEME_ETFS = {
        "159516.SZ": "半导体设备",
        "560860.SH": "工业有色",
        ...
    }
    MAIN_INDICES = {
        "000001.SH": "上证",
        "399006.SZ": "创业板",
        "000688.SH": "科创50",
        "899050.BJ": "北证50"
    }
    TIME_AUCTION = 925   # 竞价时间点
    TIME_NOON = 1130     # 午盘时间点
    TIME_CLOSE = 1500    # 收盘时间点

class TechConfig:
    """技术指标阈值"""
    BIG_YANG_PCT = 5.0           # 大阳线阈值
    BIG_YIN_PCT = -5.0           # 大阴线阈值
    VOLUME_SURGE = 1.5           # 放量阈值
    VOLUME_SHRINK = 0.7          # 缩量阈值
    BREAKOUT_MARGIN = 1.005      # 突破新高容差
    LIMIT_UP_MARGIN = 0.01       # 涨停板容差

class StrategyConfig:
    """策略参数"""
    MIN_AMOUNT = 3e8             # 最低成交额 (3亿)
    MAINLINE_AMOUNT = 20e8       # 主线行业成交额 (20亿)
    TOP_LIMIT_COUNT = 15         # 连板龙头数量
    TOP_WEIGHT_COUNT = 10        # 权重中军数量

class AuctionConfig:
    """竞价分析参数"""
    TOP_INDUSTRY_COUNT = 20      # 显示前N个行业
    MIN_STOCK_COUNT = 5          # 行业最少股票数
```

---

## 8. 使用指南

### 8.1 首次使用

```bash
# 1. 安装依赖
pip install tgw-1.7.1-py3-none-any.whl
pip install AmazingData-1.0.0-cp310-none-any.whl

# 2. 完整同步历史数据（收盘后执行）
python main.py sync 5

# 3. 运行盘后复盘
python main.py review
```

### 8.2 每日使用

**收盘后（15:00后）**:

```bash
# 完整同步 + 复盘 + 竞价分析
python main.py all

# 或分开执行
python main.py sync 5 --minute
python main.py review
python main.py auction
```

**盘前（9:25）**:

```bash
# 实时竞价分析（推荐订阅模式）
python main.py auction -r -s --sync

# 或快照查询模式（9:25时可能无数据）
python main.py auction -r --sync
```

### 8.3 命令行参数说明

| 参数 | 说明 |
|------|------|
| `--sync` | 先同步数据再分析 |
| `--no-sync` | 跳过数据同步 |
| `--refresh` | 强制刷新交易日缓存 |
| `--minute` | 同步分钟数据 |
| `-r, --realtime` | 实时决策模式（9:25盘前） |
| `-s, --subscribe` | 使用实时订阅模式 |

---

## 9. 扩展指南

### 9.1 添加新的ETF监控

```python
# config/settings.py
class MarketConfig:
    THEME_ETFS = {
        ...
        "新代码.SZ": "新ETF名称",  # 添加这行
    }
```

### 9.2 添加自定义概念映射

创建 `custom_concepts.csv`:

```csv
code,concept
600000.SH,银行
600001.SH,自定义概念
```

### 9.3 修改因子阈值

```python
# analyzers/factors.py
class AuctionFactors:
    CP_THRESHOLD = 60      # CP信号阈值
    SA_THRESHOLD = 50      # SA信号阈值
    HIGH_OPEN_THRESH_MAIN = 0.3   # 主板高开阈值
    HIGH_OPEN_THRESH_GEM = 0.5    # 双创高开阈值
```

### 9.4 添加新的分析维度

1. 在 `analyzers/` 下创建新的分析器，继承 `BaseAnalyzer`
2. 实现 `analyze(target_date, **kwargs)` 方法
3. 在 `runners/` 下创建对应的运行器
4. 在 `main.py` 中注册新命令

---

## 10. 常见问题

### Q1: 竞价额数据异常（几百亿而非几十亿）

**原因**: 使用了日K线成交额而非分钟K线

**解决**: 
```bash
# 删除今日竞价缓存，重新获取
rm AmazingData_Store/20260121/stocks_auction.csv
python main.py auction -r --sync
```

### Q2: 9:25实时模式无数据

**原因**: 历史快照/K线接口在盘前数据未入库

**解决**: 使用订阅模式 `-s`
```bash
python main.py auction -r -s --sync
```

### Q3: pre_close计算错误导致涨跌幅异常

**原因**: `get_code_info()` 返回的是"当前实时昨收价"而非历史昨收价

**解决**: 使用 `get_history_stock_status()` 获取历史昨收价，或用shift(1)计算

### Q4: ETF监控无数据

**原因**: indices.csv 数据不完整

**解决**:
```bash
# 重新同步指数数据
rm AmazingData_Store/*/indices.csv
python main.py sync 5
```

### Q5: 行业映射不完整

**原因**: API获取失败或自定义概念未加载

**解决**: 
1. 检查网络连接
2. 确认 `custom_concepts.csv` 格式正确（UTF-8编码）

---

## 附录A: 数据时间线

```
交易日时间线:
──────────────────────────────────────────────────────────────
09:15 ─┬─ 集合竞价开始
       │
09:25 ─┼─ 集合竞价结束，产生开盘价
       │  → 此时运行: python main.py auction -r -s --sync
       │
09:30 ─┼─ 连续竞价开始
       │  → 第一根分钟K线产生（包含竞价成交量）
       │
11:30 ─┼─ 上午收盘
       │
13:00 ─┼─ 下午开盘
       │
14:57 ─┼─ 收盘集合竞价开始
       │
15:00 ─┴─ 收盘
           → 运行: python main.py all
──────────────────────────────────────────────────────────────
```

## 附录B: 信号解读速查

| 信号 | 含义 | 操作建议 |
|------|------|----------|
| 🔴诱多 | CP≥60，高开存在陷阱 | 不追高，持仓者逢高减仓 |
| 🟢反核 | SA≥50，低开有承接 | 9:35站稳均线可介入 |
| 🟢趋势 | 趋势延续 | 持仓待涨 |
| 🔥高开高走 | 强势延续 | 顺势跟随 |
| ⚠️高开低走 | 冲高回落 | 规避或减仓 |
| 🔺低开高走 | 超跌反弹 | 关注反包机会 |
| ❄️低开低走 | 弱势延续 | 回避 |

---

**文档结束**

> 💡 提示: 在新对话中使用本项目时，建议先阅读此文档的 [架构设计](#2-架构设计) 和 [模块详解](#3-模块详解) 部分，快速建立上下文。
