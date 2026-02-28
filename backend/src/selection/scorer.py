from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class SelectionPolicy:
    weights: Dict[str, float]
    half_life_days: float
    min_bars: int


def exp_decay_weight(age_days: float, half_life_days: float) -> float:
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age_days / half_life_days)


def load_metrics_from_dir(dir_path: Path) -> List[Dict[str, Any]]:
    if not dir_path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for p in dir_path.glob("metrics-*.json"):
        try:
            with p.open("r", encoding="utf-8") as f:
                out.append(json.load(f) | {"_path": str(p)})
        except Exception:
            continue
    return out


def score_metric_row(row: Dict[str, Any], policy: SelectionPolicy, now: dt.datetime) -> float:
    try:
        ts = Path(row["_path"]).stem.split("metrics-")[1].rstrip("Z")
        ts_parsed = dt.datetime.strptime(ts, "%Y%m%dT%H%M%S%f")
    except Exception:
        ts_parsed = now
    age_days = (now - ts_parsed).total_seconds() / 86400.0
    decay = exp_decay_weight(age_days, policy.half_life_days)

    if int(row.get("bars", 0)) < policy.min_bars:
        return float("-inf")

    sharpe = float(row.get("sharpe", 0.0))
    cagr = float(row.get("cagr", 0.0))
    mdd = float(row.get("max_drawdown", 0.0))

    w = policy.weights
    composite = (
        w.get("sharpe", 0.0) * sharpe
        + w.get("cagr", 0.0) * cagr
        + w.get("max_drawdown", 0.0) * (-mdd)
    )
    return decay * composite
