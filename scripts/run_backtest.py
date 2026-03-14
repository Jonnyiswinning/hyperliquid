from __future__ import annotations

import csv
from datetime import datetime, timezone
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solbot.backtest.engine import BacktestEngine, walk_forward_split
from solbot.config.settings import load_config
from solbot.portfolio.account import PortfolioManager
from solbot.risk.manager import RiskConfig, RiskManager
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy, StrategyConfig
from solbot.types import Candle


def load_candles_csv(path: str) -> list[Candle]:
    out: list[Candle] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(
                Candle(
                    ts=datetime.fromisoformat(row["ts"]).astimezone(timezone.utc),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
    return out


def main(config_path: str = "config.toml", candles_csv: str = "data/sol_1m_sample.csv") -> None:
    cfg = load_config(config_path).raw
    candles = load_candles_csv(candles_csv)
    train, test = walk_forward_split(candles, cfg["backtest"]["train_ratio"])

    strategy = SolVolatilityBreakoutStrategy(StrategyConfig(**cfg["strategy"]))
    risk = RiskManager(RiskConfig(**cfg["risk"]))

    train_engine = BacktestEngine(
        strategy=strategy,
        risk=risk,
        portfolio=PortfolioManager(cfg["portfolio"]["starting_equity"], cfg["market"]["symbol"]),
        fee_bps=cfg["execution"]["fee_bps"],
        slippage_bps=cfg["backtest"]["slippage_bps"],
    )
    train_result = train_engine.run(train)

    test_engine = BacktestEngine(
        strategy=SolVolatilityBreakoutStrategy(StrategyConfig(**cfg["strategy"])),
        risk=RiskManager(RiskConfig(**cfg["risk"])),
        portfolio=PortfolioManager(cfg["portfolio"]["starting_equity"], cfg["market"]["symbol"]),
        fee_bps=cfg["execution"]["fee_bps"],
        slippage_bps=cfg["backtest"]["slippage_bps"],
    )
    test_result = test_engine.run(test)

    print("=== Train ===")
    print(train_result)
    print("=== Test ===")
    print(test_result)


if __name__ == "__main__":
    main()
