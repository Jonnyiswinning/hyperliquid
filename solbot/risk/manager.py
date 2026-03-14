from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from solbot.types import BotState, Position, RiskDecision, Signal


@dataclass
class RiskConfig:
    per_trade_risk_pct: float
    daily_loss_limit_pct: float
    max_consecutive_losses: int
    max_positions: int
    max_gross_exposure_usd: float
    max_leverage: float
    max_slippage_bps: float
    api_failure_kill_switch: int
    stale_data_seconds: int
    extreme_vol_lockout: float
    lockout_minutes: int


class RiskManager:
    def __init__(self, cfg: RiskConfig) -> None:
        self.cfg = cfg

    def evaluate_pre_trade(
        self,
        signal: Signal,
        equity: float,
        state: BotState,
        snapshot_age_seconds: float,
        open_positions: list[Position],
        gross_exposure: float,
        realized_volatility: float,
    ) -> RiskDecision:
        if state.locked_until and datetime.now(timezone.utc) < state.locked_until:
            return RiskDecision(False, "risk_lockout_active")
        if snapshot_age_seconds > self.cfg.stale_data_seconds:
            return RiskDecision(False, "stale_data")
        if realized_volatility > self.cfg.extreme_vol_lockout:
            state.locked_until = datetime.now(timezone.utc) + timedelta(minutes=self.cfg.lockout_minutes)
            return RiskDecision(False, "extreme_volatility_lockout")
        if len(open_positions) >= self.cfg.max_positions:
            return RiskDecision(False, "max_positions")
        if gross_exposure >= self.cfg.max_gross_exposure_usd:
            return RiskDecision(False, "max_gross_exposure")
        if state.consecutive_losses >= self.cfg.max_consecutive_losses:
            return RiskDecision(False, "max_consecutive_losses")
        if state.daily_loss <= -abs(equity * self.cfg.daily_loss_limit_pct):
            return RiskDecision(False, "daily_loss_limit")
        if state.api_failures >= self.cfg.api_failure_kill_switch:
            return RiskDecision(False, "api_failure_kill_switch")
        return RiskDecision(True)

    def compute_position_size(self, equity: float, entry_price: float, stop_price: float) -> float:
        risk_cap_usd = equity * self.cfg.per_trade_risk_pct
        distance = abs(entry_price - stop_price)
        if distance <= 0:
            return 0.0
        raw_size = risk_cap_usd / distance
        max_notional = equity * self.cfg.max_leverage
        return max(0.0, min(raw_size, max_notional / entry_price))

    def check_slippage(self, expected: float, actual: float) -> RiskDecision:
        if expected <= 0:
            return RiskDecision(False, "invalid_expected_price")
        slippage_bps = abs(actual - expected) / expected * 10000
        if slippage_bps > self.cfg.max_slippage_bps:
            return RiskDecision(False, "slippage_circuit_breaker")
        return RiskDecision(True)
