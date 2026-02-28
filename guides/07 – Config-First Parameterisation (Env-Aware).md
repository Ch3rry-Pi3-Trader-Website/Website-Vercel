# 07 – Config-First Parameterisation (Env-Aware)

This step implements **Step 3: Config first**, making your bot fully parameterised and environment-aware:

* Create YAML configs in `config/`
* Typed loader (`src/core/configs.py`) with deep-merge and path resolution
* Refactor CLIs to pull **pair/interval/paths/strategy params** from config by default
  (CLI flags still override)

**Precedence:** CLI flags ⟶ `{env}.yaml` ⟶ `base.yaml`
**Env selection:** `APP_ENV=dev|prod` (default: `dev`)



## 1) YAMLs (drop these in)

### `config/base.yaml`

```yaml
app:
  name: kraken-trader
  timezone: UTC

data:
  bronze_dir: data/bronze
  silver_dir: data/silver
  gold_dir: data/gold

kraken:
  pair: XXBTZUSD
  interval_min: 1

fees:
  taker_bps: 26     # 0.26%
  maker_bps: 16     # 0.16%

features:
  pipeline_config: config/features/pipeline.yaml

selection:
  policy_file: config/selection_policy.yaml

runtime:
  paper_trading: true
```

### `config/dev.yaml`

```yaml
# Dev overrides
kraken:
  interval_min: 1
runtime:
  paper_trading: true
```

### `config/prod.yaml`  *(optional but handy)*

```yaml
# Prod overrides
runtime:
  paper_trading: false
fees:
  taker_bps: 20
  maker_bps: 10
```

### `config/strategies/momentum.yaml`

```yaml
name: momentum
params:
  fast: 20
  slow: 50
```

### `config/strategies/mean_reversion.yaml`

```yaml
name: mean_reversion
params:
  window: 20
  k: 2.0
```

### `config/selection_policy.yaml`

```yaml
horizon_days: 30
metric_weights:
  sharpe: 0.6
  cagr: 0.3
  max_drawdown: 0.1
decay_half_life_days: 14
min_bars: 200
```

*(Keep your existing `config/features/pipeline.yaml` placeholder from earlier steps.)*



## 2) Typed loader

### `src/core/configs.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import os
import yaml
from pydantic import BaseModel

# - Pydantic models -

class AppConfig(BaseModel):
    name: str = "kraken-trader"
    timezone: str = "UTC"

class DataConfig(BaseModel):
    bronze_dir: str = "data/bronze"
    silver_dir: str = "data/silver"
    gold_dir: str = "data/gold"

class KrakenConfig(BaseModel):
    pair: str = "XXBTZUSD"
    interval_min: int = 1

class FeesConfig(BaseModel):
    taker_bps: int = 26
    maker_bps: int = 16

class FeaturesConfig(BaseModel):
    pipeline_config: str = "config/features/pipeline.yaml"

class SelectionConfig(BaseModel):
    policy_file: str = "config/selection_policy.yaml"

class RuntimeConfig(BaseModel):
    paper_trading: bool = True

class Config(BaseModel):
    app: AppConfig = AppConfig()
    data: DataConfig = DataConfig()
    kraken: KrakenConfig = KrakenConfig()
    fees: FeesConfig = FeesConfig()
    features: FeaturesConfig = FeaturesConfig()
    selection: SelectionConfig = SelectionConfig()
    runtime: RuntimeConfig = RuntimeConfig()

# - YAML helpers -

def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r") as f:
        return yaml.safe_load(f) or {}

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

# - Public API -

def load_config(env: Optional[str] = None, root: Optional[Path] = None) -> Config:
    """
    Load base.yaml overlaid by {env}.yaml.
    env comes from arg, $APP_ENV, or defaults to 'dev'.
    """
    root = root or Path.cwd()
    cfg_dir = root / "config"

    base = _read_yaml(cfg_dir / "base.yaml")
    env_name = (env or os.getenv("APP_ENV") or "dev").lower()
    overlay = _read_yaml(cfg_dir / f"{env_name}.yaml")

    merged = _deep_merge(base, overlay)
    return Config.model_validate(merged)

def resolve_path(root: Path, maybe_rel: str) -> Path:
    p = Path(maybe_rel)
    return p if p.is_absolute() else (root / p)

def load_strategy_params(root: Path, strategy_name: str) -> Dict[str, Any]:
    """
    Read config/strategies/<strategy_name>.yaml → {"name": ..., "params": {...}}
    Returns empty params if file missing.
    """
    path = root / "config" / "strategies" / f"{strategy_name}.yaml"
    data = _read_yaml(path)
    return data.get("params", {}) if data else {}
```



## 3) Refactor CLIs (config-first, flags override)

### `app/ingest_cli.py`

```python
"""CLI to fetch OHLC from Kraken and land into Bronze."""
import click
from pathlib import Path

from src.core.configs import load_config, resolve_path
from src.ingestion.ohlc_fetcher import fetch_ohlc_to_bronze

@click.command()
@click.option("--env", "env_name", default=None, help="Config env (dev/prod).")
@click.option("--pair", default=None, help="Override Kraken pair.")
@click.option("--interval", type=int, default=None, help="Override OHLC interval (min).")
@click.option("--outdir", default=None, help="Override output base dir.")
def main(env_name, pair, interval, outdir):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min
    out_base = outdir or f"{cfg.data.bronze_dir}/ohlc"
    out_base = str(resolve_path(root, out_base))

    path, n = fetch_ohlc_to_bronze(pair=pair, interval=interval, out_base=out_base)
    click.echo(f"[INGEST] Wrote {n} OHLC rows → {path}")

if __name__ == "__main__":
    main()
```

### `app/backtest_cli.py` (reads defaults from strategy YAML; CLI overrides supported)

```python
"""CLI: run strategy backtest on latest Silver candles (EMA or Bollinger)."""
from __future__ import annotations

from pathlib import Path
import click
import pandas as pd

from src.core.logging import setup_logging
from src.core.configs import load_config, resolve_path, load_strategy_params
from src.core.io import latest_partition, read_parquet_many
from src.strategies.registry import REGISTRY
from src.backtesting.engine import run_backtest
from src.backtesting.metrics import cagr, sharpe, max_drawdown
from src.backtesting.persist import write_metrics_json, write_timeseries_csv, timestamp_utc_str

@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--pair", default=None, help="Override pair")
@click.option("--interval", type=int, default=None, help="Override interval (min)")
@click.option("--strategy", type=click.Choice(["momentum","mean_reversion"]), default="momentum", show_default=True)
# EMA overrides
@click.option("--fast", type=int, default=None, help="EMA fast (overrides config)")
@click.option("--slow", type=int, default=None, help="EMA slow (overrides config)")
# Bollinger overrides
@click.option("--bb-window", type=int, default=None, help="BB window (overrides config)")
@click.option("--bb-k", type=float, default=None, help="BB k (overrides config)")
@click.option("--log-level", default="INFO", show_default=True)
def main(env_name, pair, interval, strategy, fast, slow, bb_window, bb_k, log_level):
    log = setup_logging(log_level)
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair     = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min

    # strategy defaults from YAML
    defaults = load_strategy_params(root, strategy)
    # precedence: CLI > strategy YAML > fallback
    if strategy == "momentum":
        fast = fast if fast is not None else int(defaults.get("fast", 20))
        slow = slow if slow is not None else int(defaults.get("slow", 50))
        params = {"fast": fast, "slow": slow}
    else:
        bb_window = bb_window if bb_window is not None else int(defaults.get("window", 20))
        bb_k = bb_k if bb_k is not None else float(defaults.get("k", 2.0))
        params = {"window": bb_window, "k": bb_k}

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

    # instantiate & signal
    Strat = REGISTRY[strategy]
    strat = Strat(**params)
    strat.prepare(df)
    sig = strat.signal(df)

    # backtest
    res = run_backtest(df=df, signal=sig, interval_min=interval, taker_bps=cfg.fees.taker_bps)
    r, eq = res["returns"], res["equity"]

    # metrics
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

    # persist
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



## 4) Sanity checks

From repo root:

```bash
# Use dev config defaults
python -m app.ingest_cli --env dev
python -m app.preprocess_cli --env dev

# Backtest using strategy YAML defaults (no numeric flags needed)
python -m app.backtest_cli --env dev --strategy momentum
python -m app.backtest_cli --env dev --strategy mean_reversion

# Override on the fly (keeps config for everything else)
python -m app.backtest_cli --env dev --strategy momentum --fast 10 --slow 40
python -m app.backtest_cli --env dev --strategy mean_reversion --bb-window 30 --bb-k 2.5
```

**Result:** Everything is now parameterised via **env → YAML config**, with **CLI flags** only when you want to override.
