# 05 – Persisted Backtests, Strategy Selection & Forward Test (Paper)

This step adds four pieces:

1. **Persist** backtest artefacts (metrics JSON + equity/returns CSVs).
2. A second strategy: **Bollinger Bands mean-reversion**.
3. **Strategy selection** driven by a YAML policy (metric weights + recency decay).
4. A simple **forward-test (paper)** runner that executes the selected snapshot.

Everything reuses your existing config and IO utilities.



## 0) Quick deps

```bash
pip install pandas numpy pyyaml
```



## 1) Persist backtest artefacts

### `src/backtesting/persist.py`

```python
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import json
import pandas as pd
from datetime import datetime, timezone

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def write_metrics_json(
    metrics: Dict[str, Any],
    out_dir: Path,
    filename: str = "metrics.json",
) -> Path:
    ensure_dir(out_dir)
    path = out_dir / filename
    with path.open("w") as f:
        json.dump(metrics, f, indent=2)
    return path

def write_timeseries_csv(
    series: pd.Series,
    out_dir: Path,
    filename: str,
) -> Path:
    ensure_dir(out_dir)
    df = series.to_frame(name=series.name or "value")
    path = out_dir / filename
    df.to_csv(path, index=True)
    return path

def timestamp_utc_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
```

### Update `app/backtest_cli.py` to persist

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
from src.backtesting.persist import (
    write_metrics_json,
    write_timeseries_csv,
    timestamp_utc_str,
)

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

    # Persist artefacts under data/gold/signals/<strategy>/<pair>/<interval>/dt=YYYY-MM-DD/
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/signals") / strat.name / pair / str(interval) / f"dt={dt_str}"

    ts = timestamp_utc_str()
    write_metrics_json(
        {
            "strategy": strat.name,
            "pair": pair,
            "interval_min": interval,
            "params": {"fast": fast, "slow": slow},
            "bars": int(len(df)),
            "cagr": float(m_cagr),
            "sharpe": float(m_sharpe),
            "max_drawdown": float(m_mdd),
        },
        out_dir=out_dir,
        filename=f"metrics-{ts}.json",
    )
    write_timeseries_csv(eq.rename("equity"), out_dir, filename=f"equity-{ts}.csv")
    write_timeseries_csv(r.rename("returns"), out_dir, filename=f"returns-{ts}.csv")
    click.echo(f"[BACKTEST] Saved artefacts → {out_dir}")

if __name__ == "__main__":
    main()
```



## 2) Second strategy: **Bollinger mean-reversion**

### `src/strategies/mean_reversion.py`

```python
from __future__ import annotations
import pandas as pd

class BollingerMeanReversion:
    name = "bb_mean_reversion"

    def __init__(self, window: int = 20, k: float = 2.0):
        self.window = window
        self.k = k

    def prepare(self, features: pd.DataFrame, config: dict | None = None) -> None:
        w, k = self.window, self.k
        ma = features["close"].rolling(w, min_periods=w).mean()
        sd = features["close"].rolling(w, min_periods=w).std()
        features["bb_mid"] = ma
        features["bb_up"] = ma + k * sd
        features["bb_lo"] = ma - k * sd

    def signal(self, features: pd.DataFrame) -> pd.Series:
        """
        Mean reversion: long if close < lower band, short if close > upper band, else flat.
        """
        close = features["close"]
        up = features["bb_up"]
        lo = features["bb_lo"]
        sig = pd.Series(0, index=features.index, dtype=int)
        sig = sig.mask(close < lo, 1)
        sig = sig.mask(close > up, -1)
        sig = sig.fillna(0).astype(int)
        return sig
```

### Update registry

#### `src/strategies/registry.py`

```python
from .momentum import Momentum
from .mean_reversion import BollingerMeanReversion

REGISTRY = {
    "momentum": Momentum,
    "mean_reversion": BollingerMeanReversion,
}
```



## 3) Strategy selection (policy-driven)

### `config/selection_policy.yaml`

```yaml
horizon_days: 30
metric_weights:
  sharpe: 0.6
  cagr: 0.3
  max_drawdown: 0.1   # penalised
decay_half_life_days: 14
min_bars: 200
```

### `src/selection/scorer.py`

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json
import datetime as dt

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
    out = []
    for p in dir_path.glob("metrics-*.json"):
        try:
            with p.open() as f:
                out.append(json.load(f) | {"_path": str(p)})
        except Exception:
            continue
    return out

def score_metric_row(row: Dict[str, Any], policy: SelectionPolicy, now: dt.datetime) -> float:
    # derive age from filename timestamp; fallback to 0 age
    try:
        ts = Path(row["_path"]).stem.split("metrics-")[1].rstrip("Z")
        ts_parsed = dt.datetime.strptime(ts, "%Y%m%dT%H%M%S%f")
    except Exception:
        ts_parsed = now
    age_days = (now - ts_parsed).total_seconds() / 86400.0
    decay = exp_decay_weight(age_days, policy.half_life_days)

    if row.get("bars", 0) < policy.min_bars:
        return float("-inf")

    sharpe = float(row.get("sharpe", 0.0))
    cagr   = float(row.get("cagr", 0.0))
    mdd    = float(row.get("max_drawdown", 0.0))  # negative

    w = policy.weights
    composite = (w.get("sharpe", 0)*sharpe) + (w.get("cagr", 0)*cagr) + (w.get("max_drawdown", 0)*(-mdd))
    return decay * composite
```

### `src/selection/selector.py`

```python
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
import yaml
import datetime as dt
from src.selection.scorer import SelectionPolicy, load_metrics_from_dir, score_metric_row

def load_policy(path: Path) -> SelectionPolicy:
    with path.open() as f:
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
    pair: str,
    interval: int,
) -> Optional[Dict[str, Any]]:
    """
    Look through data/gold/signals/<strategy>/<pair>/<interval>/**/metrics-*.json
    and return the single best record according to the policy.
    """
    policy = load_policy(policy_file)
    now = dt.datetime.utcnow()
    best: Tuple[float, Dict[str, Any]] | None = None

    if not signals_root.exists():
        return None

    for strategy_dir in signals_root.iterdir():
        candidate_dir = strategy_dir / pair / str(interval)
        for dt_part in candidate_dir.glob("dt=*"):
            metrics = load_metrics_from_dir(dt_part)
            for row in metrics:
                score = score_metric_row(row, policy, now)
                if best is None or score > best[0]:
                    best = (score, row)

    if best is None:
        return None
    return best[1] | {"_score": best[0]}
```

### `app/select_strategy_cli.py`

```python
"""CLI: choose best strategy by selection policy and persist the decision."""
from __future__ import annotations
from pathlib import Path
import json
import click
from src.core.configs import load_config, resolve_path
from src.selection.selector import select_best_strategy

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None)
@click.option("--interval", type=int, default=None)
def main(env_name, pair, interval):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)
    pair     = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min

    signals_root = resolve_path(root, f"{cfg.data.gold_dir}/signals")
    policy_file  = resolve_path(root, cfg.selection.policy_file)

    best = select_best_strategy(signals_root, policy_file, pair, interval)
    if not best:
        click.echo("[SELECT] No candidates found.")
        return

    # Persist selection snapshot
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/selection") / pair / str(interval)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "current_strategy.json"
    with out_path.open("w") as f:
        json.dump(best, f, indent=2)

    click.echo(f"[SELECT] Selected: {best.get('strategy')} with score={best.get('_score'):.4f}")
    click.echo(f"[SELECT] Saved → {out_path}")

if __name__ == "__main__":
    main()
```



## 4) Forward test (paper)

### `src/forward_test/paper_broker.py`

```python
from __future__ import annotations
import pandas as pd

class PaperBroker:
    """
    Ultra-simple paper broker:
      - executes at close price of the NEXT bar
      - tracks position (−1, 0, +1), equity, and PnL
      - no fees here (keep costs in strategy backtest for now)
    """
    def __init__(self, initial_equity: float = 1.0):
        self.equity = initial_equity
        self.position = 0.0

    def run(self, df: pd.DataFrame, signals: pd.Series) -> pd.Series:
        ret = df["close"].pct_change().fillna(0.0)
        pos = signals.shift(1).fillna(0.0)  # act next bar
        strat_ret = pos * ret
        equity = (1.0 + strat_ret).cumprod()
        return equity.rename("equity_paper")
```

### `src/forward_test/runner.py`

```python
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd
from src.core.io import latest_partition, read_parquet_many
from src.strategies.registry import REGISTRY
from src.forward_test.paper_broker import PaperBroker

def run_forward_test(
    silver_root: Path,
    selection_file: Path,
    out_dir: Path,
):
    """
    Load latest Silver candles, read selected strategy snapshot, run it on
    the full set (paper), and persist equity curve.
    """
    if not selection_file.exists():
        raise FileNotFoundError(f"Selection file not found: {selection_file}")

    with selection_file.open() as f:
        sel = json.load(f)

    pair = sel["pair"]
    interval = sel["interval_min"]
    strat_name = sel["strategy"]
    params = sel.get("params", {})

    part = latest_partition(silver_root, pair, interval)
    if part is None:
        raise FileNotFoundError(f"No Silver partition found for {pair}/{interval}")

    files = list(part.glob("*.parquet"))
    df = read_parquet_many(files)
    if df.empty:
        raise RuntimeError("Silver candles are empty")

    # Build signals
    StratCls = REGISTRY[strat_name if strat_name in REGISTRY else "momentum"]
    strat = StratCls(**params) if params else StratCls()
    strat.prepare(df, config=None)
    sig = strat.signal(df)

    # Paper broker
    broker = PaperBroker()
    eq = broker.run(df, sig)

    # Persist
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_path = out_dir / f"paper_equity_{strat_name}_{pair}_{interval}_dt={dt_str}.csv"
    eq.to_csv(out_path, index=True)
    return out_path
```

### `app/forward_test_cli.py`

```python
"""CLI: run forward paper test using selected strategy."""
from __future__ import annotations
from pathlib import Path
import click
from src.core.configs import load_config, resolve_path
from src.forward_test.runner import run_forward_test

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None, help="Optional override; otherwise uses selection file.")
@click.option("--interval", type=int, default=None, help="Optional override.")
def main(env_name, pair, interval):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    silver_root = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    selection_file = resolve_path(root, f"{cfg.data.gold_dir}/selection") / (pair or cfg.kraken.pair) / str(interval or cfg.kraken.interval_min) / "current_strategy.json"
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/forward_tests")

    try:
        out_path = run_forward_test(silver_root, selection_file, out_dir)
        click.echo(f"[FORWARD] Paper equity saved → {out_path}")
    except Exception as e:  # keep cli friendly
        click.echo(f"[FORWARD] Failed: {e}")

if __name__ == "__main__":
    main()
```



## 5) How to use (end-to-end)

From the repo root:

```bash
# 1) Ingest real data to Bronze
python -m app.ingest_cli --pair XXBTZUSD --interval 1

# 2) Bronze -> Silver
python -m app.preprocess_cli --pair XXBTZUSD --interval 1

# 3) Backtest a couple of strategies (persist metrics/equities)
python -m app.backtest_cli --pair XXBTZUSD --interval 1 --fast 20 --slow 50
python -m app.backtest_cli --pair XXBTZUSD --interval 1 --fast 10 --slow 40
# (EMA variants are fine for diversity; BB signals are available via registry for forward tests)

# 4) Select the best strategy (by selection_policy.yaml)
python -m app.select_strategy_cli --pair XXBTZUSD --interval 1

# 5) Forward test (paper) using the selected strategy snapshot
python -m app.forward_test_cli --pair XXBTZUSD --interval 1
```

**On disk you’ll have:**

* `data/gold/signals/<strategy>/<pair>/<interval>/dt=.../metrics-*.json`, `equity-*.csv`, `returns-*.csv`
* `data/gold/selection/<pair>/<interval>/current_strategy.json`
* `data/gold/forward_tests/paper_equity_...csv`
