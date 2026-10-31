"""Перечисления для торговой системы."""

from enum import Enum


class Timeframe(str, Enum):
    """Таймфреймы свечей."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class PivotKind(str, Enum):
    """Тип пивота: максимум или минимум."""
    HIGH = "high"
    LOW = "low"


class TrendDirection(str, Enum):
    """Направление тренда."""
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class StructureStatus(str, Enum):
    """Статус структуры в её жизненном цикле."""
    FORMING = "forming"
    ACTIVE = "active"
    BROKEN_UP = "broken_up"
    BROKEN_DOWN = "broken_down"
    EXPIRED = "expired"