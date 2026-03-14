from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict
import os
import tomllib


@dataclass
class AppConfig:
    raw: Dict[str, Any]

    @property
    def symbol(self) -> str:
        return self.raw["market"]["symbol"]

    @property
    def paper_mode(self) -> bool:
        return bool(self.raw["runtime"]["paper_mode"])


def _interpolate_env_values(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _interpolate_env_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env_values(v) for v in value]
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        env_key = value[2:-1]
        return os.getenv(env_key, "")
    return value


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open("rb") as f:
        loaded = tomllib.load(f)
    resolved = _interpolate_env_values(loaded)
    return AppConfig(raw=resolved)
