from __future__ import annotations

import pandas as pd


def add_ema_features(df: pd.DataFrame, windows: list[int]) -> pd.DataFrame:
    out = df.copy()
    for w in windows:
        out[f"ema_{w}"] = out["close"].ewm(span=w, adjust=False, min_periods=w).mean()
    return out


def add_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    out = df.copy()
    delta = out["close"].diff()
    gain = delta.clip(lower=0).rolling(window=window, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).rolling(window=window, min_periods=window).mean()
    rs = gain / loss.replace(0, pd.NA)
    out[f"rsi_{window}"] = 100 - (100 / (1 + rs))
    return out
