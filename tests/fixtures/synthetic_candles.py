"""Синтетические свечи для юнит-тестов."""

from typing import List

from ast_trader.core.models import Candle


def make_candles(
    prices: List[float], ts_start: int = 0, ts_step: int = 60_000
) -> List[Candle]:
    """Строит свечи из цен закрытия с минимальным диапазоном."""
    candles: List[Candle] = []
    for i, p in enumerate(prices):
        candles.append(
            Candle(
                ts=ts_start + i * ts_step,
                open=p,
                high=p + 0.01,
                low=p - 0.01,
                close=p,
                volume=1.0,
            )
        )
    return candles


def up_structure_prices() -> List[float]:
    """Цены для восходящей структуры: ЛОЙ(100) -> ХАЙ(200) -> ЛОЙ(150) -> ХАЙ(195)."""
    return (
        [104, 102, 100, 102, 104]
        + [110, 130, 150, 170, 190, 200]
        + [190, 180, 170, 160, 150]
        + [160, 170, 180, 190, 195]
        + [190, 185]
    )