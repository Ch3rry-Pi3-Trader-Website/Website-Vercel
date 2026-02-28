from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from src.features.price_volume import add_dollar_volume
from src.features.technicals import add_ema_features, add_rsi
from src.features.volatility import add_realized_vol


def run_feature_pipeline(df: pd.DataFrame, pipeline_cfg_path: Path) -> pd.DataFrame:
    out = df.copy()
    if not pipeline_cfg_path.exists():
        return out

    with pipeline_cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    steps = cfg.get("steps", [])

    for step in steps:
        kind = step.get("kind", "noop")
        params = step.get("params", {}) or {}
        if kind == "technicals":
            windows = params.get("ema_windows", [20, 50])
            out = add_ema_features(out, windows=[int(x) for x in windows])
            out = add_rsi(out, window=int(params.get("rsi_window", 14)))
        elif kind == "volatility":
            out = add_realized_vol(out, window=int(params.get("vol_window", 20)))
        elif kind == "price_volume":
            out = add_dollar_volume(out)
    return out
