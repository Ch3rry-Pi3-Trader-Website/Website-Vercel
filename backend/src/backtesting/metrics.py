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


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = (equity / roll_max) - 1.0
    return float(dd.min())
