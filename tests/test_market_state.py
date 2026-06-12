# -*- coding: utf-8 -*-

from datetime import datetime

from core.intraday_monitor import MarketPhase, MarketState


def test_market_phase_boundaries():
    cases = [
        (datetime(2026, 1, 2, 9, 14), MarketPhase.PRE_OPEN),
        (datetime(2026, 1, 2, 9, 15), MarketPhase.CALL_AUCTION),
        (datetime(2026, 1, 2, 9, 25), MarketPhase.AUCTION_END),
        (datetime(2026, 1, 2, 9, 30), MarketPhase.CONTINUOUS_AM),
        (datetime(2026, 1, 2, 11, 30), MarketPhase.NOON_BREAK),
        (datetime(2026, 1, 2, 13, 0), MarketPhase.CONTINUOUS_PM),
        (datetime(2026, 1, 2, 14, 57), MarketPhase.CLOSE_AUCTION),
        (datetime(2026, 1, 2, 15, 0), MarketPhase.CLOSED),
    ]

    for now, expected in cases:
        assert MarketState.get_current_phase(now) == expected


def test_should_collect_includes_noon_break_after_auction_end():
    assert not MarketState.should_collect(datetime(2026, 1, 2, 9, 20))
    assert MarketState.should_collect(datetime(2026, 1, 2, 9, 25))
    assert MarketState.should_collect(datetime(2026, 1, 2, 12, 0))
    assert not MarketState.should_collect(datetime(2026, 1, 2, 15, 1))
