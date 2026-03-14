from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean

from solbot.execution.executor import PaperExecutor
from solbot.portfolio.account import PortfolioManager
from solbot.risk.manager import RiskManager
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy
from solbot.types import Candle, OrderRequest
from solbot.utils.indicators import realized_vol


@dataclass
class BacktestResult:
    trades: int
    win_rate: float
    profit_factor: float
    sharpe: float
    max_drawdown: float
    expectancy: float
    avg_hold_minutes: float
    exposure_time: float
    final_equity: float


class BacktestEngine:
    def __init__(
        self,
        strategy: SolVolatilityBreakoutStrategy,
        risk: RiskManager,
        portfolio: PortfolioManager,
        fee_bps: float,
        slippage_bps: float,
    ) -> None:
        self.strategy = strategy
        self.risk = risk
        self.portfolio = portfolio
        self.executor = PaperExecutor(fee_bps=fee_bps, slippage_bps=slippage_bps, seen_client_order_ids=set())

    def run(self, candles: list[Candle], spread_bps: float = 2.0, depth: float = 1000.0) -> BacktestResult:
        equity_curve = [self.portfolio.state.equity]
        hold_bars = 0
        total_bars = 0

        for i in range(60, len(candles)):
            window = candles[: i + 1]
            last = window[-1]
            total_bars += 1
            self.portfolio.mark_to_market(last.close)
            if self.portfolio.state.position:
                hold_bars += 1

            signal = self.strategy.on_bar_close(
                candles=window,
                spread_bps=spread_bps,
                top_depth=depth,
                position=self.portfolio.state.position,
                bars_in_position=self.portfolio.state.bars_in_position,
            )
            if signal is None:
                equity_curve.append(self.portfolio.state.equity)
                continue

            rv = realized_vol(window, 20)
            decision = self.risk.evaluate_pre_trade(
                signal=signal,
                equity=self.portfolio.state.equity,
                state=type("X", (), {"locked_until": None, "consecutive_losses": 0, "daily_loss": 0.0, "api_failures": 0})(),
                snapshot_age_seconds=0,
                open_positions=[self.portfolio.state.position] if self.portfolio.state.position else [],
                gross_exposure=self.portfolio.state.gross_exposure,
                realized_volatility=rv,
            )
            if not decision.allowed:
                equity_curve.append(self.portfolio.state.equity)
                continue

            size = self.risk.compute_position_size(self.portfolio.state.equity, last.close, signal.stop_price)
            if size <= 0:
                equity_curve.append(self.portfolio.state.equity)
                continue

            if self.portfolio.state.position is None and signal.reason.startswith("vol_breakout"):
                fill = self.executor.place(
                    OrderRequest(
                        symbol=self.portfolio.symbol,
                        side=signal.side,
                        size=size,
                        order_type="market",
                        price=last.close,
                        client_order_id=f"bt-open-{i}",
                    )
                )
                self.portfolio.on_fill_open(fill, signal.stop_price, signal.take_profit)
            elif self.portfolio.state.position is not None:
                close_side = "sell" if self.portfolio.state.position.side == "buy" else "buy"
                fill = self.executor.place(
                    OrderRequest(
                        symbol=self.portfolio.symbol,
                        side=close_side,
                        size=self.portfolio.state.position.size,
                        order_type="market",
                        price=last.close,
                        reduce_only=True,
                        client_order_id=f"bt-close-{i}",
                    )
                )
                self.portfolio.on_fill_close(fill, signal.reason)

            equity_curve.append(self.portfolio.state.equity)

        return self._metrics(equity_curve, hold_bars, total_bars)

    def _metrics(self, equity_curve: list[float], hold_bars: int, total_bars: int) -> BacktestResult:
        trades = self.portfolio.state.trades
        pnls = [t.pnl for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        ret = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            if prev > 0:
                ret.append((equity_curve[i] - prev) / prev)
        sharpe = 0.0 if len(ret) < 2 else (mean(ret) / (max(1e-9, (sum((r - mean(ret)) ** 2 for r in ret) / len(ret)) ** 0.5))) * sqrt(252 * 24 * 60)

        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            peak = max(peak, v)
            if peak > 0:
                max_dd = min(max_dd, (v - peak) / peak)

        win_rate = (len(wins) / len(trades)) if trades else 0.0
        profit_factor = (sum(wins) / sum(losses)) if losses else float("inf") if wins else 0.0
        expectancy = mean(pnls) if pnls else 0.0
        avg_hold = mean([t.hold_minutes for t in trades]) if trades else 0.0
        exposure = (hold_bars / total_bars) if total_bars else 0.0
        return BacktestResult(
            trades=len(trades),
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe=sharpe,
            max_drawdown=max_dd,
            expectancy=expectancy,
            avg_hold_minutes=avg_hold,
            exposure_time=exposure,
            final_equity=equity_curve[-1],
        )


def walk_forward_split(candles: list[Candle], train_ratio: float = 0.7) -> tuple[list[Candle], list[Candle]]:
    cut = max(1, int(len(candles) * train_ratio))
    return candles[:cut], candles[cut:]
