"""Юнит-тесты для детекции пивотов."""

import pytest

from ast_trader.core.models import Candle
from ast_trader.detection.pivots import detect_pivots
from tests.fixtures.synthetic_candles import make_candles


def test_detects_single_high_pivot():
    """Один чёткий хай в середине ряда — должен найтись один пивот-хай."""
    prices = [100, 101, 102, 103, 104, 105, 104, 103, 102, 101, 100]
    candles = make_candles(prices)
    pivots = detect_pivots(candles, left=2, right=2)
    highs = [p for p in pivots if p.kind.value == "high"]
    assert len(highs) == 1
    assert highs[0].index == 5
    assert highs[0].price == pytest.approx(105.01)


def test_detects_single_low_pivot():
    """Один чёткий лой в середине ряда — должен найтись один пивот-лой."""
    prices = [105, 104, 103, 102, 101, 100, 101, 102, 103, 104, 105]
    candles = make_candles(prices)
    pivots = detect_pivots(candles, left=2, right=2)
    lows = [p for p in pivots if p.kind.value == "low"]
    assert len(lows) == 1
    assert lows[0].index == 5
    assert lows[0].price == pytest.approx(99.99)


def test_not_enough_candles_returns_empty():
    """Слишком мало свечей — пустой список."""
    candles = make_candles([100, 101, 102])
    assert detect_pivots(candles, left=3, right=3) == []


def test_invalid_left_right_raises():
    """left или right < 1 должны бросать ValueError."""
    candles = make_candles([100] * 10)
    with pytest.raises(ValueError):
        detect_pivots(candles, left=0, right=2)
    with pytest.raises(ValueError):
        detect_pivots(candles, left=2, right=0)


def test_no_pivot_on_flat_plateau():
    """Плато из одинаковых хай — не пивот."""
    prices = [100, 101, 102, 105, 105, 102, 101, 100]
    candles = make_candles(prices)
    pivots = detect_pivots(candles, left=2, right=2)
    highs = [p for p in pivots if p.kind.value == "high"]
    assert len(highs) == 0