from __future__ import annotations

import pandas as pd


def add_dollar_volume(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "volume" in out.columns:
        out["dollar_volume"] = out["close"] * out["volume"]
    return out
