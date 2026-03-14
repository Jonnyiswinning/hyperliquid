from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solbot.risk.manager import RiskConfig, RiskManager
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy, StrategyConfig
from solbot.types import BotState, Candle


def gen_candles(n: int) -> list[Candle]:
    ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
    out = []
    price = 100.0
    for i in range(n):
        drift = 0.01 if i % 7 == 0 else 0.001
        open_ = price
        close = price * (1 + drift)
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        out.append(Candle(ts=ts + timedelta(minutes=i), open=open_, high=high, low=low, close=close, volume=100 + i))
        price = close
    return out


def test_position_size_nonzero() -> None:
    rm = RiskManager(
        RiskConfig(
            per_trade_risk_pct=0.005,
            daily_loss_limit_pct=0.02,
            max_consecutive_losses=3,
            max_positions=1,
            max_gross_exposure_usd=10000,
            max_leverage=2.0,
            max_slippage_bps=10,
            api_failure_kill_switch=4,
            stale_data_seconds=60,
            extreme_vol_lockout=0.05,
            lockout_minutes=10,
        )
    )
    size = rm.compute_position_size(10000, 100, 98)
    assert size > 0


def test_strategy_signal_on_breakout() -> None:
    strategy = SolVolatilityBreakoutStrategy(
        StrategyConfig(
            atr_period=14,
            compression_lookback=20,
            breakout_lookback=25,
            vol_period=20,
            min_realized_vol=0.0,
            max_realized_vol=1.0,
            atr_expansion_mult=0.5,
            volume_confirm_mult=1.0,
            max_spread_bps=10,
            min_depth=10,
            trend_ema_period=20,
            take_profit_atr_mult=2,
            stop_atr_mult=1,
            trailing_atr_mult=1,
            max_bars_in_trade=30,
            cooldown_bars=3,
            chop_threshold=0.01,
        )
    )
    candles = gen_candles(80)
    candles[-1].close = max(c.high for c in candles[-30:-1]) * 1.01
    candles[-1].high = candles[-1].close * 1.001
    signal = strategy.on_bar_close(candles, spread_bps=2.0, top_depth=500, position=None, bars_in_position=0)
    assert signal is not None
    assert signal.side in {"buy", "sell"}


def test_risk_rejects_stale_data() -> None:
    rm = RiskManager(
        RiskConfig(
            per_trade_risk_pct=0.005,
            daily_loss_limit_pct=0.02,
            max_consecutive_losses=3,
            max_positions=1,
            max_gross_exposure_usd=10000,
            max_leverage=2.0,
            max_slippage_bps=10,
            api_failure_kill_switch=4,
            stale_data_seconds=60,
            extreme_vol_lockout=0.05,
            lockout_minutes=10,
        )
    )
    decision = rm.evaluate_pre_trade(
        signal=type("S", (), {})(),
        equity=1000,
        state=BotState(),
        snapshot_age_seconds=120,
        open_positions=[],
        gross_exposure=0,
        realized_volatility=0.01,
    )
    assert not decision.allowed
    assert decision.reason == "stale_data"
