"""Детекция подтверждённых пивотов (без репейнта)."""

import logging
from typing import List, Sequence

from ast_trader.core.models import Candle, Pivot, PivotKind

logger = logging.getLogger(__name__)


def detect_pivots(
    candles: Sequence[Candle],
    left: int,
    right: int,
) -> List[Pivot]:
    """Находит подтверждённые пивоты в последовательности свечей.

    :param candles: свечи, упорядоченные по возрастанию времени
    :param left: сколько баров слева для подтверждения
    :param right: сколько баров справа для подтверждения
    :return: список пивотов, отсортированный по индексу бара
    :raises ValueError: если left или right меньше 1
    """
    if left < 1 or right < 1:
        raise ValueError("left и right должны быть >= 1")

    n = len(candles)
    min_required = left + right + 1
    if n < min_required:
        logger.warning("Недостаточно свечей для пивотов: %d < %d", n, min_required)
        return []

    pivots: List[Pivot] = []
    for i in range(left, n - right):
        highs = [candles[j].high for j in range(i - left, i + right + 1)]
        lows = [candles[j].low for j in range(i - left, i + right + 1)]

        h = candles[i].high
        low = candles[i].low

        if h >= max(highs) and highs.count(h) == 1:
            pivots.append(
                Pivot(
                    index=i,
                    ts=candles[i].ts,
                    price=h,
                    kind=PivotKind.HIGH,
                    confirmed_index=i + right,
                )
            )

        if low <= min(lows) and lows.count(low) == 1:
            pivots.append(
                Pivot(
                    index=i,
                    ts=candles[i].ts,
                    price=low,
                    kind=PivotKind.LOW,
                    confirmed_index=i + right,
                )
            )

    pivots.sort(key=lambda p: (p.index, p.kind.value))
    logger.debug("Найдено пивотов: %d", len(pivots))
    return pivots