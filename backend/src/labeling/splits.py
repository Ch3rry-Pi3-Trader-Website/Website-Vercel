from __future__ import annotations

from typing import Iterator, Tuple

import pandas as pd


def rolling_windows(
    df: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step: int,
) -> Iterator[Tuple[pd.Index, pd.Index]]:
    n = len(df)
    start = 0
    while start + train_bars + test_bars <= n:
        train_idx = df.index[start : start + train_bars]
        test_idx = df.index[start + train_bars : start + train_bars + test_bars]
        yield train_idx, test_idx
        start += step
