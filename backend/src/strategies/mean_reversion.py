from __future__ import annotations

import pandas as pd


class BollingerMeanReversion:
    name = "mean_reversion"

    def __init__(self, window: int = 20, k: float = 2.0):
        self.window = window
        self.k = k

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        w, k = self.window, self.k
        ma = features["close"].rolling(w, min_periods=w).mean()
        sd = features["close"].rolling(w, min_periods=w).std()
        features["bb_mid"] = ma
        features["bb_up"] = ma + k * sd
        features["bb_lo"] = ma - k * sd

    def signal(self, features: pd.DataFrame) -> pd.Series:
        close = features["close"]
        up = features["bb_up"]
        lo = features["bb_lo"]
        sig = pd.Series(0, index=features.index, dtype=int)
        sig = sig.mask(close < lo, 1)
        sig = sig.mask(close > up, -1)
        return sig.fillna(0).astype(int)
