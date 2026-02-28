# 04 – Labels, EMA Strategy, and Backtest

This step gives you a **minimal, runnable** pipeline from Silver candles to:

1. **Labels** (forward returns),
2. A simple **EMA(20/50) momentum** strategy,
3. A **vectorised backtest** with core metrics (CAGR, Sharpe, Max Drawdown).

Everything reuses your YAML config and IO utilities.



## 0) Dependencies

```bash
pip install pandas numpy
```



## 1) Labels (Gold)

### `src/labeling/targets.py`

```python
from __future__ import annotations
import pandas as pd

def add_forward_return_labels(df: pd.DataFrame, horizon: int = 1) -> pd.DataFrame:
    """
    Adds forward return label over `horizon` bars:
      fwd_ret_{h} = close.shift(-h) / close - 1
    Keeps index/order. Does not drop NaNs at the tail.
    """
    out = df.copy()
    col = f"fwd_ret_{horizon}"
    out[col] = out["close"].shift(-horizon) / out["close"] - 1.0
    return out
```

### `src/labeling/splits.py`

```python
from __future__ import annotations
from typing import Iterator, Tuple
import pandas as pd

def rolling_windows(
    df: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step: int,
) -> Iterator[Tuple[pd.Index, pd.Index]]:
    """
    Yield (train_idx, test_idx) rolling windows using positional indexing.
    """
    n = len(df)
    start = 0
    while start + train_bars + test_bars <= n:
        train_idx = df.index[start : start + train_bars]
        test_idx  = df.index[start + train_bars : start + train_bars + test_bars]
        yield train_idx, test_idx
        start += step
```

### `app/label_cli.py`

```python
"""CLI: create labels from Silver candles → Gold/labels"""
from __future__ import annotations

from pathlib import Path
import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many, write_parquet_partition
from src.labeling.targets import add_forward_return_labels

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None)
@click.option("--interval", type=int, default=None)
@click.option("--horizon", type=int, default=1, show_default=True)
def main(env_name, pair, interval, horizon):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair     = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min

    silver = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    gold   = resolve_path(root,  f"{cfg.data.gold_dir}/labels")

    part = latest_partition(silver, pair, interval)
    if part is None:
        click.echo(f"[LABEL] No Silver partition at {silver}/{pair}/{interval}")
        return

    files = list(part.glob("*.parquet"))
    if not files:
        click.echo(f"[LABEL] No files in {part}")
        return

    df = read_parquet_many(files)
    if df.empty:
        click.echo("[LABEL] Silver empty.")
        return

    df = add_forward_return_labels(df, horizon=horizon)

    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out = write_parquet_partition(df, gold, pair, interval, dt_str, prefix=f"labels_h{horizon}")
    click.echo(f"[LABEL] Wrote labels (h={horizon}) → {out}")

if __name__ == "__main__":
    main()
```



## 2) Strategy – EMA(20/50) Momentum

### `src/strategies/momentum.py`

```python
from __future__ import annotations
import pandas as pd

class Momentum:
    name = "ema_crossover"

    def __init__(self, fast: int = 20, slow: int = 50):
        if fast >= slow:
            raise ValueError("fast EMA must be < slow EMA")
        self.fast = fast
        self.slow = slow

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        f, s = self.fast, self.slow
        features[f"ema_{f}"] = features["close"].ewm(span=f, adjust=False, min_periods=f).mean()
        features[f"ema_{s}"] = features["close"].ewm(span=s, adjust=False, min_periods=s).mean()
        features["spread"] = features[f"ema_{f}"] - features[f"ema_{s}"]

    def signal(self, features: pd.DataFrame) -> pd.Series:
        """
        +1 when fast>slow, -1 when fast<slow, 0 on NaNs.
        We use sign of spread; tie → 0.
        """
        sig = features["spread"].copy()
        sig = sig.where(sig.notna(), 0.0)
        sig = sig.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        return sig.astype(int)
```

*(Ensure your `registry.py` maps at least one name to this strategy):*

### `src/strategies/registry.py`

```python
from .momentum import Momentum

REGISTRY = {
    "momentum": Momentum,
}
```



## 3) Backtest Engine & Metrics

### `src/backtesting/metrics.py`

```python
from __future__ import annotations
import numpy as np
import pandas as pd

def annualisation_factor(interval_min: int) -> float:
    # bars per year (365 days)
    return (365 * 24 * 60) / interval_min

def cagr(equity: pd.Series, interval_min: int) -> float:
    if equity.empty:
        return 0.0
    start, end = equity.iloc[0], equity.iloc[-1]
    if start <= 0 or end <= 0:
        return 0.0
    n_bars = len(equity)
    bars_per_year = annualisation_factor(interval_min)
    years = n_bars / bars_per_year
    if years <= 0:
        return 0.0
    return (end / start) ** (1 / years) - 1.0

def sharpe(returns: pd.Series, interval_min: int, risk_free: float = 0.0) -> float:
    if returns.empty:
        return 0.0
    ex = returns - (risk_free / annualisation_factor(interval_min))
    if ex.std(ddof=1) == 0:
        return 0.0
    return np.sqrt(annualisation_factor(interval_min)) * ex.mean() / ex.std(ddof=1)

def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    roll_max = equity.cummax()
    dd = (equity / roll_max) - 1.0
    return dd.min()
```

### `src/backtesting/engine.py`

```python
from __future__ import annotations
import pandas as pd

def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    interval_min: int,
    taker_bps: int = 26,
) -> dict:
    """
    Vectorised long/short backtest:
    - Market returns: close.pct_change()
    - Strategy uses prior bar's signal (1, -1, 0)
    - Transaction cost when signal changes: taker_bps (basis points) per change
    """
    data = df.copy().reset_index(drop=True)
    data["ret"] = data["close"].pct_change().fillna(0.0)

    pos = signal.astype(float).shift(1).fillna(0.0)  # enter next bar
    # transaction cost when position changes
    turns = (pos.diff().abs().fillna(0.0) > 0).astype(int)
    tc = (taker_bps / 1e4) * turns  # convert bps to proportion

    strat_ret = (pos * data["ret"]) - tc
    equity = (1.0 + strat_ret).cumprod()

    return {
        "returns": strat_ret,
        "equity": equity,
        "positions": pos,
        "interval_min": interval_min,
    }
```



## 4) Backtest CLI

### `app/backtest_cli.py`

```python
"""CLI: run EMA(20/50) momentum backtest on latest Silver candles."""
from __future__ import annotations

from pathlib import Path
import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many
from src.strategies.momentum import Momentum
from src.backtesting.engine import run_backtest
from src.backtesting.metrics import cagr, sharpe, max_drawdown

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None)
@click.option("--interval", type=int, default=None)
@click.option("--fast", type=int, default=20, show_default=True)
@click.option("--slow", type=int, default=50, show_default=True)
def main(env_name, pair, interval, fast, slow):
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

    # Prepare features & signals
    strat = Momentum(fast=fast, slow=slow)
    strat.prepare(df)
    sig = strat.signal(df)

    # Run backtest
    res = run_backtest(
        df=df,
        signal=sig,
        interval_min=interval,
        taker_bps=cfg.fees.taker_bps,
    )

    r  = res["returns"]
    eq = res["equity"]

    # Metrics
    m_cagr   = cagr(eq, interval_min=interval)
    m_sharpe = sharpe(r, interval_min=interval)
    m_mdd    = max_drawdown(eq)

    click.echo(f"[BACKTEST] Strategy={strat.name} {fast}/{slow}  Bars={len(df)}")
    click.echo(f"  CAGR:    {m_cagr: .2%}")
    click.echo(f"  Sharpe:  {m_sharpe: .2f}")
    click.echo(f"  MaxDD:   {m_mdd: .2%}")

if __name__ == "__main__":
    main()
```



## 5) How to Run (repo root)

```bash
# (Assumes you already produced Silver candles via preprocess)
python -m app.label_cli --horizon 1           # optional: writes labels to gold
python -m app.backtest_cli                    # default EMA 20/50, from config

# Try alternatives
python -m app.backtest_cli --fast 10 --slow 40
python -m app.backtest_cli --env prod
```

**Output:**
Backtest prints **CAGR**, **Sharpe**, **Max Drawdown** for the latest Silver partition (no extra disk writes here).

