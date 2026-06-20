# -*- coding: utf-8 -*-

from analyzers.strategy import StrategyAnalyzer


def test_broad_environment_mixed_when_score_between_thresholds():
    analyzer = StrategyAnalyzer(None)
    env = analyzer._classify_broad_environment(1.5)
    assert env["label"] == "mixed"
    assert "结构" in env["advice"]


def test_broad_environment_stays_mixed_when_score_is_high_but_index_breadth_is_split():
    analyzer = StrategyAnalyzer(None)
    env = analyzer._classify_broad_environment(3.0, positive_count=2, negative_count=2)
    assert env["label"] == "mixed"


def test_structural_environment_can_be_strong_when_broad_is_only_mixed():
    analyzer = StrategyAnalyzer(None)
    indices_result = {
        "broad_env": {"label": "mixed"},
        "details": [
            {"name": "上证", "T": "-0.43% 放量"},
            {"name": "创业板", "T": "+2.05% 放量"},
            {"name": "科创50", "T": "+3.84% 放量"},
            {"name": "北证50", "T": "-1.18% 温和"},
        ],
    }
    top_etf = [
        {"name": "科创50ETF", "raw_pct": 4.02},
        {"name": "半导体", "raw_pct": 3.94},
        {"name": "AI人工智能", "raw_pct": 3.87},
        {"name": "创新药", "raw_pct": 3.22},
    ]
    bottom_etf = [
        {"name": "基建", "raw_pct": -2.12},
        {"name": "银行", "raw_pct": -2.42},
        {"name": "证券", "raw_pct": -2.87},
        {"name": "金融地产", "raw_pct": -3.07},
    ]
    mainlines = [
        {"industry": "数字芯片设计", "T": "+5.8% (0板) 连续领涨"},
        {"industry": "通信网络设备及器件", "T": "+6.7% (0板) 爆发领涨"},
        {"industry": "消费电子零部件及组装", "T": "+3.9% (0板) 爆发领涨"},
        {"industry": "集成电路制造", "T": "+7.3% (0板) 连续领涨"},
        {"industry": "印制电路板", "T": "+2.9% (0板) 连续领涨"},
    ]

    env = analyzer._analyze_structural_environment(indices_result, top_etf, bottom_etf, mainlines)
    assert "结构" in env["judgement"]
    assert env["score"] >= 5
    assert "主线" in env["advice"]
