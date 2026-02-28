from __future__ import annotations

import pandas as pd


def validate_candles(df: pd.DataFrame) -> pd.DataFrame:
    required = ["timestamp", "open", "high", "low", "close", "symbol", "interval"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if df.empty:
        return df

    if df["timestamp"].isna().any():
        raise ValueError("Invalid timestamps found.")
    if (df[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Non-positive OHLC prices found.")
    return df
