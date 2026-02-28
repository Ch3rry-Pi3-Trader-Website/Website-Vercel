# 08 – Config-First Labels + Makefile Defaults

This step adds:

* A **default label horizon** to config (env-overrideable).
* A **typed config** update and a config-first `label_cli.py` (flags still override).
* A **Makefile** that defaults to `APP_ENV=dev` for smooth local runs.



## 1) Add default label horizon to config

### `config/base.yaml` (append)

```yaml
labeling:
  default_horizon: 1
```

> Override per environment later (e.g., `config/dev.yaml`, `config/prod.yaml`) if you want different horizons.



## 2) Extend the typed config model

### `src/core/configs.py` (add model + field)

```python
# ... existing imports and models ...

class LabelingConfig(BaseModel):
    default_horizon: int = 1

class Config(BaseModel):
    app: AppConfig = AppConfig()
    data: DataConfig = DataConfig()
    kraken: KrakenConfig = KrakenConfig()
    fees: FeesConfig = FeesConfig()
    features: FeaturesConfig = FeaturesConfig()
    selection: SelectionConfig = SelectionConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    labeling: LabelingConfig = LabelingConfig()   # <-- add this line
```

No other changes needed here.



## 3) Config-first `label_cli.py` (flag overrides still work)

### `app/label_cli.py` (drop-in replacement)

```python
"""CLI: create labels from Silver candles → Gold/labels (config-first)."""
from __future__ import annotations

from pathlib import Path
import click
import pandas as pd

from src.core.configs import load_config, resolve_path
from src.core.io import latest_partition, read_parquet_many, write_parquet_partition
from src.labeling.targets import add_forward_return_labels

@click.command()
@click.option("--env", "env_name", default=None, help="Config environment (dev/prod).")
@click.option("--pair", default=None, help="Override pair (e.g., XXBTZUSD).")
@click.option("--interval", type=int, default=None, help="Override interval (minutes).")
@click.option("--horizon", type=int, default=None, help="Forward-return horizon; overrides config.")
def main(env_name, pair, interval, horizon):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    pair     = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min
    horizon  = horizon if horizon is not None else cfg.labeling.default_horizon

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
    out = write_parquet_partition(
        df=df,
        out_base=gold,
        pair=pair,
        interval=interval,
        dt_str=dt_str,
        prefix=f"labels_h{horizon}",
    )
    click.echo(f"[LABEL] Wrote labels (h={horizon}) → {out}")

if __name__ == "__main__":
    main()
```



## 4) Selection already uses config ✅

`select_strategy_cli.py` reads the policy path from `cfg.selection.policy_file`, so no changes required.



## 5) Makefile with `APP_ENV=dev` defaults

### `Makefile` (repo root)

```make
# Default environment (override like: make backtest APP_ENV=prod)
APP_ENV ?= dev
PY ?= python

.PHONY: ingest preprocess label bt-ema bt-bb select forward all

ingest:
	APP_ENV=$(APP_ENV) $(PY) -m app.ingest_cli

preprocess:
	APP_ENV=$(APP_ENV) $(PY) -m app.preprocess_cli

label:
	APP_ENV=$(APP_ENV) $(PY) -m app.label_cli

bt-ema:
	APP_ENV=$(APP_ENV) $(PY) -m app.backtest_cli --strategy momentum

bt-bb:
	APP_ENV=$(APP_ENV) $(PY) -m app.backtest_cli --strategy mean_reversion

select:
	APP_ENV=$(APP_ENV) $(PY) -m app.select_strategy_cli

forward:
	APP_ENV=$(APP_ENV) $(PY) -m app.forward_test_cli

all:
	$(MAKE) ingest
	$(MAKE) preprocess
	$(MAKE) bt-ema
	$(MAKE) bt-bb
	$(MAKE) select
	$(MAKE) forward
```

**Usage**

```bash
make all                 # runs with APP_ENV=dev
make ingest preprocess   # just the first stages
make bt-ema APP_ENV=prod # run with prod overrides
```

