from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from solbot.connectors.hyperliquid import MarketDataAdapter
from solbot.types import Candle


@dataclass
class MarketSnapshot:
    candles: list[Candle]
    spread_bps: float
    top_depth: float
    ts: datetime


class MarketDataService:
    def __init__(self, adapter: MarketDataAdapter) -> None:
        self.adapter = adapter

    def snapshot(self, lookback: int) -> MarketSnapshot:
        candles = self.adapter.recent_candles(lookback=lookback)
        return MarketSnapshot(
            candles=candles,
            spread_bps=self.adapter.spread_bps(),
            top_depth=self.adapter.top_depth(),
            ts=datetime.now(timezone.utc),
        )
