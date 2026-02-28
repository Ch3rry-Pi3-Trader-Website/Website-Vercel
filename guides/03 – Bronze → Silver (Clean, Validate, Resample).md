# 03 – Bronze → Silver (Clean, Validate, Resample)

This step adds a runnable **preprocess** stage that reads the latest Bronze partition, performs minimal cleaning/validation, optionally resamples (e.g., 5-minute bars), and writes partitioned Parquet to **Silver** — all driven by your YAML config.

**What you’ll get**

* Consistent IO helpers for partitions and Parquet.
* Clean, typed candle frames with lightweight validation.
* Optional resampling via a single CLI flag.
* Feature pipeline placeholder (no-op for now) wired for later.



## 0) Dependencies

```bash
pip install pandas pyarrow pyyaml pydantic
```



## 1) Core IO Helpers

### `src/core/io.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def list_partitions(base: Path, pair: str, interval: int) -> List[Path]:
    """
    Return all dt partitions under base/pair/interval/, e.g.:
      data/bronze/ohlc/XXBTZUSD/1/dt=2025-08-13
    """
    root = base / pair / str(interval)
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("dt=")])


def latest_partition(base: Path, pair: str, interval: int) -> Optional[Path]:
    parts = list_partitions(base, pair, interval)
    return parts[-1] if parts else None


def read_parquet_many(paths: Iterable[Path]) -> pd.DataFrame:
    files = [p for p in paths if p.is_file() and p.suffix == ".parquet"]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)


def write_parquet_partition(
    df: pd.DataFrame,
    out_base: Path,
    pair: str,
    interval: int,
    dt_str: str,
    prefix: str = "part",
) -> Path:
    """
    Write df to out_base/pair/interval/dt=YYYY-MM-DD/{prefix}-<n>.parquet
    """
    out_dir = out_base / pair / str(interval) / f"dt={dt_str}"
    ensure_dir(out_dir)
    # simple rolling file name
    existing = list(out_dir.glob(f"{prefix}-*.parquet"))
    out_path = out_dir / f"{prefix}-{len(existing)+1}.parquet"
    df.to_parquet(out_path, index=False)
    return out_path
```



## 2) Preprocessing Stubs (clean → validate → resample)

### `src/preprocessing/clean.py`

```python
from __future__ import annotations
import pandas as pd


def clean_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal cleaning:
      - enforce dtypes
      - drop exact duplicates
      - sort by timestamp
      - keep only expected columns
    """
    if df.empty:
        return df.copy()

    cols = ["timestamp", "open", "high", "low", "close", "vwap", "volume", "count", "pair", "interval_min"]
    keep = [c for c in cols if c in df.columns]
    out = df[keep].copy()

    # types
    for col in ["open", "high", "low", "close", "vwap", "volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "count" in out.columns:
        out["count"] = pd.to_numeric(out["count"], errors="coerce").astype("Int64")
    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")

    # tidy
    out = out.drop_duplicates().sort_values("timestamp").reset_index(drop=True)
    return out
```

### `src/preprocessing/validate.py`

```python
from __future__ import annotations
import pandas as pd


def validate_candles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Lightweight validation stub. Raise if critical columns are missing or empty.
    Replace with pandera/Great Expectations later if you like.
    """
    required = ["timestamp", "open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if df.empty:
        return df
    if df["timestamp"].isna().any():
        raise ValueError("Found NaT in timestamp")
    return df
```

### `src/preprocessing/resample.py`

```python
from __future__ import annotations
import pandas as pd


def resample_candles(df: pd.DataFrame, rule: str | None = None) -> pd.DataFrame:
    """
    Resample to a new frequency if rule is provided (e.g., '5T', '1H').
    If rule is None, return as-is.
    """
    if df.empty or rule is None:
        return df.copy()

    g = (
        df.set_index("timestamp")
          .sort_index()
          .resample(rule)
    )
    out = g.agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "vwap": "mean",
        "volume": "sum",
        "count": "sum",
        "pair": "last",
        "interval_min": "last",
    }).dropna(subset=["open", "high", "low", "close"]).reset_index()
    return out
```



## 3) Features Pipeline Placeholder

### `src/features/pipeline.py`

```python
from __future__ import annotations
from pathlib import Path

import pandas as pd


def run_feature_pipeline(df: pd.DataFrame, pipeline_cfg_path: Path) -> pd.DataFrame:
    """
    Placeholder: return df unchanged for now.
    Later we'll apply technicals/volatility/etc based on the YAML pipeline.
    """
    return df.copy()
```

### `config/features/pipeline.yaml`

```yaml
# Placeholder pipeline config
steps:
  - name: identity
    kind: noop
```



## 4) Preprocess CLI (Bronze → Silver)

### `app/preprocess_cli.py`

```python
"""CLI: Bronze -> Silver (clean, optional resample, optional features)"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many, write_parquet_partition
from src.preprocessing.clean import clean_candles
from src.preprocessing.validate import validate_candles
from src.preprocessing.resample import resample_candles
from src.features.pipeline import run_feature_pipeline


@click.command()
@click.option("--env", "env_name", default=None, help="Config environment (dev/prod). Defaults to $APP_ENV or dev.")
@click.option("--pair", default=None, help="Override pair (e.g., XXBTZUSD).")
@click.option("--interval", type=int, default=None, help="Override source interval in minutes.")
@click.option("--resample", default=None, help="Optional pandas offset alias to resample to (e.g., '5T', '1H').")
def main(env_name: Optional[str], pair: Optional[str], interval: Optional[int], resample: Optional[str]):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min

    bronze_ohlc = resolve_path(root, f"{cfg.data.bronze_dir}/ohlc")
    silver_candles = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    features_cfg = resolve_path(root, cfg.features.pipeline_config)

    # 1) Find latest Bronze partition
    part = latest_partition(bronze_ohlc, pair, interval)
    if part is None:
        click.echo(f"[PREPROCESS] No Bronze partition found at {bronze_ohlc}/{pair}/{interval}")
        return

    files = list(part.glob("*.parquet"))
    if not files:
        click.echo(f"[PREPROCESS] No Parquet files in {part}")
        return

    click.echo(f"[PREPROCESS] Reading {len(files)} files from {part}")

    # 2) Read and clean
    df = read_parquet_many(files)
    df = clean_candles(df)
    df = validate_candles(df)

    # 3) Optional resample
    if resample:
        df = resample_candles(df, rule=resample)

    # 4) (Optional) run features pipeline (currently a no-op)
    df = run_feature_pipeline(df, pipeline_cfg_path=features_cfg)

    if df.empty:
        click.echo("[PREPROCESS] Result is empty after cleaning/resample.")
        return

    # Partition by latest timestamp date (UTC)
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_path = write_parquet_partition(
        df=df,
        out_base=silver_candles,
        pair=pair,
        interval=interval if not resample else int(pd.Timedelta(resample).total_seconds() // 60),
        dt_str=dt_str,
        prefix="candles",
    )
    click.echo(f"[PREPROCESS] Wrote Silver candles → {out_path}")


if __name__ == "__main__":
    main()
```



## 5) How to Run

From repo root:

```bash
# Use config defaults (dev): pair=XXBTZUSD, interval=1
python -m app.preprocess_cli

# Explicit env
python -m app.preprocess_cli --env dev

# Override and resample to 5-minute candles
python -m app.preprocess_cli --interval 1 --resample 5T

# Switch to prod config (works with public data too)
APP_ENV=prod python -m app.preprocess_cli
```

**Expected:**

* Reads latest Bronze partition under
  `data/bronze/ohlc/XXBTZUSD/1/dt=YYYY-MM-DD/`
* Writes Silver candles to
  `data/silver/candles/XXBTZUSD/<interval>/dt=YYYY-MM-DD/candles-<n>.parquet`
* If `--resample 5T`, the interval folder becomes `.../5/` (5 minutes)

