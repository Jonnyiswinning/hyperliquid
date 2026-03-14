from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Signal:
    side: str
    confidence: float
    stop_price: float
    take_profit: float
    reason: str


@dataclass
class Position:
    side: str
    size: float
    entry_price: float
    stop_price: float
    take_profit: float
    opened_at: datetime
    trailing_stop: Optional[float] = None


@dataclass
class OrderRequest:
    symbol: str
    side: str
    size: float
    order_type: str
    price: Optional[float]
    reduce_only: bool = False
    client_order_id: str = ""


@dataclass
class Fill:
    order_id: str
    symbol: str
    side: str
    size: float
    price: float
    fee: float
    ts: datetime


@dataclass
class TradeRecord:
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    fees: float
    opened_at: datetime
    closed_at: datetime
    hold_minutes: float
    reason: str


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""


@dataclass
class BotState:
    last_signal_ts: Optional[datetime] = None
    daily_loss: float = 0.0
    consecutive_losses: int = 0
    locked_until: Optional[datetime] = None
    api_failures: int = 0
    open_order_ids: set[str] = field(default_factory=set)
