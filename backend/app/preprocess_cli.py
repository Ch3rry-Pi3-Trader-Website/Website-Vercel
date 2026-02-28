"""CLI: Bronze -> Silver (clean, validate, optional resample/features)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many, write_parquet_partition
from src.features.pipeline import run_feature_pipeline
from src.preprocessing.clean import clean_candles
from src.preprocessing.resample import resample_candles
from src.preprocessing.validate import validate_candles


@click.command()
@click.option("--env", "env_name", default=None, help="Config environment (dev/prod).")
@click.option("--symbol", default=None, help="Symbol override.")
@click.option("--interval", default=None, help="Source interval override.")
@click.option("--resample", default=None, help="Optional pandas rule (for example: W, M).")
def main(env_name: Optional[str], symbol: Optional[str], interval: Optional[str], resample: Optional[str]) -> None:
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    symbol = (symbol or cfg.market.default_symbol).upper()
    interval = interval or cfg.market.interval

    bronze_ohlcv = resolve_path(root, f"{cfg.data.bronze_dir}/ohlcv")
    silver_candles = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    features_cfg = resolve_path(root, cfg.features.pipeline_config)

    part = latest_partition(bronze_ohlcv, symbol, interval)
    if part is None:
        click.echo(f"[PREPROCESS] No Bronze partition found at {bronze_ohlcv}/symbol={symbol}/interval={interval}")
        return

    files = list(part.glob("*.parquet"))
    if not files:
        click.echo(f"[PREPROCESS] No Parquet files in {part}")
        return

    df = read_parquet_many(files)
    df = clean_candles(df)
    df = validate_candles(df)
    if resample:
        df = resample_candles(df, rule=resample)
    df = run_feature_pipeline(df, pipeline_cfg_path=features_cfg)

    if df.empty:
        click.echo("[PREPROCESS] Result is empty after cleaning/resample.")
        return

    out_interval = interval if not resample else resample
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_path = write_parquet_partition(
        df=df,
        out_base=silver_candles,
        symbol=symbol,
        interval=out_interval,
        dt_str=dt_str,
        prefix="candles",
    )
    click.echo(f"[PREPROCESS] Wrote Silver candles -> {out_path}")


if __name__ == "__main__":
    main()
