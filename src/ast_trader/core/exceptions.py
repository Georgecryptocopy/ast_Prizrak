"""Доменные исключения торговой системы."""


class AstError(Exception):
    """Базовое исключение системы."""


class InvalidCandleError(AstError):
    """Некорректная свеча (нарушение согласованности OHLC)."""


class NotEnoughDataError(AstError):
    """Недостаточно данных для расчёта."""