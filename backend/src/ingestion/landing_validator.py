from __future__ import annotations

from pathlib import Path


def validate_partition(path: Path) -> bool:
    return path.exists() and any(path.glob("*.parquet"))
