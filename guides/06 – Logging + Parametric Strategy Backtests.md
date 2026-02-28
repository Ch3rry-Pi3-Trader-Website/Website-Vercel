# 06 – Logging + Parametric Strategy Backtests

This upgrade adds:

* A shared **minimal logging** setup.
* A unified **backtest CLI** with `--strategy` to choose **EMA momentum** or **Bollinger mean-reversion**, each with their own params.
* Persisted metrics & timeseries (as before).
* Optional **Makefile** targets for quick runs.



## 1) Minimal logging (shared)

### `src/core/logging.py`

```python
import logging
from typing import Optional

def setup_logging(level: str = "INFO") -> logging.Logger:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=lvl,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("strategybot")
```

Usage:

```python
from src.core.logging import setup_logging
log = setup_logging()
log.info("hello")
```



## 2) Backtest CLI with `--strategy` + Bollinger params

Replace your file with the following:

### `app/backtest_cli.py`

```python
"""CLI: run strategy backtest on latest Silver candles (EMA or Bollinger)."""
from __future__ import annotations

from pathlib import Path
import click
import pandas as pd

from src.core.logging import setup_logging
from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many
from src.strategies.registry import REGISTRY
from src.backtesting.engine import run_backtest
from src.backtesting.metrics import cagr, sharpe, max_drawdown
from src.backtesting.persist import write_metrics_json, write_timeseries_csv, timestamp_utc_str

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None)
@click.option("--interval", type=int, default=None)
@click.option("--strategy", type=click.Choice(["momentum","mean_reversion"]), default="momentum", show_default=True)
# EMA params
@click.option("--fast", type=int, default=20, show_default=True, help="EMA fast (momentum)")
@click.option("--slow", type=int, default=50, show_default=True, help="EMA slow (momentum)")
# Bollinger params
@click.option("--bb-window", type=int, default=20, show_default=True, help="BB window (mean_reversion)")
@click.option("--bb-k", type=float, default=2.0, show_default=True, help="BB k (mean_reversion)")
@click.option("--log-level", default="INFO", show_default=True)
def main(env_name, pair, interval, strategy, fast, slow, bb_window, bb_k, log_level):
    log = setup_logging(log_level)
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair     = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min

    silver = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    part = latest_partition(silver, pair, interval)
    if part is None:
        click.echo(f"[BACKTEST] No Silver partition at {silver}/{pair}/{interval}")
        return

    files = list(part.glob("*.parquet"))
    if not files:
        click.echo(f"[BACKTEST] No files in {part}")
        return

    df = read_parquet_many(files)
    if df.empty:
        click.echo("[BACKTEST] Silver empty.")
        return

    # Instantiate strategy
    Strat = REGISTRY[strategy]
    if strategy == "momentum":
        strat = Strat(fast=fast, slow=slow)
        params = {"fast": fast, "slow": slow}
    else:
        strat = Strat(window=bb_window, k=bb_k)
        params = {"window": bb_window, "k": bb_k}

    # Prepare & signal
    strat.prepare(df)
    sig = strat.signal(df)

    # Backtest
    res = run_backtest(
        df=df,
        signal=sig,
        interval_min=interval,
        taker_bps=cfg.fees.taker_bps,
    )
    r, eq = res["returns"], res["equity"]

    # Metrics
    m = {
        "strategy": strategy,
        "pair": pair,
        "interval_min": interval,
        "params": params,
        "bars": int(len(df)),
        "cagr": float(cagr(eq, interval)),
        "sharpe": float(sharpe(r, interval)),
        "max_drawdown": float(max_drawdown(eq)),
    }
    click.echo(f"[BACKTEST] {strategy} | Bars={m['bars']} | CAGR={m['cagr']:.2%} | Sharpe={m['sharpe']:.2f} | MaxDD={m['max_drawdown']:.2%}")

    # Persist
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/signals") / strat.name / pair / str(interval) / f"dt={dt_str}"
    ts = timestamp_utc_str()
    write_metrics_json(m, out_dir, filename=f"metrics-{ts}.json")
    write_timeseries_csv(eq.rename("equity"), out_dir, filename=f"equity-{ts}.csv")
    write_timeseries_csv(r.rename("returns"), out_dir, filename=f"returns-{ts}.csv")
    click.echo(f"[BACKTEST] Saved artefacts → {out_dir}")

if __name__ == "__main__":
    main()
```

### Examples

```bash
# EMA momentum
python -m app.backtest_cli --strategy momentum --fast 10 --slow 40

# Bollinger mean-reversion
python -m app.backtest_cli --strategy mean_reversion --bb-window 20 --bb-k 2.0
```



## 3) Ensure registry has both strategies

### `src/strategies/registry.py`

```python
from .momentum import Momentum
from .mean_reversion import BollingerMeanReversion

REGISTRY = {
    "momentum": Momentum,
    "mean_reversion": BollingerMeanReversion,
}
```



## 4) (Optional) Makefile refresh

```make
ingest:       ; python -m app.ingest_cli
preprocess:   ; python -m app.preprocess_cli
bt-ema:       ; python -m app.backtest_cli --strategy momentum --fast 20 --slow 50
bt-bb:        ; python -m app.backtest_cli --strategy mean_reversion --bb-window 20 --bb-k 2.0
select:       ; python -m app.select_strategy_cli
forward:      ; python -m app.forward_test_cli
pipeline:     ; python -m flows.five_min_pipeline
```



## Done

You now have:

* Shared logging across CLIs (`--log-level` supported in backtests),
* Switchable strategies with parameterised inputs (EMA / Bollinger),
* Persisted metrics & curves compatible with your selection step.

