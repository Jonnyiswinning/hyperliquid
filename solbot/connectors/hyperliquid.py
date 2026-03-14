from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
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
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        mid = (best_bid + best_ask) / 2
        if mid <= 0:
            return 99999.0
        return ((best_ask - best_bid) / mid) * 10000

    def top_depth(self) -> float:
        book = self.client.l2_book(self.symbol)
        bids = book.get("levels", [[], []])[0]
        asks = book.get("levels", [[], []])[1]
        bid_size = float(bids[0][1]) if bids else 0.0
        ask_size = float(asks[0][1]) if asks else 0.0
        return min(bid_size, ask_size)
