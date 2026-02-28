from __future__ import annotations

import pandas as pd


def equity_from_returns(returns: pd.Series, initial_equity: float = 1.0) -> pd.Series:
    return (initial_equity * (1.0 + returns).cumprod()).rename("equity")
