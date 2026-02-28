from __future__ import annotations

import pandas as pd

from src.execution.risk import apply_daily_loss_cap, apply_flip_cooldown, apply_max_position


class PaperBroker:
    def __init__(self, initial_equity: float = 1.0):
        self.equity = initial_equity

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        taker_bps: int = 4,
        max_position: float = 1.0,
        flip_cooldown_bars: int = 0,
        daily_loss_cap: float = 0.0,
    ) -> pd.Series:
        sig = apply_flip_cooldown(signals.fillna(0.0).astype(float), flip_cooldown_bars)
        sig = apply_max_position(sig, max_position)

        data = df.copy().sort_values("timestamp").reset_index(drop=True)
        ret = data["close"].pct_change().fillna(0.0)
        pos = sig.shift(1).fillna(0.0)
        turns = (pos.diff().abs().fillna(0.0) > 0).astype(int)
        tc = (taker_bps / 1e4) * turns

        strat_ret = (pos * ret) - tc
        strat_ret.index = pd.to_datetime(data["timestamp"], utc=True)
        strat_ret = apply_daily_loss_cap(strat_ret, daily_loss_cap)

        return (self.equity * (1.0 + strat_ret).cumprod()).rename("equity_paper")
