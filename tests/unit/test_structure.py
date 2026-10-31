"""Юнит-тесты для детектора структур."""

import pytest

from ast_trader.core.enums import StructureStatus, Timeframe, TrendDirection
from ast_trader.core.exceptions import InvalidCandleError
from ast_trader.core.models import Candle
from ast_trader.detection.structure import StructureDetector, StructureDetectorConfig
from tests.fixtures.synthetic_candles import make_candles, up_structure_prices


def _detector(**overrides):
    """Создаёт детектор с маленьким окном пивотов для тестов."""
    cfg = StructureDetectorConfig(
        pivot_left=2,
        pivot_right=2,
        min_retrace=0.5,
        max_retrace=1.5,
        p3_break_tolerance=0.02,
        **overrides,
    )
    return StructureDetector(cfg, Timeframe.M15)


def test_detects_up_structure_with_50pct_retrace():
    """Восходящая структура с откатом ровно 50% должна найтись."""
    candles = make_candles(up_structure_prices())
    structures = _detector().detect(candles)

    assert len(structures) == 1
    s = structures[0]
    assert s.direction is TrendDirection.UP
    assert s.top == pytest.approx(200.01)
    assert s.bottom == pytest.approx(149.99)
    assert s.retrace_ratio == pytest.approx(0.5, abs=0.001)
    assert s.status is StructureStatus.ACTIVE


def test_no_structure_when_retrace_below_threshold():
    """Откат меньше 50% — структура не создаётся."""
    prices = (
        [104, 102, 100, 102, 104]
        + [110, 130, 150, 170, 190, 200]
        + [190, 180, 170]
        + [180, 190, 195]
        + [190, 185]
    )
    candles = make_candles(prices)
    assert _detector().detect(candles) == []


def test_no_structure_when_p3_breaks_extremum():
    """Третья точка сильно пробила первый хай — продолжение тренда, не база."""
    prices = (
        [104, 102, 100, 102, 104]
        + [110, 130, 150, 170, 190, 200]
        + [190, 180, 170, 160, 150]
        + [170, 190, 210, 220]
        + [210, 205]
    )
    candles = make_candles(prices)
    assert _detector().detect(candles) == []


def test_detects_down_structure():
    """Нисходящая структура (зеркальный паттерн)."""
    prices = (
        [196, 198, 200, 198, 196]
        + [190, 170, 150, 130, 110, 100]
        + [110, 120, 130, 140, 150]
        + [140, 130, 120, 110, 105]
        + [110, 115]
    )
    candles = make_candles(prices)
    structures = _detector().detect(candles)

    down = [s for s in structures if s.direction is TrendDirection.DOWN]
    assert len(down) == 1
    assert down[0].bottom == pytest.approx(99.99)
    assert down[0].top == pytest.approx(150.01)


def test_invalid_candle_raises():
    """Свеча с нарушенным порядком цен бросает исключение."""
    bad = Candle(ts=1, open=100, high=90, low=110, close=100, volume=1.0)
    with pytest.raises(InvalidCandleError):
        _detector().detect([bad] * 10)


def test_empty_input_returns_empty():
    """Пустой вход — пустой выход."""
    assert _detector().detect([]) == []


def test_too_few_candles_returns_empty():
    """Слишком мало свечей — пустой выход."""
    candles = make_candles([100, 101, 102])
    assert _detector().detect(candles) == []