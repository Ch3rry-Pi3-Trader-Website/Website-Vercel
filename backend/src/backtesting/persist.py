from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_metrics_json(metrics: Dict[str, Any], out_dir: Path, filename: str = "metrics.json") -> Path:
    ensure_dir(out_dir)
    path = out_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    return path


def write_timeseries_csv(series: pd.Series, out_dir: Path, filename: str) -> Path:
    ensure_dir(out_dir)
    path = out_dir / filename
    series.to_frame(name=series.name or "value").to_csv(path, index=True)
    return path


def timestamp_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
