from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def list_partitions(base: Path, symbol: str, interval: str) -> List[Path]:
    root = base / f"symbol={symbol}" / f"interval={interval}"
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("dt=")])


def latest_partition(base: Path, symbol: str, interval: str) -> Optional[Path]:
    parts = list_partitions(base, symbol, interval)
    return parts[-1] if parts else None


def read_parquet_many(paths: Iterable[Path]) -> pd.DataFrame:
    files = [p for p in paths if p.is_file() and p.suffix == ".parquet"]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def write_parquet_partition(
    df: pd.DataFrame,
    out_base: Path,
    symbol: str,
    interval: str,
    dt_str: str,
    prefix: str = "part",
) -> Path:
    out_dir = out_base / f"symbol={symbol}" / f"interval={interval}" / f"dt={dt_str}"
    ensure_dir(out_dir)

    existing = list(out_dir.glob(f"{prefix}-*.parquet"))
    out_path = out_dir / f"{prefix}-{len(existing) + 1}.parquet"
    df.to_parquet(out_path, index=False, compression="zstd")
    return out_path
