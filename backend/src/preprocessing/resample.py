from __future__ import annotations

import pandas as pd


def resample_candles(df: pd.DataFrame, rule: str | None = None) -> pd.DataFrame:
    if df.empty or rule is None:
        return df.copy()

    grouped = (
        df.set_index("timestamp")
        .sort_index()
        .resample(rule)
    )
    out = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "adj_close": "last",
            "volume": "sum",
            "symbol": "last",
            "interval": "last",
        }
    )
    out = out.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return out
