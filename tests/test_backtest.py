from __future__ import annotations

from datetime import datetime, timedelta, timezone

from solbot.backtest.engine import BacktestEngine
from solbot.portfolio.account import PortfolioManager
from solbot.risk.manager import RiskConfig, RiskManager
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy, StrategyConfig
from solbot.types import Candle


def test_backtest_runs() -> None:
    candles = []
    px = 100.0
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(300):
        change = 1.001 if i % 10 else 1.01
        o = px
        c = px * change
        candles.append(Candle(start + timedelta(minutes=i), o, max(o, c) * 1.001, min(o, c) * 0.999, c, 120 + i))
        px = c

    strategy = SolVolatilityBreakoutStrategy(
        StrategyConfig(14, 20, 30, 20, 0.0, 1.0, 1.2, 1.0, 10.0, 1.0, 20, 2.0, 1.0, 1.0, 60, 5, 0.01)
    )
    risk = RiskManager(RiskConfig(0.005, 0.05, 5, 1, 1_000_000, 2.0, 20.0, 6, 120, 1.0, 30))
    engine = BacktestEngine(strategy, risk, PortfolioManager(10000, "SOL"), fee_bps=2, slippage_bps=1)
    result = engine.run(candles)
    assert result.final_equity > 0
