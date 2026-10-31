"""Детектор структур (баз накопления) по алгоритму авторов."""

import logging
import uuid
from dataclasses import dataclass
from typing import List, Sequence

from ast_trader.core.enums import PivotKind, StructureStatus, Timeframe, TrendDirection
from ast_trader.core.models import Candle, Pivot, Structure
from ast_trader.detection.pivots import detect_pivots

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StructureDetectorConfig:
    """Конфигурация детектора структур."""
    pivot_left: int = 5
    pivot_right: int = 5
    min_retrace: float = 0.5
    max_retrace: float = 1.5
    p3_break_tolerance: float = 0.02
    min_height_pct: float = 0.0


class StructureDetector:
    """Детектор структур/баз по алгоритму авторов."""

    def __init__(self, config: StructureDetectorConfig, timeframe: Timeframe) -> None:
        self._cfg = config
        self._tf = timeframe

    def detect(self, candles: Sequence[Candle]) -> List[Structure]:
        """Находит все структуры в последовательности свечей."""
        if len(candles) < 4:
            logger.debug("Слишком мало свечей (%d) — пропуск", len(candles))
            return []

        for c in candles:
            c.validate()

        pivots = detect_pivots(candles, self._cfg.pivot_left, self._cfg.pivot_right)
        if len(pivots) < 4:
            logger.debug("Недостаточно пивотов (%d) для структур", len(pivots))
            return []

        structures: List[Structure] = []
        structures.extend(self._detect_up(candles, pivots))
        structures.extend(self._detect_down(candles, pivots))
        structures.sort(key=lambda s: s.formed_ts)

        logger.info(
            "ТФ=%s: обнаружено структур=%d (пивотов=%d, свечей=%d)",
            self._tf.value, len(structures), len(pivots), len(candles),
        )
        return structures

    def _detect_up(self, candles: Sequence[Candle], pivots: List[Pivot]) -> List[Structure]:
        result: List[Structure] = []
        for i in range(len(pivots) - 3):
            l0, h1, l1, h2 = pivots[i], pivots[i + 1], pivots[i + 2], pivots[i + 3]

            if not (
                l0.kind is PivotKind.LOW
                and h1.kind is PivotKind.HIGH
                and l1.kind is PivotKind.LOW
                and h2.kind is PivotKind.HIGH
            ):
                continue

            if not (l0.index < h1.index < l1.index < h2.index):
                continue

            impulse = h1.price - l0.price
            if impulse <= 0:
                continue

            retrace = (h1.price - l1.price) / impulse
            if not (self._cfg.min_retrace <= retrace <= self._cfg.max_retrace):
                continue

            if h2.price > h1.price * (1.0 + self._cfg.p3_break_tolerance):
                continue

            top, bottom = h1.price, l1.price
            if not self._height_ok(top, bottom):
                continue

            result.append(
                self._build(
                    direction=TrendDirection.UP,
                    top=top,
                    bottom=bottom,
                    p1=h1, p2=l1, p3=h2,
                    impulse_start=l0.price,
                    impulse_end=h1.price,
                    retrace=retrace,
                    candles=candles,
                )
            )
        return result

    def _detect_down(self, candles: Sequence[Candle], pivots: List[Pivot]) -> List[Structure]:
        result: List[Structure] = []
        for i in range(len(pivots) - 3):
            h0, l1, h1, l2 = pivots[i], pivots[i + 1], pivots[i + 2], pivots[i + 3]

            if not (
                h0.kind is PivotKind.HIGH
                and l1.kind is PivotKind.LOW
                and h1.kind is PivotKind.HIGH
                and l2.kind is PivotKind.LOW
            ):
                continue

            if not (h0.index < l1.index < h1.index < l2.index):
                continue

            impulse = h0.price - l1.price
            if impulse <= 0:
                continue

            retrace = (h1.price - l1.price) / impulse
            if not (self._cfg.min_retrace <= retrace <= self._cfg.max_retrace):
                continue

            if l2.price < l1.price * (1.0 - self._cfg.p3_break_tolerance):
                continue

            top, bottom = h1.price, l1.price
            if not self._height_ok(top, bottom):
                continue

            result.append(
                self._build(
                    direction=TrendDirection.DOWN,
                    top=top,
                    bottom=bottom,
                    p1=l1, p2=h1, p3=l2,
                    impulse_start=h0.price,
                    impulse_end=l1.price,
                    retrace=retrace,
                    candles=candles,
                )
            )
        return result

    def _height_ok(self, top: float, bottom: float) -> bool:
        if bottom <= 0:
            return False
        height_pct = (top - bottom) / bottom * 100.0
        return height_pct >= self._cfg.min_height_pct

    def _build(
        self,
        *,
        direction: TrendDirection,
        top: float,
        bottom: float,
        p1: Pivot,
        p2: Pivot,
        p3: Pivot,
        impulse_start: float,
        impulse_end: float,
        retrace: float,
        candles: Sequence[Candle],
    ) -> Structure:
        formed_ts = (
            candles[p3.confirmed_index].ts
            if p3.confirmed_index < len(candles)
            else candles[-1].ts
        )
        return Structure(
            id=str(uuid.uuid4()),
            timeframe=self._tf,
            direction=direction,
            top=top,
            bottom=bottom,
            p1_index=p1.index,
            p2_index=p2.index,
            p3_index=p3.index,
            impulse_start_price=impulse_start,
            impulse_end_price=impulse_end,
            retrace_ratio=round(retrace, 4),
            formed_ts=formed_ts,
            status=StructureStatus.ACTIVE,
        )