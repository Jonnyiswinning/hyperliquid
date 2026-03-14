from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from solbot.types import Fill, Position, TradeRecord


@dataclass
class AccountState:
    equity: float
    cash: float
    position: Position | None = None
    bars_in_position: int = 0
    gross_exposure: float = 0.0
    trades: list[TradeRecord] = field(default_factory=list)


class PortfolioManager:
    def __init__(self, starting_equity: float, symbol: str) -> None:
        self.symbol = symbol
        self.state = AccountState(equity=starting_equity, cash=starting_equity)

    def mark_to_market(self, price: float) -> None:
        pos = self.state.position
        if pos is None:
            return
        direction = 1 if pos.side == "buy" else -1
        unreal = direction * (price - pos.entry_price) * pos.size
        self.state.equity = self.state.cash + unreal
        self.state.gross_exposure = abs(price * pos.size)
        self.state.bars_in_position += 1

    def on_fill_open(self, fill: Fill, stop: float, tp: float) -> None:
        self.state.position = Position(
            side=fill.side,
            size=fill.size,
            entry_price=fill.price,
            stop_price=stop,
            take_profit=tp,
            opened_at=fill.ts,
        )
        self.state.cash -= fill.fee
        self.state.equity -= fill.fee
        self.state.bars_in_position = 0

    def on_fill_close(self, fill: Fill, reason: str) -> TradeRecord:
        pos = self.state.position
        if pos is None:
            raise RuntimeError("Attempted to close when no active position")
        direction = 1 if pos.side == "buy" else -1
        pnl = direction * (fill.price - pos.entry_price) * pos.size - fill.fee
        self.state.cash += pnl
        self.state.equity = self.state.cash
        trade = TradeRecord(
            symbol=self.symbol,
            side=pos.side,
            entry_price=pos.entry_price,
            exit_price=fill.price,
            size=pos.size,
            pnl=pnl,
            fees=fill.fee,
            opened_at=pos.opened_at,
            closed_at=fill.ts,
            hold_minutes=(fill.ts - pos.opened_at).total_seconds() / 60,
            reason=reason,
        )
        self.state.position = None
        self.state.bars_in_position = 0
        self.state.gross_exposure = 0.0
        self.state.trades.append(trade)
        return trade
