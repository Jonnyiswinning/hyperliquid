from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from solbot.types import BotState


class StateStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> BotState:
        if not self.path.exists():
            return BotState()
        with self.path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        state = BotState(
            daily_loss=raw.get("daily_loss", 0.0),
            consecutive_losses=raw.get("consecutive_losses", 0),
            api_failures=raw.get("api_failures", 0),
            open_order_ids=set(raw.get("open_order_ids", [])),
        )
        if raw.get("last_signal_ts"):
            state.last_signal_ts = datetime.fromisoformat(raw["last_signal_ts"])
        if raw.get("locked_until"):
            state.locked_until = datetime.fromisoformat(raw["locked_until"])
        return state

    def save(self, state: BotState) -> None:
        payload = asdict(state)
        payload["open_order_ids"] = sorted(payload["open_order_ids"])
        if state.last_signal_ts:
            payload["last_signal_ts"] = state.last_signal_ts.isoformat()
        if state.locked_until:
            payload["locked_until"] = state.locked_until.isoformat()
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
