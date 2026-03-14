# Hyperliquid SOL Intraday Volatility Bot (Python)

Production-focused, conservative, intraday trading bot for **SOL perpetual market on Hyperliquid**.

## Strategy choice (SOL-specific)
Primary strategy: **Volatility expansion after compression breakout**.

Why this is appropriate for SOL intraday:
- SOL frequently transitions from low realized volatility compression to impulsive expansion intraday.
- Breakout + ATR expansion captures directional volatility bursts while avoiding constant mean-reversion churn.
- Liquidity/spread gates are critical on perps and are built-in.
- Strict lockouts and per-trade risk caps prioritize survival over overtrading.

Secondary confirmation filter:
- **EMA trend filter**: long only above EMA, short only below EMA.

Implemented controls:
- Volatility regime filter (min/max realized vol).
- Compression-to-expansion gate using short ATR vs baseline ATR.
- Volume confirmation multiplier.
- Spread and top-of-book depth filter.
- Chop filter (`net move / summed range`) to avoid noisy conditions.
- ATR stop, ATR take-profit, ATR trailing stop.
- Time stop and post-exit cooldown.

---

## Project tree

```text
hyperliquid/
├── .env.example
├── config.toml
├── data/
│   └── sol_1m_sample.csv
├── logs/
├── pyproject.toml
├── README.md
├── scripts/
│   └── run_backtest.py
├── solbot/
│   ├── __init__.py
│   ├── backtest/engine.py
│   ├── config/settings.py
│   ├── connectors/hyperliquid.py
│   ├── execution/executor.py
│   ├── logging_utils/journal.py
│   ├── logging_utils/logger.py
│   ├── market_data/service.py
│   ├── portfolio/account.py
│   ├── risk/manager.py
│   ├── runners/core.py
│   ├── runners/live.py
│   ├── runners/paper.py
│   ├── strategy/vol_breakout.py
│   ├── types.py
│   └── utils/
│       ├── alerts.py
│       ├── indicators.py
│       └── state_store.py
├── state/
└── tests/
    ├── test_backtest.py
    └── test_strategy_and_risk.py
```

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
```

Load env vars with your preferred method (`direnv`, shell export, etc).

## Run in paper mode (default)

```bash
python -m solbot.runners.paper
```

## Run in live mode

1. Set `runtime.paper_mode: false` in `config.toml`.
2. Set `WALLET_ADDRESS` and `PRIVATE_KEY`.
3. Run:

```bash
python -m solbot.runners.live
```

> Live order endpoints on Hyperliquid require signed `/exchange` payloads. This project keeps the adapter boundary (`HyperliquidClient.place_order`) explicit so a hardened signer implementation can be swapped in without changing strategy/risk code.

## Backtest

```bash
python scripts/run_backtest.py
```

Includes walk-forward split (`train_ratio`) with train/test output.

## First parameters to tune

1. `strategy.atr_expansion_mult`
2. `strategy.volume_confirm_mult`
3. `strategy.breakout_lookback`
4. `strategy.stop_atr_mult` + `take_profit_atr_mult`
5. `risk.per_trade_risk_pct`
6. `risk.daily_loss_limit_pct`
7. `risk.extreme_vol_lockout`
8. `strategy.max_spread_bps`

## Risk framework included

- Per-trade risk percent sizing.
- Daily drawdown lockout.
- Max consecutive losses lockout.
- Max simultaneous positions.
- Max gross exposure and leverage cap.
- API failure kill switch.
- Stale data rejection.
- Duplicate order prevention.
- Slippage circuit breaker.
- Optional end-of-day flatten.
- Extreme volatility hard lockout.

## Observability

- JSON structured logs (`logs/bot.log`).
- CSV trade journal (`logs/trades.csv`).
- Telegram alerts for fills, stop events, lockouts, and errors.

## Security / operations

- Secrets only via env interpolation in config (`${ENV_KEY}`).
- Startup checks prevent accidental live mode with missing key.
- Restart-safe persisted state in `state/runner_state.json`.
- Idempotent duplicate `client_order_id` protections in executors.

## Known limitations

- Live signing for Hyperliquid `/exchange` is intentionally isolated and must be implemented with your org’s key management/signing policy.
- No websocket path in v1 (REST polling only). Good for robustness, but not ideal for very fast micro-breakouts.
- Partial fill modeling in backtests is approximated via slippage/fees, not L2 replay.

## Roadmap

1. Add websocket market stream + order/fill stream reconciliation.
2. Implement full Hyperliquid signed order flow with robust nonce handling and key vault integration.
3. Add adaptive session schedules by volatility regime.
4. Add advanced execution (maker-first then taker failover) for lower fee footprint.
5. Add portfolio-level regime dashboard and Prometheus metrics.
