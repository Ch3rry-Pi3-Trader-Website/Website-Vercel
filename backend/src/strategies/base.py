from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    name: str

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        ...

    def signal(self, features: pd.DataFrame) -> pd.Series:
        ...
