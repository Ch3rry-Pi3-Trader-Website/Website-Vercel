from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.core.io import latest_partition, read_parquet_many
from src.forward_test.paper_broker import PaperBroker
from src.strategies.registry import REGISTRY


def run_forward_test(
    silver_root: Path,
    selection_file: Path,
    out_dir: Path,
    taker_bps: int,
    max_position: float,
    flip_cooldown_bars: int,
    daily_loss_cap: float,
) -> Path:
    if not selection_file.exists():
        raise FileNotFoundError(f"Selection file not found: {selection_file}")

    with selection_file.open("r", encoding="utf-8") as f:
        sel = json.load(f)

    symbol = sel["symbol"]
    interval = sel["interval"]
    strat_name = sel["strategy"]
    params = sel.get("params", {})

    part = latest_partition(silver_root, symbol, interval)
    if part is None:
        raise FileNotFoundError(f"No Silver partition found for {symbol}/{interval}")

    files = list(part.glob("*.parquet"))
    df = read_parquet_many(files)
    if df.empty:
        raise RuntimeError("Silver candles are empty")

    StratCls = REGISTRY[strat_name if strat_name in REGISTRY else "momentum"]
    strat = StratCls(**params) if params else StratCls()
    strat.prepare(df, config=None)
    sig = strat.signal(df)

    broker = PaperBroker()
    eq = broker.run(
        df=df,
        signals=sig,
        taker_bps=taker_bps,
        max_position=max_position,
        flip_cooldown_bars=flip_cooldown_bars,
        daily_loss_cap=daily_loss_cap,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_path = out_dir / f"paper_equity_{strat_name}_{symbol}_{interval}_dt={dt_str}.csv"
    eq.to_csv(out_path, index=True)
    return out_path
