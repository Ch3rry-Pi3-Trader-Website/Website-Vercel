from __future__ import annotations

import pandas as pd


class Momentum:
    name = "momentum"

    def __init__(self, fast: int = 20, slow: int = 50):
        if fast >= slow:
            raise ValueError("fast EMA must be < slow EMA")
        self.fast = fast
        self.slow = slow

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        f, s = self.fast, self.slow
        features[f"ema_{f}"] = features["close"].ewm(span=f, adjust=False, min_periods=f).mean()
        features[f"ema_{s}"] = features["close"].ewm(span=s, adjust=False, min_periods=s).mean()
        features["spread"] = features[f"ema_{f}"] - features[f"ema_{s}"]

    def signal(self, features: pd.DataFrame) -> pd.Series:
        sig = features["spread"].copy()
        sig = sig.where(sig.notna(), 0.0)
        sig = sig.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        return sig.astype(int)
