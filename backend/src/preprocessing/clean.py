from __future__ import annotations

import pandas as pd


def clean_candles(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    cols = ["timestamp", "open", "high", "low", "close", "adj_close", "volume", "symbol", "interval"]
    keep = [c for c in cols if c in df.columns]
    out = df[keep].copy()

    for col in ["open", "high", "low", "close", "adj_close", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.dropna(subset=["timestamp", "open", "high", "low", "close"])
    out = out.drop_duplicates(subset=["timestamp"], keep="last")
    out = out.sort_values("timestamp").reset_index(drop=True)
    return out
