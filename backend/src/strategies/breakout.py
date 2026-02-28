from __future__ import annotations

import pandas as pd


class Breakout:
    name = "breakout"

    def __init__(self, window: int = 20):
        self.window = window

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        w = self.window
        features["hh"] = features["high"].rolling(w, min_periods=w).max()
        features["ll"] = features["low"].rolling(w, min_periods=w).min()

    def signal(self, features: pd.DataFrame) -> pd.Series:
        sig = pd.Series(0, index=features.index, dtype=int)
        sig = sig.mask(features["close"] > features["hh"].shift(1), 1)
        sig = sig.mask(features["close"] < features["ll"].shift(1), -1)
        return sig.fillna(0).astype(int)
