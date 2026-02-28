from __future__ import annotations

import pandas as pd


def add_forward_return_labels(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    out = df.copy()
    col = f"fwd_ret_{horizon}"
    out[col] = out["close"].shift(-horizon) / out["close"] - 1.0
    return out
