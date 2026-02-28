from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from src.selection.scorer import SelectionPolicy, load_metrics_from_dir, score_metric_row


def load_policy(path: Path) -> SelectionPolicy:
    with path.open("r", encoding="utf-8") as f:
        y = yaml.safe_load(f) or {}
    w = y.get("metric_weights", {})
    return SelectionPolicy(
        weights=w,
        half_life_days=float(y.get("decay_half_life_days", 14)),
        min_bars=int(y.get("min_bars", 200)),
    )


def select_best_strategy(
    signals_root: Path,
    policy_file: Path,
    symbol: str,
    interval: str,
) -> Optional[Dict[str, Any]]:
    policy = load_policy(policy_file)
    now = dt.datetime.utcnow()
    best: Tuple[float, Dict[str, Any]] | None = None

    if not signals_root.exists():
        return None

    for strategy_dir in signals_root.iterdir():
        candidate_dir = strategy_dir / symbol / interval
        for dt_part in candidate_dir.glob("dt=*"):
            metrics = load_metrics_from_dir(dt_part)
            for row in metrics:
                score = score_metric_row(row, policy, now)
                if best is None or score > best[0]:
                    best = (score, row)

    if best is None:
        return None
    return best[1] | {"_score": best[0]}
