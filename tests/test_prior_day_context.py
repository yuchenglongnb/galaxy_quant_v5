import json
from pathlib import Path

from analyzers.context.prior_day_context import PriorDayContextLoader
from analyzers.context.prior_day_readthrough import PriorDayReadthroughBuilder


class DummyDataManager:
    def __init__(self, window):
        self._window = window

    def get_analysis_window_days(self, target_date, lookback=2):
        return list(self._window)


def _write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_prior_day_context_available(tmp_path, monkeypatch):
    analysis_root = tmp_path / "analysis" / "daily"
    validation_root = tmp_path / "validation" / "daily"
    prev_date = "20260623"

    _write_text(
        analysis_root / prev_date / "auction_review.json",
        json.dumps(
            {
                "market_regime": {"label": "risk_off"},
                "environment_gate": {"decision": "selective_reversal_only"},
                "leading_clusters": ["数字芯片设计", "证券"],
                "intraday_confirmation_summary": {"available": False},
            },
            ensure_ascii=False,
        ),
    )
    _write_text(
        validation_root / prev_date / "signal_metrics.csv",
        "date,signal_category,trigger_count,success_rate\n"
        "20260623,trap,14,100\n"
        "20260623,reversal,8,25\n"
        "20260623,trend,66,27.27\n",
    )
    _write_text(
        validation_root / prev_date / "signal_detail.csv",
        "date,actionable\n"
        "20260623,false\n"
        "20260623,false\n"
        "20260623,false\n",
    )

    monkeypatch.setattr(PriorDayContextLoader, "ANALYSIS_DAILY_ROOT", analysis_root)
    monkeypatch.setattr(PriorDayContextLoader, "VALIDATION_DAILY_ROOT", validation_root)

    context = PriorDayContextLoader.load(20260624, data_manager=DummyDataManager([20260623, 20260624]))

    assert context["available"] is True
    assert context["prev_trade_date"] == "20260623"
    assert context["market_regime"] == "risk_off"
    assert context["environment_decision"] == "selective_reversal_only"
    assert context["leading_clusters"] == ["数字芯片设计", "证券"]
    assert context["bias"]["trend_bias"] == "negative"
    assert context["bias"]["cp_bias"] == "positive"
    assert context["context_confidence"] == "medium"
    assert context["data_quality"]["signal_metrics_available"] is True
    assert context["readthrough"]["confidence"] == "medium"
    assert "高 CP 票继续警惕兑现风险。" in context["readthrough"]["risk_points"]


def test_prior_day_context_missing_files_returns_fallback(tmp_path, monkeypatch):
    analysis_root = tmp_path / "analysis" / "daily"
    validation_root = tmp_path / "validation" / "daily"
    monkeypatch.setattr(PriorDayContextLoader, "ANALYSIS_DAILY_ROOT", analysis_root)
    monkeypatch.setattr(PriorDayContextLoader, "VALIDATION_DAILY_ROOT", validation_root)

    context = PriorDayContextLoader.load(20260624, data_manager=DummyDataManager([20260623, 20260624]))

    assert context["available"] is False
    assert context["context_confidence"] == "low"
    assert "prior_day_context_unavailable" in context["notes"]
    assert "前一日语境数据不足" in context["readthrough"]["headline"]


def test_readthrough_low_confidence_stays_conservative():
    context = {
        "available": True,
        "context_confidence": "low",
        "signal_metrics": {},
        "leading_clusters": [],
    }
    readthrough = PriorDayReadthroughBuilder.build(context)
    assert readthrough["confidence"] == "low"
    assert readthrough["focus_points"] == []
    assert "前一日语境数据不足" in readthrough["headline"]
def test_readthrough_missing_category_rates_is_conservative():
    result = PriorDayReadthroughBuilder.build({
        "available": True,
        "context_confidence": "medium",
        "market_regime": "continuation",
        "signal_metrics": {},
        "leading_clusters": [],
    })

    assert result["bias"] == "trend_continuation_check"
    assert result["confidence"] == "medium"
