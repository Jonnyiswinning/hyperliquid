from __future__ import annotations

from solbot.config.settings import load_config
from solbot.connectors.hyperliquid import HyperliquidClient, MarketDataAdapter
from solbot.execution.executor import PaperExecutor
from solbot.logging_utils.journal import TradeJournal
from solbot.logging_utils.logger import build_logger
from solbot.market_data.service import MarketDataService
from solbot.portfolio.account import PortfolioManager
from solbot.risk.manager import RiskConfig, RiskManager
from solbot.runners.core import BotRunner
from solbot.strategy.vol_breakout import SolVolatilityBreakoutStrategy, StrategyConfig
from solbot.utils.alerts import AlertClient
from solbot.utils.state_store import StateStore


def main(config_path: str = "config.toml") -> None:
    cfg = load_config(config_path).raw
    client = HyperliquidClient(base_url=cfg["hyperliquid"]["base_url"])
    market_adapter = MarketDataAdapter(client, cfg["market"]["symbol"], cfg["market"]["interval"])
    market = MarketDataService(market_adapter)

    strategy = SolVolatilityBreakoutStrategy(StrategyConfig(**cfg["strategy"]))
    risk = RiskManager(RiskConfig(**cfg["risk"]))
    portfolio = PortfolioManager(starting_equity=cfg["portfolio"]["starting_equity"], symbol=cfg["market"]["symbol"])

    executor = PaperExecutor(
        fee_bps=cfg["execution"]["fee_bps"],
        slippage_bps=cfg["execution"]["paper_slippage_bps"],
        seen_client_order_ids=set(),
    )
    journal = TradeJournal(cfg["logging"]["trade_journal_csv"])
    state_store = StateStore(cfg["runtime"]["state_path"])
    alerts = AlertClient(
        telegram_bot_token=cfg["alerts"].get("telegram_bot_token", ""),
        telegram_chat_id=cfg["alerts"].get("telegram_chat_id", ""),
    )
    logger = build_logger("solbot-paper", cfg["logging"]["json_log_path"])

    runner = BotRunner(
        market=market,
        strategy=strategy,
        risk=risk,
        portfolio=portfolio,
        executor=executor,
        journal=journal,
        state_store=state_store,
        alerts=alerts,
        logger=logger,
        poll_seconds=cfg["runtime"]["poll_seconds"],
        flatten_hour_utc=cfg["runtime"]["flatten_hour_utc"],
        no_overnight=cfg["runtime"]["no_overnight"],
    )
    runner.run_forever(lookback_bars=cfg["runtime"]["lookback_bars"])


if __name__ == "__main__":
    main()
