from __future__ import annotations

import csv
from pathlib import Path

from solbot.types import TradeRecord


class TradeJournal:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            with self.path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "symbol",
                        "side",
                        "entry_price",
                        "exit_price",
                        "size",
                        "pnl",
                        "fees",
                        "opened_at",
                        "closed_at",
                        "hold_minutes",
                        "reason",
                    ]
                )

    def append(self, trade: TradeRecord) -> None:
        with self.path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    trade.symbol,
                    trade.side,
                    trade.entry_price,
                    trade.exit_price,
                    trade.size,
                    trade.pnl,
                    trade.fees,
                    trade.opened_at.isoformat(),
                    trade.closed_at.isoformat(),
                    trade.hold_minutes,
                    trade.reason,
                ]
            )
