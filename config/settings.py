# -*- coding: utf-8 -*-
"""
配置中心 - 统一管理所有配置项
"""


import os


class DBConfig:
    """数据库/API配置"""
    USERNAME = os.getenv("AD_USERNAME", "")
    PASSWORD = os.getenv("AD_PASSWORD", "")
    IP = os.getenv("AD_HOST", "")
    PORT = int(os.getenv("AD_PORT", "8600"))
    STORE_PATH = "./AmazingData_Store"
    CUSTOM_CONCEPT_PATH = "./custom_concepts.csv"
    MAX_WORKERS = 8
    BATCH_TASK_TIMEOUT_SECONDS = 180


class UniverseConfig:
    """Runtime universe controls for data sync."""

    # Keep daily stock sync focused. If the file is missing/empty, DataManager
    # falls back to the full A-share list so existing workflows still run.
    STOCK_POOL_PATH = "./watchlists/stock_pool.csv"
    STOCK_BENCHMARK_MAP_PATH = "./watchlists/group_benchmark_map.csv"
    USE_ALL_STOCKS_DAILY = False

    # Industry index daily data is slow and often overlaps poorly with theme
    # ETF observation. Keep it opt-in; ETF monitors carry sector expression.
    SYNC_INDUSTRY_DAILY = False

    # Minute data should only cover decision targets, not the full market.
    MINUTE_INCLUDE_STOCK_POOL = True
    MINUTE_INCLUDE_ETFS = True
    MINUTE_INCLUDE_MAIN_INDICES = True


class ConceptConfig:
    """Filters for THS concepts used as tradable theme labels."""

    # Keep raw THS concepts, but exclude these from signal-facing labels.
    THS_EXCLUDE_EXACT = {
        "同花顺出海50",
        "同花顺果指数",
        "同花顺新质50",
        "中国AI 50",
        "高股息精选",
    }
    THS_EXCLUDE_KEYWORDS = (
        "年报预增",
        "季报预增",
        "回购增持",
        "同花顺",
    )
    THS_EXCLUDE_REGEX = (
        r".*50$",
        r".*指数$",
    )


class MarketConfig:
    """市场标的配置"""
    
    # 主题ETF监控池（用于盘中监测和竞价分析）
    THEME_ETFS = {
        # 科技
        "159516.SZ": "半导体设备",
        "512480.SH": "半导体",
        "159732.SZ": "消费电子",
        "159246.SZ": "AI人工智能",
        "159851.SZ": "金融科技",
        "515790.SH": "光伏",
        "516160.SH": "新能源",
        
        # 资源
        "560860.SH": "工业有色",
        "562800.SH": "稀有金属",
        "159870.SZ": "化工",
        "561260.SH": "电力",
        "159981.SZ": "能源化工",
        
        # 消费&医药
        "159928.SZ": "消费",
        "512170.SH": "医疗",
        "159992.SZ": "创新药",
        
        # 金融
        "512880.SH": "证券",
        "512800.SH": "银行",
        "512640.SH": "金融地产",
        
        # 制造&基建
        "515030.SH": "新能源车",
        "561380.SH": "电网设备",
        "159206.SZ": "卫星",
        "516950.SH": "基建",
        "159805.SZ": "传媒",
        
        # 宽基
        "510300.SH": "沪深300",
        "510500.SH": "中证500",
        "159915.SZ": "创业板",
        "588000.SH": "科创50ETF",
    }
    
    # ETF监控池（别名，用于竞价分析）
    ETF_MONITORS = THEME_ETFS
    
    # 主要指数
    MAIN_INDICES = {
        "000001.SH": "上证",
        "399006.SZ": "创业板",
        "000688.SH": "科创50",
        "899050.BJ": "北证50"
    }
    
    # 分钟数据时间点 (HHMM格式)
    # 注意：分钟K线时间戳代表该分钟的结束时间
    # 例如 930 代表 9:30:00~9:30:59 的K线
    TIME_AUCTION = 925       # 竞价结束 9:25（盘前可能无数据，会fallback到930）
    TIME_NOON = 1130         # 午间 11:30
    TIME_CLOSE = 1500        # 收盘 15:00（包含收盘集合竞价）


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
    REVERSAL_THRESHOLD = 1.0     # 反转阈值


class AuctionConfig:
    """竞价分析参数"""
    TOP_INDUSTRY_COUNT = 20      # 显示前N个行业
    MIN_STOCK_COUNT = 5          # 行业最少股票数
    CP_THRESHOLD = 60            # CP诱多信号阈值
    SA_THRESHOLD = 50            # SA反核信号阈值
    TREND_MIN_AUCTION_PCT = -1.5 # 趋势候选允许的最低竞价涨跌幅
    ACTION_TOPK_INDEX = 2        # 每类信号最多保留的可执行短名单数量
    ACTION_TOPK_ETF = 3
    ACTION_TOPK_STOCK = 5
    ACTION_TOPK_INDUSTRY = 3
    ACTION_TOPK_TRAP = 3         # CP风险主报告只展示Top3
    ACTION_TOPK_REVERSAL = 5     # 反核保留Top3-Top5观察空间
    ACTION_TOPK_TREND = 1        # 趋势重构期间仅展示Top1观察项
    ACTION_TOPK_REVERSAL_HIGH_CONFIDENCE = 3
    ACTION_REVERSAL_HIGH_CONFIDENCE_REGIMES = ("risk_off",)
    ACTION_BLOCKED_LONG_REGIMES = ("hostile",)
    ACTION_REVERSAL_HIGH_CONFIDENCE_SCENARIOS = ("REVERSAL_OVERSOLD",)
    ACTION_REVERSAL_HIGH_CONFIDENCE_UNIVERSES = ("index", "ETF")
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_GROWTH_MIN_BODY = 0.30
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_GROWTH_MIN_CLOSE = 0.10
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_MIN_BODY = 1.20
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_MIN_CLOSE = 0.60
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_THEME_COUNT_MIN = 2
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_POSITIVE_SHARE_MIN = 0.55
    ACTION_RISK_OFF_STRUCTURAL_REPAIR_INDEX_ETF_BONUS = 8.0
    ACTION_TRAP_HIGHLIGHT_TOP = 1 # CP第一名作为最高优先级警报
    ACTION_TRAP_SCENARIOS = (
        "TRAP_HOT_SECTOR",
        "TRAP_OVERHEATED_ACCELERATION",
    )
    ACTION_TREND_SCENARIOS = (
        "TREND_ACCELERATE",
    )
    ACTION_MIN_SCORE_TRAP = 60
    ACTION_MIN_SCORE_REVERSAL = 55
    ACTION_MIN_SCORE_TREND = 50
    ACTION_MIN_SCORE_REVERSAL_HOSTILE = 80
    ACTION_MIN_SCORE_TREND_HOSTILE = 80
    ACTION_MAX_ABS_AUCTION_PCT = 10
    ACTION_TREND_MIN_AUCTION_PCT = -0.5
    ACTION_TREND_HIGH_OPEN_PCT = 5.0
    ACTION_TREND_HIGH_OPEN_PENALTY = 12.0
    ACTION_TREND_CONFIRM_BIAS_BONUS = 18.0
    ACTION_TREND_CONFIRM_OBSERVE_PENALTY = 8.0
    ACTION_TREND_CONFIRM_PRICE_WEIGHT = 4.0
    ACTION_TREND_CONFIRM_RS_WEIGHT = 3.0
    ACTION_TREND_CONFIRM_AMOUNT_WEIGHT = 6.0
    ACTION_PREOPEN_RELIABILITY_OBSERVE_PENALTY = 8.0
    ACTION_PREOPEN_RELIABILITY_DEPRIORITIZE_PENALTY = 18.0
    ACTION_PREOPEN_RELIABILITY_EXCLUDE_PENALTY = 35.0
    ACTION_TREND_GROUP_REGIME_MIN_CONFIRMED_COUNT = 2
    ACTION_TREND_GROUP_REGIME_MIN_CONFIRMED_DAYS = 2
    ACTION_TREND_GROUP_REGIME_MAX_BONUS = 8.0
    ACTION_TREND_GROUP_REGIME_MAX_PENALTY = 10.0
    ACTION_THEME_CLUSTER_MIN_SAMPLE_COUNT = 40
    ACTION_THEME_CLUSTER_BASELINE_TREND = 50.0
    ACTION_THEME_CLUSTER_BASELINE_REVERSAL = 50.0
    ACTION_THEME_CLUSTER_DIRECTED_WEIGHT = 3.0
    ACTION_THEME_CLUSTER_HITRATE_WEIGHT = 0.2
    ACTION_THEME_CLUSTER_RISK_OFF_REVERSAL_BONUS = 2.0
    ACTION_THEME_CLUSTER_MAX_BONUS = 10.0
    ACTION_THEME_CLUSTER_MAX_PENALTY = 10.0
    ACTION_OVERHEATED_PREV_PCT = 3.0
    ACTION_OVERHEATED_AUCTION_PCT = 5.0
    ACTION_OVERHEATED_POS_5D = 70.0
    ACTION_STRONG_REPAIR_INDEX_AVG_MIN = 0.80
    ACTION_STRONG_REPAIR_ETF_AVG_MIN = 0.50
    ACTION_STRONG_REPAIR_INDEX_POSITIVE_MIN = 0.75
    ACTION_STRONG_REPAIR_ETF_POSITIVE_MIN = 0.70
    ACTION_STRONG_REPAIR_WEAK_INDEX_STATES_MIN = 2
    ACTION_TREND_STRONG_REPAIR_STOCK_BONUS = 6.0
    ACTION_HOSTILE_INDEX_AVG_MAX = -0.15
    ACTION_HOSTILE_ETF_AVG_MAX = -0.30
    ACTION_HOSTILE_INDEX_POSITIVE_MAX = 0.25
    ACTION_HOSTILE_ETF_POSITIVE_MAX = 0.30
    ACTION_HOSTILE_WEAK_INDEX_STATES = ("连跌", "昨跌", "反弹夭折")
    # Price gaps beyond the board limit are usually ex-rights/ex-dividend
    # discontinuities or stale pre-close values. Keep a small buffer for
    # vendor rounding and exclude them from CP/SA aggregation.
    PRICE_DISCONTINUITY_LIMIT_MAIN = 12.0
    PRICE_DISCONTINUITY_LIMIT_ST = 7.0
    PRICE_DISCONTINUITY_LIMIT_GEM_STAR = 22.0
    PRICE_DISCONTINUITY_LIMIT_BSE = 32.0
    REALTIME_CAPTURE_SECONDS = 2.0
    REALTIME_CAPTURE_MIN_RATIO = 0.90


class AIReportConfig:
    """AI report interpretation controls."""

    # off: template only; shadow: trace only; assist: AI/local text in report;
    # replace: same as assist, reserved for stricter future rollout.
    MODE = os.getenv("AI_REPORT_MODE", "assist").lower()
    API_KEY = os.getenv("AI_MODEL_API_KEY", "")
    BASE_URL = os.getenv("AI_MODEL_BASE_URL", "")
    MODEL = os.getenv("AI_MODEL_NAME", "")
    TIMEOUT_SECONDS = float(os.getenv("AI_MODEL_TIMEOUT_SECONDS", "20"))
    MODEL_MAX_CALLS_PER_RUN = int(os.getenv("AI_MODEL_MAX_CALLS_PER_RUN", "3"))
    TRACE_DIR = os.getenv("AI_REPORT_TRACE_DIR", "./reports/ai_traces")


class MonitorConfig:
    """盘中监测参数"""
    DEFAULT_INTERVAL = 60        # 默认采集间隔（秒）
    NOON_INTERVAL_MULT = 5       # 午休间隔倍数
    SUMMARY_INTERVAL = 5         # 市场概览打印间隔（分钟）
    
    # 量能异动阈值
    VOLUME_SURGE_RATIO = 2.0     # 分钟成交量突增倍数
    PRICE_MOVE_THRESHOLD = 0.5   # 价格异动阈值（%）
    
    # 告警阈值
    INDEX_DROP_ALERT = -1.0      # 指数跌幅告警（%）
    ETF_SURGE_ALERT = 3.0        # ETF涨幅告警（%）
