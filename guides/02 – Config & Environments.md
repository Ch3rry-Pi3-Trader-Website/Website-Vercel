# 02 – Config & Environments (YAML + Pydantic)

This step wires up a **typed configuration layer** so your bot is fully parameterised and environment-aware. You’ll define defaults in `config/base.yaml`, overlay them with `config/{env}.yaml`, and still allow **CLI flags to override** everything at runtime.

**Precedence:**
CLI flags ⟶ `{env}.yaml` ⟶ `base.yaml`



## 1) Install lightweight dependencies

```bash
pip install pyyaml pydantic click
```



## 2) Create your YAMLs

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
  taker_bps: 26   # 0.26%
  maker_bps: 16   # 0.16%

features:
  pipeline_config: config/features/pipeline.yaml

selection:
  policy_file: config/selection_policy.yaml

runtime:
  paper_trading: true
```

### `config/dev.yaml`

```yaml
kraken:
  interval_min: 1
runtime:
  paper_trading: true
```

### `config/prod.yaml`

```yaml
runtime:
  paper_trading: false
fees:
  taker_bps: 20
  maker_bps: 10
```

> Choose environment via `APP_ENV=dev|prod` (default: `dev`).
> Windows PowerShell: `$env:APP_ENV = "prod"`
> bash/zsh: `export APP_ENV=prod`



## 3) Typed config loader

### `src/core/configs.py`

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import os
import yaml
from pydantic import BaseModel


#  Pydantic models (typed config) 

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


#  YAML helpers 

def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge b into a (recursive), returning a new dict."""
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


#  Public API 

def load_config(env: Optional[str] = None, root: Optional[Path] = None) -> Config:
    """
    Load base.yaml and overlay {env}.yaml (env from arg or $APP_ENV, default 'dev').
    Returns a typed Config object.
    """
    root = root or Path.cwd()
    cfg_dir = root / "config"

    base = _read_yaml(cfg_dir / "base.yaml")

    env_name = (env or os.getenv("APP_ENV") or "dev").lower()
    overlay = _read_yaml(cfg_dir / f"{env_name}.yaml")

    merged = _deep_merge(base, overlay)
    return Config.model_validate(merged)

def resolve_path(root: Path, maybe_rel: str) -> Path:
    """Turn a config path into an absolute Path anchored at repo root."""
    p = Path(maybe_rel)
    return p if p.is_absolute() else (root / p)
```



## 4) Use config in your CLI (flags still override)

### `app/ingest_cli.py`

```python
"""CLI to fetch OHLC from Kraken and land into Bronze."""
from pathlib import Path
import click

from src.core.configs import load_config, resolve_path
from src.ingestion.ohlc_fetcher import fetch_ohlc_to_bronze


@click.command()
@click.option("--env", "env_name", default=None,
              help="Config environment (dev/prod). Defaults to $APP_ENV or dev.")
@click.option("--pair", default=None, help="Kraken pair, overrides config.")
@click.option("--interval", type=int, default=None, help="OHLC interval (min), overrides config.")
@click.option("--outdir", default=None, help="Output base directory, overrides config.")
def main(env_name, pair, interval, outdir):
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    # Resolve with precedence: CLI > config
    pair = pair or cfg.kraken.pair
    interval = interval or cfg.kraken.interval_min
    out_base = outdir or f"{cfg.data.bronze_dir}/ohlc"
    out_base = str(resolve_path(root, out_base))

    path, n = fetch_ohlc_to_bronze(pair=pair, interval=interval, out_base=out_base)
    click.echo(f"[INGEST] Wrote {n} OHLC rows → {path}")


if __name__ == "__main__":
    main()
```

> If you still have the stubbed fetcher from earlier, keep its signature as `fetch_ohlc_to_bronze(pair, interval, out_base)` and have it return `(path, n)` even if values are mocked—this keeps the CLI stable when you implement real IO.



## 5) Run it

From the repo root:

```bash
# default env (dev)
python -m app.ingest_cli

# explicit env
python -m app.ingest_cli --env dev
python -m app.ingest_cli --env prod

# override values via flags
python -m app.ingest_cli --env dev --pair XXBTZUSD --interval 5
```

**What you get now**

* Single source of truth in `config/*.yaml`.
* Clean layering: **base** ⟶ **env overlay** ⟶ **CLI flag**.
* Paths resolved against project root, so outputs land where you expect.
