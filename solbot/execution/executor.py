from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
import time
import uuid

from solbot.connectors.hyperliquid import HyperliquidClient
from solbot.types import Fill, OrderRequest


class Executor(Protocol):
    def place(self, request: OrderRequest) -> Fill:
        ...


@dataclass
class PaperExecutor:
    fee_bps: float
    slippage_bps: float
    seen_client_order_ids: set[str]

    def place(self, request: OrderRequest) -> Fill:
        if request.client_order_id and request.client_order_id in self.seen_client_order_ids:
            raise RuntimeError("duplicate_order_prevented")
        if request.client_order_id:
            self.seen_client_order_ids.add(request.client_order_id)
        if request.price is None:
            raise RuntimeError("paper_executor_requires_reference_price")

        side_mult = 1 if request.side == "buy" else -1
        exec_price = request.price * (1 + (self.slippage_bps / 10000) * side_mult)
        fee = exec_price * request.size * (self.fee_bps / 10000)
        return Fill(
            order_id=f"paper-{uuid.uuid4().hex[:10]}",
            symbol=request.symbol,
            side=request.side,
            size=request.size,
            price=exec_price,
            fee=fee,
            ts=datetime.now(timezone.utc),
        )


class LiveExecutor:
    def __init__(self, client: HyperliquidClient, retries: int = 3, retry_delay_s: float = 0.35) -> None:
        self.client = client
        self.retries = retries
        self.retry_delay_s = retry_delay_s
        self.seen_client_order_ids: set[str] = set()

    def place(self, request: OrderRequest) -> Fill:
        if request.client_order_id and request.client_order_id in self.seen_client_order_ids:
            raise RuntimeError("duplicate_order_prevented")
        if request.client_order_id:
            self.seen_client_order_ids.add(request.client_order_id)

        last_err: Exception | None = None
        for _ in range(self.retries):
            try:
                result = self.client.place_order(request)
                status = result.get("status", "")
                if status and status not in {"ok", "filled", "resting"}:
                    raise RuntimeError(f"rejected_order_{status}")
                fill = result.get("fill") or {}
                price = float(fill.get("px", request.price or 0.0))
                size = float(fill.get("sz", request.size))
                fee = float(fill.get("fee", 0.0))
                oid = str(fill.get("oid", result.get("orderId", "")))
                return Fill(
                    order_id=oid,
                    symbol=request.symbol,
                    side=request.side,
                    size=size,
                    price=price,
                    fee=fee,
                    ts=datetime.now(timezone.utc),
                )
            except Exception as err:  # noqa: BLE001
                last_err = err
                time.sleep(self.retry_delay_s)
        raise RuntimeError(f"live_order_failed_after_retries: {last_err}")
