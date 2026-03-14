from __future__ import annotations

from statistics import mean, pstdev

from solbot.types import Candle


def true_range(curr: Candle, prev: Candle) -> float:
    return max(curr.high - curr.low, abs(curr.high - prev.close), abs(curr.low - prev.close))


def atr(candles: list[Candle], period: int) -> float:
    if len(candles) <= period:
        return 0.0
    trs: list[float] = []
    for i in range(len(candles) - period, len(candles)):
        trs.append(true_range(candles[i], candles[i - 1]))
    return mean(trs)


def realized_vol(candles: list[Candle], period: int) -> float:
    if len(candles) < period + 1:
        return 0.0
    returns = []
    for i in range(len(candles) - period, len(candles)):
        prev = candles[i - 1].close
        if prev <= 0:
            continue
        returns.append((candles[i].close / prev) - 1)
    if len(returns) < 2:
        return 0.0
    return pstdev(returns)


def rolling_high(candles: list[Candle], period: int) -> float:
    return max(c.high for c in candles[-period:]) if len(candles) >= period else 0.0


def rolling_low(candles: list[Candle], period: int) -> float:
    return min(c.low for c in candles[-period:]) if len(candles) >= period else 0.0


def average_volume(candles: list[Candle], period: int) -> float:
    if len(candles) < period:
        return 0.0
    return mean(c.volume for c in candles[-period:])
