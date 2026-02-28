"""CLI: create forward-return labels from Silver candles -> Gold labels."""
from __future__ import annotations

from pathlib import Path

import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many, write_parquet_partition
from src.labeling.targets import add_forward_return_labels


@click.command()
@click.option("--env", "env_name", default=None, help="Config environment (dev/prod).")
@click.option("--symbol", default=None, help="Symbol override.")
@click.option("--interval", default=None, help="Interval override.")
@click.option("--horizon", type=int, default=None, help="Forward-return horizon.")
def main(env_name, symbol, interval, horizon) -> None:
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    symbol = (symbol or cfg.market.default_symbol).upper()
    interval = interval or cfg.market.interval
    horizon = horizon if horizon is not None else cfg.labeling.default_horizon

    silver = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    gold = resolve_path(root, f"{cfg.data.gold_dir}/labels")

    part = latest_partition(silver, symbol, interval)
    if part is None:
        click.echo(f"[LABEL] No Silver partition at {silver}/symbol={symbol}/interval={interval}")
        return

    files = list(part.glob("*.parquet"))
    df = read_parquet_many(files)
    if df.empty:
        click.echo("[LABEL] Silver empty.")
        return

    df = add_forward_return_labels(df, horizon=horizon)
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out = write_parquet_partition(
        df=df,
        out_base=gold,
        symbol=symbol,
        interval=interval,
        dt_str=dt_str,
        prefix=f"labels_h{horizon}",
    )
    click.echo(f"[LABEL] Wrote labels (h={horizon}) -> {out}")


if __name__ == "__main__":
    main()
