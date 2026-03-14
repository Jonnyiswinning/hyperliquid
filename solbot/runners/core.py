from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from solbot.execution.executor import Executor
from solbot.logging_utils.journal import TradeJournal
from solbot.logging_utils.logger import log_with_context
from solbot.market_data.service import MarketDataService
from solbot.portfolio.account import PortfolioManager
from solbot.risk.manager import RiskManager
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy
from solbot.types import BotState, OrderRequest
from solbot.utils.alerts import AlertClient
from solbot.utils.indicators import realized_vol
from solbot.utils.state_store import StateStore


class BotRunner:
    def __init__(
        self,
        market: MarketDataService,
        strategy: SolVolatilityBreakoutStrategy,
        risk: RiskManager,
        portfolio: PortfolioManager,
        executor: Executor,
        journal: TradeJournal,
        state_store: StateStore,
        alerts: AlertClient,
        logger: logging.Logger,
        poll_seconds: int,
        flatten_hour_utc: int,
        no_overnight: bool,
    ) -> None:
        self.market = market
        self.strategy = strategy
        self.risk = risk
        self.portfolio = portfolio
        self.executor = executor
        self.journal = journal
        self.state_store = state_store
        self.alerts = alerts
        self.logger = logger
        self.poll_seconds = poll_seconds
        self.flatten_hour_utc = flatten_hour_utc
        self.no_overnight = no_overnight
        self.state: BotState = state_store.load()

    def run_forever(self, lookback_bars: int) -> None:
        while True:
            self.iterate_once(lookback_bars)
            self.state_store.save(self.state)
            time.sleep(self.poll_seconds)

    def iterate_once(self, lookback_bars: int) -> None:
        snapshot = self.market.snapshot(lookback=lookback_bars)
        if not snapshot.candles:
            log_with_context(self.logger, logging.WARNING, "No candles received")
            return
        now = datetime.now(timezone.utc)
        last = snapshot.candles[-1]
        self.portfolio.mark_to_market(last.close)
        if self.no_overnight and now.hour >= self.flatten_hour_utc and self.portfolio.state.position:
            self._force_flatten(last.close, "session_flatten")
            return

        signal = self.strategy.on_bar_close(
            candles=snapshot.candles,
            spread_bps=snapshot.spread_bps,
            top_depth=snapshot.top_depth,
            position=self.portfolio.state.position,
            bars_in_position=self.portfolio.state.bars_in_position,
        )
        if signal is None:
            return

        rv = realized_vol(snapshot.candles, 20)
        decision = self.risk.evaluate_pre_trade(
            signal=signal,
            equity=self.portfolio.state.equity,
            state=self.state,
            snapshot_age_seconds=(now - last.ts).total_seconds(),
            open_positions=[self.portfolio.state.position] if self.portfolio.state.position else [],
            gross_exposure=self.portfolio.state.gross_exposure,
            realized_volatility=rv,
        )
        if not decision.allowed:
            log_with_context(self.logger, logging.INFO, "Risk rejected signal", reason=decision.reason)
            if "lockout" in decision.reason:
                self.alerts.send(f"Lockout engaged: {decision.reason}")
            return

        if self.portfolio.state.position is None and signal.reason.startswith("vol_breakout"):
            size = self.risk.compute_position_size(self.portfolio.state.equity, last.close, signal.stop_price)
            if size <= 0:
                return
            fill = self.executor.place(
                OrderRequest(
                    symbol=self.portfolio.symbol,
                    side=signal.side,
                    size=size,
                    order_type="market",
                    price=last.close,
                    client_order_id=f"open-{uuid.uuid4().hex[:12]}",
                )
            )
            self.portfolio.on_fill_open(fill, signal.stop_price, signal.take_profit)
            self.alerts.send(f"Opened {fill.side} {fill.size:.3f} {fill.symbol} @ {fill.price:.3f}")
            log_with_context(self.logger, logging.INFO, "Position opened", side=fill.side, size=fill.size, price=fill.price)
            return

        if self.portfolio.state.position is not None:
            close_side = "sell" if self.portfolio.state.position.side == "buy" else "buy"
            fill = self.executor.place(
                OrderRequest(
                    symbol=self.portfolio.symbol,
                    side=close_side,
                    size=self.portfolio.state.position.size,
                    order_type="market",
                    price=last.close,
                    reduce_only=True,
                    client_order_id=f"close-{uuid.uuid4().hex[:12]}",
                )
            )
            trade = self.portfolio.on_fill_close(fill, signal.reason)
            self.journal.append(trade)
            self.state.daily_loss += min(0.0, trade.pnl)
            if trade.pnl < 0:
                self.state.consecutive_losses += 1
            else:
                self.state.consecutive_losses = 0
            self.alerts.send(f"Closed {trade.side} pnl={trade.pnl:.2f} reason={trade.reason}")
            log_with_context(self.logger, logging.INFO, "Position closed", pnl=trade.pnl, reason=trade.reason)

    def _force_flatten(self, last_price: float, reason: str) -> None:
        if self.portfolio.state.position is None:
            return
        close_side = "sell" if self.portfolio.state.position.side == "buy" else "buy"
        fill = self.executor.place(
            OrderRequest(
                symbol=self.portfolio.symbol,
                side=close_side,
                size=self.portfolio.state.position.size,
                order_type="market",
                price=last_price,
                reduce_only=True,
                client_order_id=f"flatten-{uuid.uuid4().hex[:12]}",
            )
        )
        trade = self.portfolio.on_fill_close(fill, reason)
        self.journal.append(trade)
        self.alerts.send(f"Session flatten executed pnl={trade.pnl:.2f}")
