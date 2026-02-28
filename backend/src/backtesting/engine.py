from __future__ import annotations

import pandas as pd

from src.execution.risk import apply_daily_loss_cap, apply_flip_cooldown, apply_max_position


def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    interval_min: int,
    taker_bps: int = 4,
    max_position: float = 1.0,
    flip_cooldown_bars: int = 0,
    daily_loss_cap: float = 0.0,
) -> dict:
    data = df.copy().sort_values("timestamp").reset_index(drop=True)
    data["ret"] = data["close"].pct_change().fillna(0.0)
    timestamps = pd.to_datetime(data["timestamp"], utc=True)

    sig = signal.copy().astype(float).fillna(0.0)
    sig.index = data.index
    sig = apply_flip_cooldown(sig, flip_cooldown_bars)
    sig = apply_max_position(sig, max_position)

    pos = sig.shift(1).fillna(0.0)
    turns = (pos.diff().abs().fillna(0.0) > 0).astype(int)
    tc = (taker_bps / 1e4) * turns

    strat_ret = (pos * data["ret"]) - tc
    strat_ret.index = timestamps
    strat_ret = apply_daily_loss_cap(strat_ret, daily_loss_cap)
    equity = (1.0 + strat_ret).cumprod()

    pos.index = timestamps
    return {
        "returns": strat_ret.rename("returns"),
        "equity": equity.rename("equity"),
        "positions": pos.rename("position"),
        "interval_min": interval_min,
    }
