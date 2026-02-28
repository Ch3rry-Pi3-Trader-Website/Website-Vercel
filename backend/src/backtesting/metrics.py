from __future__ import annotations

import numpy as np
import pandas as pd


def annualisation_factor(interval_min: int) -> float:
    return (365 * 24 * 60) / interval_min


def cagr(equity: pd.Series, interval_min: int) -> float:
    if equity.empty:
        return 0.0
    start, end = float(equity.iloc[0]), float(equity.iloc[-1])
    if start <= 0 or end <= 0:
        return 0.0
    years = len(equity) / annualisation_factor(interval_min)
    if years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1.0


def sharpe(returns: pd.Series, interval_min: int, risk_free: float = 0.0) -> float:
    if returns.empty:
        return 0.0
    ex = returns - (risk_free / annualisation_factor(interval_min))
    std = ex.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0
    return np.sqrt(annualisation_factor(interval_min)) * ex.mean() / std


def to_log_returns(returns: pd.Series) -> pd.Series:
    if returns.empty:
        return returns.copy()
    # Guard against invalid log for pathological <= -100% returns.
    clipped = returns.clip(lower=-0.999999999)
    return np.log1p(clipped)


def sharpe_log(log_returns: pd.Series, interval_min: int, risk_free: float = 0.0) -> float:
    if log_returns.empty:
        return 0.0
    ex = log_returns - (risk_free / annualisation_factor(interval_min))
    std = ex.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0
    return float(np.sqrt(annualisation_factor(interval_min)) * ex.mean() / std)


def sortino_log(log_returns: pd.Series, interval_min: int, target: float = 0.0) -> float:
    if log_returns.empty:
        return 0.0
    target_per_bar = target / annualisation_factor(interval_min)
    downside = log_returns[log_returns < target_per_bar] - target_per_bar
    dstd = downside.std(ddof=1)
    if dstd == 0 or pd.isna(dstd):
        return 0.0
    mean_excess = log_returns.mean() - target_per_bar
    return float(np.sqrt(annualisation_factor(interval_min)) * mean_excess / dstd)


def realized_vol_log(log_returns: pd.Series, interval_min: int) -> float:
    if log_returns.empty:
        return 0.0
    std = log_returns.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0
    return float(std * np.sqrt(annualisation_factor(interval_min)))


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = (equity / roll_max) - 1.0
    return float(dd.min())
