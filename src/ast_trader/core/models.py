"""Модели данных: свеча, пивот, структура, профиль объёма.

Все модели типизированы и снабжены валидацией там, где это критично
для корректности расчётов (в первую очередь — свечи).
"""

from __future__ import annotations

from dataclasses import dataclass

from ast_trader.core.enums import (
    PivotKind,
    StructureStatus,
    Timeframe,
    TrendDirection,
)
from ast_trader.core.exceptions import InvalidCandleError

__all__ = [
    "Candle",
    "Pivot",
    "Structure",
    "VolumeBin",
    "VolumeProfile",
]


@dataclass(frozen=True)
class Candle:
    """Одна свеча. Неизменяемая.

    Инварианты:
    - high >= max(open, close)
    - low  <= min(open, close)
    - high >= low
    - volume >= 0
    """

    ts: int          # время открытия в unix-миллисекундах
    open: float
    high: float
    low: float
    close: float
    volume: float

    def validate(self) -> None:
        """Проверяет согласованность OHLC и объёма.

        :raises InvalidCandleError: при нарушении целостности данных
        """
        if self.high < self.low:
            raise InvalidCandleError(f"high < low при ts={self.ts}")
        if self.high < max(self.open, self.close):
            raise InvalidCandleError(f"high ниже тела свечи при ts={self.ts}")
        if self.low > min(self.open, self.close):
            raise InvalidCandleError(f"low выше тела свечи при ts={self.ts}")
        if self.volume < 0:
            raise InvalidCandleError(f"отрицательный объём при ts={self.ts}")


@dataclass(frozen=True)
class Pivot:
    """Подтверждённый пивот (точка разворота).

    Пивот становится доступным только после прохождения
    `right` баров справа — это защита от репейнта.
    """

    index: int            # индекс бара, на котором пивот
    ts: int               # время бара пивота
    price: float          # цена пивота
    kind: PivotKind       # HIGH или LOW
    confirmed_index: int  # индекс бара, на котором пивот подтверждён


@dataclass
class Structure:
    """Структура (база накопления).

    Границы фиксируются по первым двум структурным точкам
    и не двигаются без отдельного события расширения.
    """

    id: str
    timeframe: Timeframe
    direction: TrendDirection
    top: float                     # верхняя граница (по первой точке)
    bottom: float                  # нижняя граница (по второй точке)
    p1_index: int                  # индекс первой структурной точки
    p2_index: int                  # индекс второй структурной точки
    p3_index: int                  # индекс третьей (подтверждающей) точки
    impulse_start_price: float     # начало импульса
    impulse_end_price: float       # конец импульса (первый хай/лой)
    retrace_ratio: float           # откат / импульс
    formed_ts: int                 # время формирования (подтверждение 3-й точки)
    status: StructureStatus = StructureStatus.FORMING


@dataclass(frozen=True)
class VolumeBin:
    """Один бин профиля объёма."""

    price_low: float
    price_high: float
    volume: float


@dataclass(frozen=True)
class VolumeProfile:
    """Профиль объёма структуры."""

    top: float
    bottom: float
    poc: float                     # Point of Control — цена с макс. объёмом
    vah: float                     # верхняя граница зоны стоимости
    val: float                     # нижняя граница зоны стоимости
    total_volume: float            # суммарный объём в диапазоне
    bins: tuple[VolumeBin, ...]    # все бины (неизменяемый кортеж)


# Будущие модели (добавим на следующих этапах):
# - TradeLevel   (уровень с POC/VAH/VAL, SL/TP, статусом)
# - Position     (позиция с тейками, стопами, доборами, раннером)
# - Order        (ордер для исполнения на бирже)

@dataclass
class TradeLevel:
    """Торговый уровень, созданный после пробоя структуры.

    Связывает структуру, профиль объёма и торговые параметры
    (направление, стоп, тейк, статус).
    """

    id: str
    structure_id: str             # id исходной структуры
    timeframe: Timeframe
    direction: TrendDirection     # направление пробоя (вход в эту сторону)
    poc: float                    # главная точка входа
    vah: float                    # верхняя граница зоны стоимости
    val: float                    # нижняя граница зоны стоимости
    top: float                    # верх структуры
    bottom: float                 # низ структуры
    sl: float                     # стоп-лосс
    tp: float | None = None       # целевой уровень (пока не ищем)
    created_ts: int = 0
    status: str = "ACTIVE"        # ACTIVE / WORKED_OFF / INVALIDATED / FLIPPED
    strength: float = 0.0         # сила уровня (для ранжирования)