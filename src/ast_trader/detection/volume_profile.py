"""Профиль объёма: POC, VAH, VAL.

Разбивает ценовой диапазон на бины и распределяет объём свечей
пропорционально перекрытию свечи с бином. Находит точку максимального
объёма (POC) и зону стоимости (Value Area).

Алгоритм повторяет логику из оригинального индикатора (f_calcVP).
"""

import logging
from typing import Sequence

from ast_trader.core.models import Candle, VolumeBin, VolumeProfile

logger = logging.getLogger(__name__)


def calc_volume_profile(
    candles: Sequence[Candle],
    top: float,
    bottom: float,
    bins: int = 20,
    va_pct: float = 70.0,
) -> VolumeProfile:
    """Рассчитывает профиль объёма для диапазона [bottom, top].

    :param candles: свечи внутри структуры
    :param top: верхняя граница диапазона
    :param bottom: нижняя граница диапазона
    :param bins: количество бинов (по умолчанию 20)
    :param va_pct: процент объёма для зоны стоимости (по умолчанию 70)
    :return: VolumeProfile с POC, VAH, VAL и бинами
    :raises ValueError: при некорректных параметрах
    """
    if top <= bottom:
        raise ValueError(f"top ({top}) должен быть больше bottom ({bottom})")
    if bins < 1:
        raise ValueError(f"bins ({bins}) должен быть >= 1")
    if not (0.0 < va_pct <= 100.0):
        raise ValueError(f"va_pct ({va_pct}) должен быть в (0, 100]")
    if not candles:
        raise ValueError("список свечей пуст")

    bin_size = (top - bottom) / bins
    volumes = [0.0] * bins

    # Распределяем объём свечей по бинам пропорционально перекрытию
    for c in candles:
        c.validate()
        if c.volume <= 0:
            continue

        candle_high = min(c.high, top)
        candle_low = max(c.low, bottom)
        if candle_high <= candle_low:
            continue  # свеча вне диапазона

        candle_range = c.high - c.low
        if candle_range <= 0:
            # Плоская свеча: весь объём в бин по цене закрытия
            idx = int((c.close - bottom) / bin_size)
            idx = min(max(idx, 0), bins - 1)
            volumes[idx] += c.volume
            continue

        for b in range(bins):
            b_low = bottom + b * bin_size
            b_high = b_low + bin_size
            overlap = max(0.0, min(candle_high, b_high) - max(candle_low, b_low))
            if overlap > 0:
                volumes[b] += c.volume * (overlap / candle_range)

    total_volume = sum(volumes)

    # Формируем список бинов
    bins_list = tuple(
        VolumeBin(
            price_low=bottom + i * bin_size,
            price_high=bottom + (i + 1) * bin_size,
            volume=volumes[i],
        )
        for i in range(bins)
    )

    # Если объёма нет — возвращаем дефолт (середина диапазона)
    if total_volume <= 0:
        mid = (top + bottom) / 2.0
        logger.warning("Профиль объёма: нет объёма в диапазоне, возвращаю середину")
        return VolumeProfile(
            top=top, bottom=bottom,
            poc=mid, vah=top, val=bottom,
            total_volume=0.0, bins=bins_list,
        )

    # POC — бин с максимальным объёмом
    poc_idx = max(range(bins), key=lambda i: volumes[i])
    poc = bottom + (poc_idx + 0.5) * bin_size

    # Value Area — расширяем от POC, пока не наберём нужный % объёма
    va_target = total_volume * (va_pct / 100.0)
    va_vol = volumes[poc_idx]
    lo_idx = poc_idx
    hi_idx = poc_idx

    safety = 0
    while va_vol < va_target and safety < bins:
        below = volumes[lo_idx - 1] if lo_idx > 0 else 0.0
        above = volumes[hi_idx + 1] if hi_idx < bins - 1 else 0.0

        if below >= above and lo_idx > 0:
            lo_idx -= 1
            va_vol += below
        elif hi_idx < bins - 1:
            hi_idx += 1
            va_vol += above
        elif lo_idx > 0:
            lo_idx -= 1
            va_vol += below
        else:
            break
        safety += 1

    val = bottom + lo_idx * bin_size
    vah = bottom + (hi_idx + 1) * bin_size

    logger.debug(
        "Профиль объёма: POC=%.2f VAH=%.2f VAL=%.2f общий_объём=%.2f",
        poc, vah, val, total_volume,
    )

    return VolumeProfile(
        top=top, bottom=bottom,
        poc=poc, vah=vah, val=val,
        total_volume=total_volume, bins=bins_list,
    )