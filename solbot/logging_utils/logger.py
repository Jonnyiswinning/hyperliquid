from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "context"):
            payload["context"] = getattr(record, "context")
        return json.dumps(payload)


def build_logger(name: str, log_path: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    fh = logging.FileHandler(log_path)
    fh.setFormatter(JsonFormatter())
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(JsonFormatter())
    logger.addHandler(sh)
    return logger


def log_with_context(logger: logging.Logger, level: int, msg: str, **context: Any) -> None:
    logger.log(level, msg, extra={"context": context})
