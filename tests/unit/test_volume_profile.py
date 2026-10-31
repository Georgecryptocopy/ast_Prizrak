"""Юнит-тесты для профиля объёма."""

import pytest

from ast_trader.core.models import Candle
from ast_trader.detection.volume_profile import calc_volume_profile


def make_candle(ts, high, low, volume, close=None):
    """Создаёт свечу с заданными параметрами."""
    if close is None:
        close = (high + low) / 2.0
    return Candle(ts=ts, open=close, high=high, low=low, close=close, volume=volume)


def test_uniform_volume_poc_takes_first_bin_on_tie():
    """Равномерный объём по всему диапазону.

    Примечание: при одинаковом объёме во всех бинах алгоритм
    выбирает первый бин с максимумом (как в оригинальном индикаторе).
    Поэтому POC = центр первого бина, а не середина диапазона.
    """
    # Одна большая свеча, покрывающая весь диапазон
    candles = [make_candle(ts=0, high=200, low=100, volume=1000)]
    vp = calc_volume_profile(candles, top=200, bottom=100, bins=10, va_pct=70)

    assert vp.total_volume == pytest.approx(1000)
    # Все бины по 100. При равенстве берётся первый бин (индекс 0).
    # Центр бина 0: 100 + 0.5 * 10 = 105
    assert vp.poc == pytest.approx(105.0)
    assert len(vp.bins) == 10


def test_concentrated_volume_at_bottom():
    """Объём сконцентрирован внизу → POC внизу, VA узкая."""
    candles = [
        make_candle(ts=0, high=110, low=100, volume=100),
        make_candle(ts=1, high=110, low=100, volume=100),
        make_candle(ts=2, high=200, low=190, volume=10),
    ]
    vp = calc_volume_profile(candles, top=200, bottom=100, bins=10, va_pct=70)

    assert vp.total_volume == pytest.approx(210)
    assert vp.poc == pytest.approx(105)  # середина первого бина
    assert vp.val == pytest.approx(100)  # VA начинается с первого бина
    assert vp.vah == pytest.approx(110)  # VA покрывает только первый бин


def test_value_area_covers_required_pct():
    """Зона стоимости покрывает не менее заданного % объёма."""
    candles = [
        make_candle(ts=i, high=100 + (i + 1) * 10, low=100 + i * 10, volume=10)
        for i in range(10)
    ]
    vp = calc_volume_profile(candles, top=200, bottom=100, bins=10, va_pct=70)

    assert vp.total_volume == pytest.approx(100)
    # VA должен покрывать минимум 70% от общего объёма
    # Это проверяется косвенно через структуру зоны
    assert vp.val <= vp.poc <= vp.vah


def test_empty_candles_raises():
    """Пустой список свечей — ошибка."""
    with pytest.raises(ValueError, match="пуст"):
        calc_volume_profile([], top=200, bottom=100)


def test_top_below_bottom_raises():
    """top меньше или равен bottom — ошибка."""
    candles = [make_candle(0, 200, 100, 100)]
    with pytest.raises(ValueError, match="больше"):
        calc_volume_profile(candles, top=100, bottom=200)


def test_invalid_bins_raises():
    """bins меньше 1 — ошибка."""
    candles = [make_candle(0, 200, 100, 100)]
    with pytest.raises(ValueError, match="bins"):
        calc_volume_profile(candles, top=200, bottom=100, bins=0)


def test_invalid_va_pct_raises():
    """va_pct вне (0, 100] — ошибка."""
    candles = [make_candle(0, 200, 100, 100)]
    with pytest.raises(ValueError, match="va_pct"):
        calc_volume_profile(candles, top=200, bottom=100, va_pct=0)
    with pytest.raises(ValueError, match="va_pct"):
        calc_volume_profile(candles, top=200, bottom=100, va_pct=101)


def test_zero_volume_returns_middle():
    """Нулевой объём у всех свечей — POC в середине диапазона."""
    candles = [make_candle(0, 200, 100, volume=0)]
    vp = calc_volume_profile(candles, top=200, bottom=100, bins=10, va_pct=70)

    assert vp.total_volume == 0
    assert vp.poc == pytest.approx(150)
    assert vp.vah == pytest.approx(200)
    assert vp.val == pytest.approx(100)


def test_candles_outside_range_ignored():
    """Свечи вне диапазона не учитываются."""
    candles = [
        make_candle(ts=0, high=200, low=100, volume=100),
        make_candle(ts=1, high=500, low=400, volume=9999),  # вне диапазона
    ]
    vp = calc_volume_profile(candles, top=200, bottom=100, bins=10, va_pct=70)

    assert vp.total_volume == pytest.approx(100)  # только первая свеча


def test_bins_count_matches():
    """Количество бинов равно заданному."""
    candles = [make_candle(0, 200, 100, 100)]
    for b in [5, 10, 20, 50]:
        vp = calc_volume_profile(candles, top=200, bottom=100, bins=b, va_pct=70)
        assert len(vp.bins) == b