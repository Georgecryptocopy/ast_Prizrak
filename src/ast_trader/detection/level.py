"""Создание торговых уровней из пробитых структур.

Уровень создаётся, когда цена пробивает структуру (закрывается
за её границей). Направление пробоя определяет направление входа:

- пробой вверх → уровень LONG (вход на ретесте снизу)
- пробой вниз  → уровень SHORT (вход на ретесте сверху)

Стоп ставится по формуле из видео: 10-20% от размера базы,
за экстремальной шпилькой структуры.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import List, Sequence

from ast_trader.core.enums import Timeframe, TrendDirection
from ast_trader.core.models import (
    Candle,
    Structure,
    StructureStatus,
    TradeLevel,
    VolumeProfile,
)
from ast_trader.detection.volume_profile import calc_volume_profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LevelBuilderConfig:
    """Конфигурация построителя уровней."""

    # стоп = stop_pct от размера базы (в долях, например 0.15 = 15%)
    stop_pct: float = 0.15
    # минимальный стоп в % от цены (страховка от слишком узкого стопа)
    min_stop_pct: float = 0.005
    # макс. стоп в % (для крупных баз — не более 10%)
    max_stop_pct: float = 0.10
    # мин. баров закрытия за границей для подтверждения пробоя
    confirm_bars: int = 2
    # мин. % тела свечи за границей для признания пробоя
    body_pct_beyond: float = 0.60
    # параметры профиля объёма
    vp_bins: int = 20
    vp_va_pct: float = 70.0


class LevelBuilder:
    """Строит торговые уровни из пробитых структур."""

    def __init__(self, config: LevelBuilderConfig, timeframe: Timeframe) -> None:
        self._cfg = config
        self._tf = timeframe

    def from_structure(
        self,
        structure: Structure,
        candles: Sequence[Candle],
        current_bar_index: int,
    ) -> TradeLevel | None:
        """Создаёт уровень, если структура пробита.

        Возвращает None, если пробой ещё не подтверждён.
        """
        if structure.status in (StructureStatus.BROKEN_UP, StructureStatus.BROKEN_DOWN):
            logger.debug("Структура %s уже пробита ранее — пропуск", structure.id[:8])
            return None

        # проверяем пробой
        break_dir = self._check_breakout(structure, candles, current_bar_index)
        if break_dir is None:
            return None

        # профиль объёма внутри структуры
        try:
            vp = calc_volume_profile(
                candles,
                top=structure.top,
                bottom=structure.bottom,
                bins=self._cfg.vp_bins,
                va_pct=self._cfg.vp_va_pct,
            )
        except ValueError as e:
            logger.warning("Не удалось построить профиль объёма: %s", e)
            return None

        # стоп по формуле из видео
        sl = self._calc_stop(structure, break_dir)

        # оценка силы уровня
        strength = self._calc_strength(structure, vp, candles)

        level = TradeLevel(
            id=str(uuid.uuid4()),
            structure_id=structure.id,
            timeframe=self._tf,
            direction=break_dir,
            poc=vp.poc,
            vah=vp.vah,
            val=vp.val,
            top=structure.top,
            bottom=structure.bottom,
            sl=sl,
            tp=None,  # цель пока не ищем — это отдельный модуль
            created_ts=candles[current_bar_index].ts,
            status="ACTIVE",
            strength=strength,
        )

        logger.info(
            "Уровень создан: id=%s dir=%s POC=%.2f SL=%.2f strength=%.2f",
            level.id[:8], level.direction.value, level.poc, level.sl, level.strength,
        )
        return level

    # ──────────────────────────────────────────────────────────
    def _check_breakout(
        self,
        structure: Structure,
        candles: Sequence[Candle],
        current_bar_index: int,
    ) -> TrendDirection | None:
        """Проверяет, пробита ли структура.

        Пробой:
        - закрытие тела свечи за границей на >= body_pct_beyond%
        - подтверждение в течение confirm_bars баров

        :return: направление пробоя (UP/DOWN) или None
        """
        if current_bar_index < self._cfg.confirm_bars:
            return None

        # проверяем последние confirm_bars баров
        for j in range(self._cfg.confirm_bars):
            idx = current_bar_index - j
            if idx < 0 or idx >= len(candles):
                return None
            c = candles[idx]
            c.validate()

            body_top = max(c.open, c.close)
            body_bot = min(c.open, c.close)
            body_len = max(body_top - body_bot, 1e-12)

            # пробой вверх: тело закрылось над верхней границей
            if body_top > structure.top:
                part_beyond = (body_top - structure.top) / body_len
                if part_beyond >= self._cfg.body_pct_beyond:
                    return TrendDirection.UP

            # пробой вниз: тело закрылось под нижней границей
            if body_bot < structure.bottom:
                part_beyond = (structure.bottom - body_bot) / body_len
                if part_beyond >= self._cfg.body_pct_beyond:
                    return TrendDirection.DOWN

        return None

    # ──────────────────────────────────────────────────────────
    def _calc_stop(self, structure: Structure, direction: TrendDirection) -> float:
        """Стоп по формуле: 10-20% от размера базы, не более 10%."""
        size_pct = (structure.top - structure.bottom) / structure.bottom
        stop_frac = size_pct * self._cfg.stop_pct
        stop_frac = max(self._cfg.min_stop_pct, min(stop_frac, self._cfg.max_stop_pct))

        if direction is TrendDirection.UP:
            # LONG: стоп за нижней границей структуры
            return structure.bottom * (1.0 - stop_frac)
        else:
            # SHORT: стоп за верхней границей структуры
            return structure.top * (1.0 + stop_frac)

    # ──────────────────────────────────────────────────────────
    def _calc_strength(
        self,
        structure: Structure,
        vp: VolumeProfile,
        candles: Sequence[Candle],
    ) -> float:
        """Простая оценка силы уровня.

        Формула: объём × множитель ТФ × длительность структуры.
        В следующих итерациях добавим касания, пивоты, скоринг.
        """
        vol_score = min(vp.total_volume / max(1.0, vp.total_volume), 5.0)
        duration = max(1, structure.p3_index - structure.p1_index)
        dur_score = min(duration / 20.0, 3.0)
        tf_mult = {
            Timeframe.M1: 0.5, Timeframe.M5: 0.7, Timeframe.M15: 0.9,
            Timeframe.M30: 1.0, Timeframe.H1: 1.2, Timeframe.H4: 1.5,
            Timeframe.D1: 2.0, Timeframe.W1: 2.5,
        }.get(self._tf, 1.0)
        return round((vol_score + dur_score) * tf_mult, 2)