from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import time

import json
from urllib.request import Request, urlopen

from solbot.types import Candle, Fill, OrderRequest


@dataclass
class HyperliquidClient:
    base_url: str
    timeout_s: float = 5.0
    wallet_address: str = ""
    private_key: str = ""

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        req = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    def metadata(self) -> dict[str, Any]:
        return self._post("/info", {"type": "meta"})

    def l2_book(self, coin: str) -> dict[str, Any]:
        return self._post("/info", {"type": "l2Book", "coin": coin})

    def candles(self, coin: str, interval: str, start_ms: int, end_ms: int) -> list[Candle]:
        data = self._post(
            "/info",
            {"type": "candleSnapshot", "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms}},
        )
        candles = []
        for row in data:
            candles.append(
                Candle(
                    ts=datetime.fromtimestamp(row["t"] / 1000, tz=timezone.utc),
                    open=float(row["o"]),
                    high=float(row["h"]),
                    low=float(row["l"]),
                    close=float(row["c"]),
                    volume=float(row["v"]),
                )
            )
        return candles

    def account_state(self, user: str) -> dict[str, Any]:
        return self._post("/info", {"type": "clearinghouseState", "user": user})

    def user_fills(self, user: str) -> list[Fill]:
        rows = self._post("/info", {"type": "userFills", "user": user})
        fills: list[Fill] = []
        for row in rows:
            fills.append(
                Fill(
                    order_id=str(row.get("oid", "")),
                    symbol=row["coin"],
                    side="buy" if row.get("side", "B") in ["B", "buy"] else "sell",
                    size=float(row["sz"]),
                    price=float(row["px"]),
                    fee=float(row.get("fee", 0.0)),
                    ts=datetime.fromtimestamp(row["time"] / 1000, tz=timezone.utc),
                )
            )
        return fills

    def place_order(self, req: OrderRequest) -> dict[str, Any]:
        if not self.private_key:
            raise RuntimeError("Live order signing not configured. Provide PRIVATE_KEY for live mode.")
        # Hyperliquid order placement requires signed payload via /exchange endpoint.
        # This adapter keeps interface stable; signing is delegated to future hardened signer integration.
        raise NotImplementedError("Signed /exchange order flow is environment-specific and must be supplied for live mode.")

    def cancel(self, order_id: str, coin: str) -> dict[str, Any]:
        if not self.private_key:
            raise RuntimeError("Live cancel signing not configured.")
        raise NotImplementedError("Signed cancel flow is environment-specific and must be supplied for live mode.")


def _parse_book_level(level: Any) -> tuple[float, float] | None:
    """Accepts Hyperliquid level entries in list or dict form and returns (price, size)."""
    if isinstance(level, (list, tuple)) and len(level) >= 2:
        try:
            return float(level[0]), float(level[1])
        except (TypeError, ValueError):
            return None

    if isinstance(level, dict):
        price_raw = level.get("px")
        size_raw = level.get("sz")
        if price_raw is None or size_raw is None:
            return None
        try:
            return float(price_raw), float(size_raw)
        except (TypeError, ValueError):
            return None

    return None


class MarketDataAdapter:
    def __init__(self, client: HyperliquidClient, symbol: str, interval: str) -> None:
        self.client = client
        self.symbol = symbol
        self.interval = interval

    def recent_candles(self, lookback: int = 200) -> list[Candle]:
        now_ms = int(time.time() * 1000)
        duration = 60_000 * lookback
        return self.client.candles(self.symbol, self.interval, now_ms - duration, now_ms)

    def spread_bps(self) -> float:
        book = self.client.l2_book(self.symbol)
        bids = book.get("levels", [[], []])[0]
        asks = book.get("levels", [[], []])[1]
        if not bids or not asks:
            return 99999.0

        bid = _parse_book_level(bids[0])
        ask = _parse_book_level(asks[0])
        if bid is None or ask is None:
            return 99999.0

        best_bid, _ = bid
        best_ask, _ = ask
        mid = (best_bid + best_ask) / 2
        if mid <= 0:
            return 99999.0
        return ((best_ask - best_bid) / mid) * 10000

    def top_depth(self) -> float:
        book = self.client.l2_book(self.symbol)
        bids = book.get("levels", [[], []])[0]
        asks = book.get("levels", [[], []])[1]

        bid = _parse_book_level(bids[0]) if bids else None
        ask = _parse_book_level(asks[0]) if asks else None
        if bid is None or ask is None:
            return 0.0

        _, bid_size = bid
        _, ask_size = ask
        return min(bid_size, ask_size)
