from __future__ import annotations

import json
from urllib.request import Request, urlopen


class AlertClient:
    def __init__(self, telegram_bot_token: str = "", telegram_chat_id: str = "") -> None:
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id

    def send(self, message: str) -> None:
        if not self.telegram_bot_token or not self.telegram_chat_id:
            return
        req = Request(
            f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
            data=json.dumps({"chat_id": self.telegram_chat_id, "text": message}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=5):  # noqa: S310
            pass
