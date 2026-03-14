from __future__ import annotations

from dataclasses import dataclass

from solbot.types import Candle, Position, Signal
from solbot.utils.indicators import atr, average_volume, realized_vol, rolling_high, rolling_low


@dataclass
class StrategyConfig:
    atr_period: int
    compression_lookback: int
    breakout_lookback: int
    vol_period: int
    min_realized_vol: float
    max_realized_vol: float
    atr_expansion_mult: float
    volume_confirm_mult: float
    max_spread_bps: float
    min_depth: float
    trend_ema_period: int
    take_profit_atr_mult: float
    stop_atr_mult: float
    trailing_atr_mult: float
    max_bars_in_trade: int
    cooldown_bars: int
    chop_threshold: float


class SolVolatilityBreakoutStrategy:
    """Primary strategy: breakout after compression with ATR and volume expansion."""

    def __init__(self, cfg: StrategyConfig) -> None:
        self.cfg = cfg
        self.cooldown_remaining = 0

    def _ema(self, values: list[float], period: int) -> float:
        if len(values) < period:
            return values[-1]
        k = 2 / (period + 1)
        ema = values[-period]
        for v in values[-period + 1 :]:
            ema = (v * k) + (ema * (1 - k))
        return ema

    def _chop_index(self, candles: list[Candle]) -> float:
        if len(candles) < self.cfg.compression_lookback + 1:
            return 1.0
        window = candles[-self.cfg.compression_lookback :]
        total_range = sum(c.high - c.low for c in window)
        net = abs(window[-1].close - window[0].open)
        if total_range <= 0:
            return 1.0
        return net / total_range

    def on_bar_close(
        self,
        candles: list[Candle],
        spread_bps: float,
        top_depth: float,
        position: Position | None,
        bars_in_position: int,
    ) -> Signal | None:
        if len(candles) < max(self.cfg.breakout_lookback, self.cfg.atr_period) + 2:
            return None

        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return None

        closes = [c.close for c in candles]
        current = candles[-1]
        current_atr = atr(candles, self.cfg.atr_period)
        rv = realized_vol(candles, self.cfg.vol_period)
        short_atr = atr(candles[-self.cfg.compression_lookback - 1 :], min(5, self.cfg.atr_period))

        if spread_bps > self.cfg.max_spread_bps or top_depth < self.cfg.min_depth:
            return None
        if not (self.cfg.min_realized_vol <= rv <= self.cfg.max_realized_vol):
            return None
        if current_atr <= 0 or short_atr <= 0:
            return None
        if short_atr > current_atr / self.cfg.atr_expansion_mult:
            return None
        if self._chop_index(candles) < self.cfg.chop_threshold:
            return None

        avg_vol = average_volume(candles[:-1], self.cfg.breakout_lookback)
        if avg_vol <= 0 or current.volume < avg_vol * self.cfg.volume_confirm_mult:
            return None

        trend = self._ema(closes, self.cfg.trend_ema_period)
        resistance = rolling_high(candles[:-1], self.cfg.breakout_lookback)
        support = rolling_low(candles[:-1], self.cfg.breakout_lookback)

        if position is not None:
            return self._manage_position(position, current, current_atr, bars_in_position)

        if current.close > resistance and current.close > trend:
            stop = current.close - current_atr * self.cfg.stop_atr_mult
            tp = current.close + current_atr * self.cfg.take_profit_atr_mult
            return Signal("buy", 1.0, stop, tp, "vol_breakout_long")

        if current.close < support and current.close < trend:
            stop = current.close + current_atr * self.cfg.stop_atr_mult
            tp = current.close - current_atr * self.cfg.take_profit_atr_mult
            return Signal("sell", 1.0, stop, tp, "vol_breakout_short")

        return None

    def _manage_position(self, position: Position, candle: Candle, current_atr: float, bars_in_position: int) -> Signal | None:
        if bars_in_position >= self.cfg.max_bars_in_trade:
            self.cooldown_remaining = self.cfg.cooldown_bars
            return Signal(
                side="sell" if position.side == "buy" else "buy",
                confidence=1.0,
                stop_price=position.stop_price,
                take_profit=position.take_profit,
                reason="time_stop",
            )

        if position.side == "buy":
            trailing = candle.close - current_atr * self.cfg.trailing_atr_mult
            if candle.low <= max(position.stop_price, trailing):
                self.cooldown_remaining = self.cfg.cooldown_bars
                return Signal("sell", 1.0, position.stop_price, position.take_profit, "stop_or_trail")
            if candle.high >= position.take_profit:
                self.cooldown_remaining = self.cfg.cooldown_bars
                return Signal("sell", 1.0, position.stop_price, position.take_profit, "take_profit")
        else:
            trailing = candle.close + current_atr * self.cfg.trailing_atr_mult
            if candle.high >= min(position.stop_price, trailing):
                self.cooldown_remaining = self.cfg.cooldown_bars
                return Signal("buy", 1.0, position.stop_price, position.take_profit, "stop_or_trail")
            if candle.low <= position.take_profit:
                self.cooldown_remaining = self.cfg.cooldown_bars
                return Signal("buy", 1.0, position.stop_price, position.take_profit, "take_profit")
        return None
