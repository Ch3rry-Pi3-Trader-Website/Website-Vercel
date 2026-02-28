from __future__ import annotations

import pandas as pd


def add_realized_vol(df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    out = df.copy()
    ret = out["close"].pct_change()
    out[f"rv_{window}"] = ret.rolling(window=window, min_periods=window).std()
    return out
