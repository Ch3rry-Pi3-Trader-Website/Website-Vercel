from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import os

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "pi3-invest-backend"
    timezone: str = "UTC"


class DataConfig(BaseModel):
    bronze_dir: str = "data/bronze"
    silver_dir: str = "data/silver"
    gold_dir: str = "data/gold"


class MarketConfig(BaseModel):
    default_symbol: str = "SPY"
    default_universe: str = "sp500"
    interval: str = "1d"
    interval_min: int = 1440
    lookback_days: int = 30
    universe_cache_file: str = "data/reference/sp500_symbols.json"
    fallback_symbols: list[str] = Field(default_factory=lambda: ["SPY", "AAPL", "MSFT"])


class IngestionConfig(BaseModel):
    provider: str = "yfinance"
    batch_size: int = 50
    auto_adjust: bool = True
    pause_seconds: float = 0.1
    max_retries: int = 2


class FeesConfig(BaseModel):
    taker_bps: int = 4
    maker_bps: int = 2


class FeaturesConfig(BaseModel):
    pipeline_config: str = "config/features/pipeline.yaml"


class SelectionConfig(BaseModel):
    policy_file: str = "config/selection_policy.yaml"


class RuntimeConfig(BaseModel):
    paper_trading: bool = True


class LabelingConfig(BaseModel):
    default_horizon: int = 1


class RiskConfig(BaseModel):
    max_position: float = 1.0
    flip_cooldown_bars: int = 0
    daily_loss_cap: float = 0.0


class Config(BaseModel):
    app: AppConfig = AppConfig()
    data: DataConfig = DataConfig()
    market: MarketConfig = MarketConfig()
    ingestion: IngestionConfig = IngestionConfig()
    fees: FeesConfig = FeesConfig()
    features: FeaturesConfig = FeaturesConfig()
    selection: SelectionConfig = SelectionConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    labeling: LabelingConfig = LabelingConfig()
    risk: RiskConfig = RiskConfig()


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    out = dict(a)
    for key, value in b.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(env: Optional[str] = None, root: Optional[Path] = None) -> Config:
    root = root or Path.cwd()
    cfg_dir = root / "config"

    base = _read_yaml(cfg_dir / "base.yaml")
    env_name = (env or os.getenv("APP_ENV") or "dev").lower()
    overlay = _read_yaml(cfg_dir / f"{env_name}.yaml")

    merged = _deep_merge(base, overlay)
    return Config.model_validate(merged)


def resolve_path(root: Path, maybe_relative: str) -> Path:
    p = Path(maybe_relative)
    return p if p.is_absolute() else (root / p)


def load_strategy_params(root: Path, strategy_name: str) -> Dict[str, Any]:
    path = root / "config" / "strategies" / f"{strategy_name}.yaml"
    data = _read_yaml(path)
    return data.get("params", {}) if data else {}
