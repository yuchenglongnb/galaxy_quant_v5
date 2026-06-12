# -*- coding: utf-8 -*-
"""
竞价因子计算模块

核心因子:
- CP (Crowding Pump): 拥挤诱多指数 - 捕捉高开诱多陷阱
- SA (Support Absorption): 承接反核指数 - 捕捉低开反转机会

公式:
CP = (排名权重 × 5日位置 / OAR) × (1 + 昨涨幅 × 昨量比)
SA = (竞价额亿 / max(|竞价跌幅|, 0.3)) × (1 + |昨实体跌| × 昨量比)
"""

import pandas as pd
import numpy as np

from ai.signal_interpreter import SignalInterpreter
from config.settings import AuctionConfig


class AuctionFactors:
    """竞价因子计算器"""
    
    # ═══════════════════════════════════════════════════════════
    # 配置参数
    # ═══════════════════════════════════════════════════════════
    
    # 排名权重
    RANK_WEIGHTS = {
        1: 1.0, 2: 1.0, 3: 1.0,      # Top3
        4: 0.7, 5: 0.7,              # Top5
        6: 0.3, 7: 0.3, 8: 0.3, 9: 0.3, 10: 0.3,  # Top10
    }
    DEFAULT_RANK_WEIGHT = 0.1
    
    # 高开阈值（主板/双创）
    HIGH_OPEN_THRESH_MAIN = 0.3    # 主板高开阈值
    HIGH_OPEN_THRESH_GEM = 0.5     # 双创高开阈值
    
    # 低开/平开阈值
    LOW_OPEN_THRESH = 0.2          # 低于此为低开，高于此为平开
    
    # 跌幅分母下限（防止除零）
    MIN_DROP_PCT = 0.3
    
    # 信号阈值
    
    # ═══════════════════════════════════════════════════════════
    # CP指数计算
    # ═══════════════════════════════════════════════════════════
    
    @classmethod
    def calc_cp(cls, row, market_oar=1.0):
        """
        计算CP (Crowding Pump) 拥挤诱多指数
        
        公式: (排名权重 × 5日位置 / OAR) × (1 + 昨涨幅 × 昨量比)
        
        触发条件: 
        - 竞价涨幅 > 高开阈值（主板0.3%/双创0.5%）
        - 或 昨日大涨(>2%)后今日不低开(>=0)
        
        参数:
            row: 包含以下字段的dict或Series
                - amt_rank: 竞价额排名
                - pos_5d: 5日位置 (0-100)
                - auction_pct: 竞价涨幅 (%)
                - prev_pct: 昨日涨跌幅 (%)
                - prev_vol_ratio: 昨日量比
                - is_gem: 是否双创 (可选)
            market_oar: 市场OAR
            
        返回:
            float: CP值，None表示不触发
        """
        # 获取阈值
        is_gem = row.get('is_gem', False)
        high_thresh = cls.HIGH_OPEN_THRESH_GEM if is_gem else cls.HIGH_OPEN_THRESH_MAIN
        
        auction_pct = row.get('auction_pct', 0) or 0
        prev_pct = row.get('prev_pct', 0) or 0
        
        # 触发条件判断
        # 条件1: 标准高开
        is_high_open = auction_pct > high_thresh
        
        # 条件2: 昨日大涨(>2%)后今日不低开(>=0)，也视为诱多风险
        is_post_surge = prev_pct > 2.0 and auction_pct >= 0
        
        # 条件3: 昨日涨幅>3%，今日任何高于-0.3%的开盘都有诱多风险
        is_strong_surge = prev_pct > 3.0 and auction_pct > -0.3
        
        if not (is_high_open or is_post_surge or is_strong_surge):
            return None
        
        # 排名权重
        amt_rank = int(row.get('amt_rank', 99) or 99)
        rank_weight = cls.RANK_WEIGHTS.get(amt_rank, cls.DEFAULT_RANK_WEIGHT)
        
        # 5日位置 (0-1)
        pos_5d = (row.get('pos_5d', 50) or 50) / 100.0
        
        # OAR修正（缩量时放大CP）
        oar = max(market_oar, 0.5)
        
        # 基础分
        base_cp = (rank_weight * pos_5d) / oar
        
        # 昨日获利抛压系数
        prev_pct_decimal = prev_pct / 100.0  # 转为小数
        prev_vol_ratio = row.get('prev_vol_ratio', 1.0) or 1.0
        
        # 只有昨日上涨才计入获利抛压（阈值降低到1%）
        if prev_pct > 1.0:
            profit_factor = 1.0 + prev_pct_decimal * 10 * (prev_vol_ratio / 1.5)
        else:
            profit_factor = 1.0
        
        cp = base_cp * profit_factor * 100  # 放大到百分制
        
        return round(cp, 1)
    
    # ═══════════════════════════════════════════════════════════
    # SA指数计算
    # ═══════════════════════════════════════════════════════════
    
    @classmethod
    def calc_sa(cls, row, market_oar=1.0):
        """
        计算SA (Support Absorption) 承接反核指数
        
        公式: (竞价额亿 × 排名权重) / max(|竞价跌幅|, 0.5) × (1 + 恐慌释放系数)
        
        触发条件: 竞价涨幅 < -0.2% (必须是明确的低开)
        
        恐慌释放系数: 
        - 昨日实体为负（收阴）才计入
        - 系数 = |昨实体跌幅| × 昨量比
        
        参数:
            row: 包含以下字段的dict或Series
                - auction_amt: 竞价额 (亿)
                - auction_pct: 竞价涨幅 (%)
                - prev_body_pct: 昨日实体涨跌幅 (%)
                - prev_vol_ratio: 昨日量比
                - amt_rank: 竞价额排名
            market_oar: 市场OAR
            
        返回:
            float: SA值，None表示不触发
        """
        # 触发条件：必须是明确的低开（<-0.3%），平开不触发
        auction_pct = row.get('auction_pct', 0) or 0
        if auction_pct > -0.3:  # 必须低开，平开不算
            return None
        
        # 竞价额 (亿)
        auction_amt = row.get('auction_amt', 0) or 0
        if auction_amt <= 0:
            return None
        
        # 排名权重（和CP一致）
        amt_rank = int(row.get('amt_rank', 99) or 99)
        rank_weight = cls.RANK_WEIGHTS.get(amt_rank, cls.DEFAULT_RANK_WEIGHT)
        
        # 低开系数：跌幅越大，承接价值越高
        # 跌0.5%→系数2，跌1%→系数3，跌2%→系数5
        drop_pct = abs(auction_pct)
        low_open_factor = 1.0 + drop_pct / 0.5
        
        # 基础分：竞价额 × 排名权重 × 低开系数
        base_sa = auction_amt * rank_weight * low_open_factor
        
        # 昨日恐慌释放系数（只有昨日收阴才计入）
        prev_body_pct = row.get('prev_body_pct', 0) or 0
        prev_vol_ratio = row.get('prev_vol_ratio', 1.0) or 1.0
        
        # 只有昨日实体为负（收阴线）才算恐慌释放
        if prev_body_pct < -1.0:  # 昨日实体跌幅>1%
            panic_factor = 1.0 + abs(prev_body_pct) / 2.0 * (prev_vol_ratio / 1.5)
        else:
            panic_factor = 1.0
        
        sa = base_sa * panic_factor
        
        return round(sa, 1)
    
    # ═══════════════════════════════════════════════════════════
    # ETF专用SA指数计算
    # ═══════════════════════════════════════════════════════════
    
    @classmethod
    def calc_etf_sa(cls, row, market_oar=1.0):
        """
        计算ETF专用SA (Support Absorption) 承接反核指数
        
        与行业SA不同，ETF没有"竞价额"概念，因此采用技术面指标：
        
        公式: 基准分 × 低开系数 × 超跌系数 × 恐慌释放系数
        
        触发条件: 竞价涨幅 < -0.3% (必须是明确的低开)
        
        参数说明:
        - 基准分: 20（固定值，相当于行业20亿竞价额的水平）
        - 低开系数: 跌幅越大，承接价值越高
        - 超跌系数: 5日位越低，承接价值越高
        - 恐慌释放系数: 昨日收阴且跌幅大时，今日低开承接价值更高
        
        参数:
            row: 包含以下字段的dict或Series
                - auction_pct: 竞价涨幅 (%)
                - pos_5d: 5日位置 (0-100)
                - prev_body_pct: 昨日实体涨跌幅 (%)
                - prev_vol_ratio: 昨日量比
            market_oar: 市场OAR（暂未使用，保留接口一致性）
            
        返回:
            float: SA值，None表示不触发
        """
        # 触发条件：必须是明确的低开（<-0.3%），平开不触发
        auction_pct = row.get('auction_pct', 0) or 0
        if auction_pct > -0.3:  # 必须低开，平开不算
            return None
        
        # ========== 基准分 ==========
        # 固定值20，相当于行业20亿竞价额的水平
        base_score = 20
        
        # ========== 低开系数 ==========
        # 跌幅越大，承接价值越高
        # 跌0.5% → 2.0，跌1.0% → 3.0，跌2.0% → 5.0
        drop_pct = abs(auction_pct)
        low_open_factor = 1.0 + drop_pct / 0.5
        
        # ========== 超跌系数 ==========
        # 5日位越低，承接价值越高
        # 5日位0% → 2.0（极度超跌），5日位50% → 1.5，5日位100% → 1.0（高位）
        pos_5d = row.get('pos_5d', 50) or 50
        oversold_factor = 2.0 - (pos_5d / 100)
        
        # ========== 恐慌释放系数 ==========
        # 只有昨日实体为负（收阴线）且跌幅>1%才计入
        prev_body_pct = row.get('prev_body_pct', 0) or 0
        prev_vol_ratio = row.get('prev_vol_ratio', 1.0) or 1.0
        
        if prev_body_pct < -1.0:  # 昨日实体跌幅>1%
            panic_factor = 1.0 + abs(prev_body_pct) / 3.0 * (prev_vol_ratio / 1.5)
        else:
            panic_factor = 1.0
        
        # ========== 计算最终SA ==========
        sa = base_score * low_open_factor * oversold_factor * panic_factor
        
        return round(sa, 1)
    
    # ═══════════════════════════════════════════════════════════
    # 5日位置计算
    # ═══════════════════════════════════════════════════════════
    
    @staticmethod
    def calc_position_5d(df, code_col='code', close_col='close', date_col='date_int', reference_col='open'):
        """
        计算5日位置
        
        公式: (收盘价 - 5日最低) / (5日最高 - 5日最低) × 100%
        
        参数:
            df: DataFrame，包含多日数据
            code_col: 代码列名
            close_col: 收盘价列名
            date_col: 日期列名
            
        返回:
            Series: 5日位置 (0-100)
        """
        df = df.sort_values([code_col, date_col])
        
        # 竞价时点只能使用T-1及更早的收盘价区间。
        df['high_5d'] = df.groupby(code_col)[close_col].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).max()
        )
        df['low_5d'] = df.groupby(code_col)[close_col].transform(
            lambda x: x.shift(1).rolling(5, min_periods=1).min()
        )
        
        range_5d = df['high_5d'] - df['low_5d']
        reference_price = df[reference_col].fillna(df[close_col]) if reference_col in df.columns else df[close_col]
        df['pos_5d'] = np.where(
            range_5d > 0,
            ((reference_price - df['low_5d']) / range_5d * 100).clip(0, 100),
            50  # 如果没有波动，默认50%
        )
        
        return df['pos_5d']


class ScenarioIdentifier:
    """场景识别器"""
    
    # ═══════════════════════════════════════════════════════════
    # 场景类型定义
    # ═══════════════════════════════════════════════════════════
    
    # 诱多场景
    TRAP_HOT_SECTOR = 'TRAP_HOT_SECTOR'       # 热门板块拥挤高开
    TRAP_MOMENTUM = 'TRAP_MOMENTUM'           # 连涨后冲顶高开
    TRAP_VOLUME_FADE = 'TRAP_VOLUME_FADE'     # 放量后缩量高开
    TRAP_OVERHEATED_ACCELERATION = 'TRAP_OVERHEATED_ACCELERATION' # 高位加速兑现风险
    TRAP_GENERIC = 'TRAP_GENERIC'             # 通用诱多
    
    # 反核场景
    REVERSAL_PANIC = 'REVERSAL_PANIC'         # 恐慌出清反转
    REVERSAL_WASHOUT = 'REVERSAL_WASHOUT'     # 洗盘拉升
    REVERSAL_OVERSOLD = 'REVERSAL_OVERSOLD'   # 超跌反弹
    REVERSAL_GENERIC = 'REVERSAL_GENERIC'     # 通用反核
    
    # 趋势场景
    TREND_CONTINUE = 'TREND_CONTINUE'         # 趋势延续
    TREND_ACCELERATE = 'TREND_ACCELERATE'     # 趋势加速
    
    @classmethod
    def identify(cls, row, market_oar=1.0, realtime=False):
        """
        识别场景类型
        
        参数:
            row: 包含以下字段的dict或Series
                - cp: CP值 (可为None)
                - sa: SA值 (可为None)
                - auction_pct: 竞价涨幅
                - body_pct: 实体涨幅 (仅供盘后解释和验证，不参与候选生成)
                - prev_pct: 昨日涨跌幅
                - prev_body_pct: 昨日实体涨跌幅
                - prev_vol_ratio: 昨日量比
                - pos_5d: 5日位置
                - amt_rank: 竞价额排名
                - trend_state: 趋势状态 ('连涨'/'连跌'/'震荡'等)
            market_oar: 市场OAR
            realtime: 是否实时模式（9:25盘前，没有body_pct）
            
        返回:
            str: 场景类型，None表示无明显信号
        """
        cp = row.get('cp')
        sa = row.get('sa')
        auction_pct = row.get('auction_pct', 0) or 0
        prev_pct = row.get('prev_pct', 0) or 0
        prev_body_pct = row.get('prev_body_pct', 0) or 0
        prev_vol_ratio = row.get('prev_vol_ratio', 1.0) or 1.0
        pos_5d = row.get('pos_5d', 50) or 50
        amt_rank = row.get('amt_rank', 99) or 99
        trend_state = row.get('trend_state', '震荡')
        
        # ═══════════════════════════════════════════════════════════
        # 🔴 诱多场景判断 (CP >= 60)
        # ═══════════════════════════════════════════════════════════
        if cp is not None and cp >= AuctionConfig.CP_THRESHOLD:
            # 场景1: 热门板块拥挤高开
            if amt_rank <= 3 and prev_pct > 1.5:
                return cls.TRAP_HOT_SECTOR
            
            # 场景2: 连涨后冲顶高开
            if trend_state == '连涨' and pos_5d > 80:
                return cls.TRAP_MOMENTUM
            
            # 场景3: 放量后缩量高开
            if prev_vol_ratio > 1.5 and market_oar < 0.9:
                return cls.TRAP_VOLUME_FADE
            
            # 通用诱多
            return cls.TRAP_GENERIC

        # 昨日已强势、今日明显高开且处于高位时，更接近兑现风险而非趋势机会。
        if (
            prev_pct >= AuctionConfig.ACTION_OVERHEATED_PREV_PCT
            and auction_pct >= AuctionConfig.ACTION_OVERHEATED_AUCTION_PCT
            and pos_5d >= AuctionConfig.ACTION_OVERHEATED_POS_5D
        ):
            return cls.TRAP_OVERHEATED_ACCELERATION
        
        # ═══════════════════════════════════════════════════════════
        # 🟢 反核场景判断
        # 候选生成只使用竞价时点可见数据。body_pct 留给盘后验证层。
        # ═══════════════════════════════════════════════════════════
        if sa is not None and sa >= AuctionConfig.SA_THRESHOLD:
            # 场景1: 恐慌出清反转
            if prev_body_pct < -2.0 and prev_vol_ratio > 1.5:
                return cls.REVERSAL_PANIC
            
            # 场景2: 趋势中洗盘拉升
            if trend_state in ['连涨', '反弹', '昨涨'] and prev_pct > 0:
                return cls.REVERSAL_WASHOUT
            
            # 场景3: 超跌反弹
            if pos_5d < 20:
                return cls.REVERSAL_OVERSOLD
            
            # 通用反核
            return cls.REVERSAL_GENERIC
        
        # ═══════════════════════════════════════════════════════════
        # 🟢 趋势候选判断
        # 只使用昨日趋势和竞价涨跌幅。收盘实体由盘后验证层处理。
        # ═══════════════════════════════════════════════════════════
        if trend_state in ['连涨', '昨涨'] and auction_pct >= AuctionConfig.TREND_MIN_AUCTION_PCT:
            if prev_vol_ratio > 1.2 and prev_pct > 1.0:
                return cls.TREND_ACCELERATE
            
            return cls.TREND_CONTINUE
        
        return None
    
    @classmethod
    def get_signal_type(cls, scenario):
        """
        获取信号类型
        
        返回: ('🔴CP风险', 'trap') / ('🟢反核', 'reversal') / ('🟢趋势', 'trend') / None
        """
        if scenario is None:
            return None
        
        if scenario.startswith('TRAP'):
            return '🔴CP风险', 'trap'
        elif scenario.startswith('REVERSAL'):
            return '🟢反核', 'reversal'
        elif scenario.startswith('TREND'):
            return '🟢趋势', 'trend'
        
        return None


class CommentaryGenerator:
    """评语生成器"""
    
    # ═══════════════════════════════════════════════════════════
    # 评语模板
    # ═══════════════════════════════════════════════════════════
    
    TEMPLATES = {
        # 诱多场景
        'TRAP_HOT_SECTOR': {
            'context': '放量{prev_kline}({prev_pct}, 量比{prev_vol_ratio})，获利盘堆积',
            'action': '{oar_desc}下Top{rank}拥挤高开',
            'risk': '昨日追涨资金已有丰厚获利，今日高开是完美的兑现窗口。{oar_reason}',
            'advice': '持仓者逢高减仓，空仓者回避追高'
        },
        'TRAP_MOMENTUM': {
            'context': '连涨趋势，5日位置{pos_5d}(高位)',
            'action': '高位逆势高开{auction_pct}',
            'risk': '连续上涨后动能衰竭，高位高开是典型的诱多形态。获利盘兑现意愿强烈。',
            'advice': '短线获利了结，不追高'
        },
        'TRAP_VOLUME_FADE': {
            'context': '昨日放量(量比{prev_vol_ratio})，今日{oar_desc}',
            'action': '缩量环境下逆势高开',
            'risk': '放量后缩量高开，说明跟风资金不足。高开消耗做多动能后易被存量抛压淹没。',
            'advice': '观望为主，等缩量回调后再考虑'
        },
        'TRAP_GENERIC': {
            'context': '昨日{prev_kline}({prev_pct})',
            'action': '今日高开{auction_pct}',
            'risk': 'CP值偏高，高开存在诱多风险。',
            'advice': '谨慎追高'
        },
        
        # 反核场景
        'REVERSAL_PANIC': {
            'context': '放量{prev_kline}({prev_body_pct}, 量比{prev_vol_ratio})，恐慌盘释放',
            'action': 'Top{rank}竞价额(主力在场) + 适度低开(恐慌盘出清)',
            'risk': '"高竞价额+适度低开"是经典的主力吸筹模型。竞价额大说明主力在接货，低开说明散户在割肉，开盘反转确认控盘意图。',
            'advice': '站稳分时均线可介入，止损设开盘价下方1%'
        },
        'REVERSAL_WASHOUT': {
            'context': '趋势向上，昨日{prev_kline}({prev_pct})',
            'action': '低开{auction_pct}，SA达到候选阈值',
            'risk': '趋势延续中的低开可能形成洗盘，但需要盘中实体和承接强度确认。',
            'advice': '观察开盘后能否收回开盘价，确认后再处理'
        },
        'REVERSAL_OVERSOLD': {
            'context': '连续调整，5日位置{pos_5d}(低位)',
            'action': '恐慌低开{auction_pct}，进入承接观察区',
            'risk': '连续调整后的恐慌低开具备超跌修复条件，但反弹是否成立仍需盘中确认。',
            'advice': '观察能否站上开盘价和5日线'
        },
        'REVERSAL_GENERIC': {
            'context': '昨日{prev_kline}({prev_pct})',
            'action': '低开{auction_pct}，SA达到候选阈值',
            'risk': 'SA值较高，存在承接机会，需要盘中确认。',
            'advice': '关注开盘后实体方向和承接持续性'
        },
        
        # 趋势场景
        'TREND_CONTINUE': {
            'context': '连涨趋势中',
            'action': '{gap_desc}{auction_pct}，进入趋势延续候选',
            'risk': '已有趋势基础，但能否延续需要盘中实体确认。',
            'advice': '观察回踩是否守住开盘价和短期支撑'
        },
        'TREND_ACCELERATE': {
            'context': '昨日趋势较强且量能活跃',
            'action': '{gap_desc}{auction_pct}，进入趋势加速候选',
            'risk': '昨日量价条件支持趋势加速，但需要盘中实体确认，避免追高误判。',
            'advice': '观察开盘后是否放量延续'
        }
    }
    
    @classmethod
    def generate(cls, row, scenario, market_oar=1.0):
        """
        生成评语
        
        参数:
            row: 数据行
            scenario: 场景类型
            market_oar: 市场OAR
            
        返回:
            dict: {context, action, risk, advice}
        """
        template = cls.TEMPLATES.get(scenario)
        if not template:
            return None
        
        # 计算变量
        variables = cls._calc_variables(row, market_oar)
        
        # 填充模板
        result = {}
        for key, tmpl in template.items():
            try:
                result[key] = tmpl.format(**variables)
            except KeyError:
                result[key] = tmpl
        
        return SignalInterpreter.interpret(
            name=str(row.get("name", row.get("_name", ""))),
            target_type=str(row.get("target_type", "")),
            scenario=scenario,
            category="trap" if scenario.startswith("TRAP") else "reversal" if scenario.startswith("REVERSAL") else "trend",
            row=row,
            market_oar=market_oar,
            fallback=result,
        )
    
    @classmethod
    def _calc_variables(cls, row, market_oar):
        """计算模板变量"""
        
        # 基础数值
        amt_rank = row.get('amt_rank', 99) or 99
        pos_5d = row.get('pos_5d', 50) or 50
        auction_pct = row.get('auction_pct', 0) or 0
        body_pct = row.get('body_pct', 0) or 0
        prev_pct = row.get('prev_pct', 0) or 0
        prev_body_pct = row.get('prev_body_pct', 0) or 0
        prev_vol_ratio = row.get('prev_vol_ratio', 1.0) or 1.0
        
        variables = {
            'rank': f"{amt_rank}",
            'pos_5d': f"{pos_5d:.0f}%",
            'auction_pct': f"{auction_pct:+.2f}%",
            'body_pct': f"{body_pct:+.2f}%",
            'prev_pct': f"{prev_pct:+.2f}%",
            'prev_body_pct': f"{prev_body_pct:+.2f}%",
            'prev_vol_ratio': f"{prev_vol_ratio:.1f}",
        }
        
        # 昨日K线描述
        variables['prev_kline'] = cls._describe_kline(prev_body_pct)
        
        # OAR描述
        if market_oar < 0.9:
            variables['oar_desc'] = '缩量环境'
            variables['oar_reason'] = '缩量环境不支持热门板块持续高举高打，高开消耗做多动能后易被抛压淹没。'
        elif market_oar > 1.2:
            variables['oar_desc'] = '放量环境'
            variables['oar_reason'] = ''
        else:
            variables['oar_desc'] = '平量环境'
            variables['oar_reason'] = ''
        
        # 缺口描述
        variables['gap_desc'] = cls._describe_gap(auction_pct)
        
        return variables
    
    @staticmethod
    def _describe_kline(body_pct):
        """描述K线形态"""
        if body_pct > 2.0:
            return '大阳线'
        elif body_pct > 0.5:
            return '阳线'
        elif body_pct < -2.0:
            return '大阴线'
        elif body_pct < -0.5:
            return '阴线'
        else:
            return '十字星'
    
    @staticmethod
    def _describe_gap(auction_pct):
        """描述缺口"""
        if auction_pct > 1.0:
            return '大幅高开'
        elif auction_pct > 0.3:
            return '高开'
        elif auction_pct < -1.0:
            return '大幅低开'
        elif auction_pct < -0.3:
            return '低开'
        else:
            return '平开'
