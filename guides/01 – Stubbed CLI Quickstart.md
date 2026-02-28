
# 01 – Stubbed CLI Quickstart

This guide sets up **minimal runnable stubs** so every stage of the pipeline can execute end-to-end without external services or dependencies. Each CLI just **prints what it would do** (no network calls, no file writes beyond ensuring folders exist). This lets you validate the wiring before implementing real logic.

> **Why stubs?**
>
> * Sanity-check the project layout and imports.
> * Verify CLI entry points and parameters.
> * Unblock CI and enable early tests.



## Quickstart (run from repo root)

```bash
python -m app.ingest_cli --pair XXBTZUSD --interval 1
python -m app.preprocess_cli --pair XXBTZUSD
python -m app.label_cli --pair XXBTZUSD --target triple_barrier
python -m app.backtest_cli --pair XXBTZUSD --strategies momentum mean_reversion breakout
python -m app.select_strategy_cli --pair XXBTZUSD
python -m app.forward_test_cli --pair XXBTZUSD --mode paper
python -m app.trade_cli --pair XXBTZUSD --confirm
```

> All commands are stubbed and will **print** what they’d do, without touching external services. No third-party deps required.



## app/ingest\_cli.py

```python
"""CLI to fetch OHLC/trades from Kraken and land into Bronze layer (STUB)."""
import argparse
from src.ingestion.ohlc_fetcher import fetch_ohlc_to_bronze
from src.ingestion.trades_fetcher import fetch_trades_to_bronze


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD", help="Trading pair symbol")
    p.add_argument("--interval", type=int, default=1, help="OHLC interval (minutes)")
    p.add_argument("--trades", action="store_true", help="Also fetch recent trades")
    return p.parse_args()


def main():
    args = parse_args()
    print(f"[INGEST:STUB] Would fetch OHLC for {args.pair} @ {args.interval}m and write to data/bronze/ohlc …")
    fetch_ohlc_to_bronze(args.pair, args.interval)

    if args.trades:
        print(f"[INGEST:STUB] Would fetch TRADES for {args.pair} and write to data/bronze/trades …")
        fetch_trades_to_bronze(args.pair)


if __name__ == "__main__":
    main()
```



## app/preprocess\_cli.py

```python
"""CLI to transform Bronze → Silver (clean/resample/features) (STUB)."""
import argparse
from src.preprocessing.clean import clean_bronze
from src.preprocessing.resample import resample_candles
from src.features.pipeline import build_features


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    p.add_argument("--interval", type=int, default=1)
    return p.parse_args()


def main():
    args = parse_args()
    print(f"[PREPROCESS:STUB] Bronze → Silver for {args.pair} @ {args.interval}m …")
    clean_bronze(args.pair, args.interval)
    resample_candles(args.pair, args.interval)
    build_features(args.pair)


if __name__ == "__main__":
    main()
```



## app/label\_cli.py

```python
"""CLI to generate labels/targets for backtests (Gold) (STUB)."""
import argparse
from src.labeling.targets import make_labels


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    p.add_argument("--target", default="forward_return", choices=["forward_return", "triple_barrier"])
    return p.parse_args()


def main():
    args = parse_args()
    print(f"[LABEL:STUB] Generating {args.target} labels for {args.pair} → data/gold/labels …")
    make_labels(args.pair, args.target)


if __name__ == "__main__":
    main()
```



## app/backtest\_cli.py

```python
"""CLI to run backtests and walk-forward evaluation (STUB)."""
import argparse
from src.strategies.registry import REGISTRY
from src.backtesting.engine import run_backtest


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    p.add_argument("--strategies", nargs="+", default=["momentum"])
    return p.parse_args()


def main():
    args = parse_args()
    print(f"[BACKTEST:STUB] Running strategies {args.strategies} on {args.pair} …")
    for name in args.strategies:
        strat_cls = REGISTRY[name]
        strat = strat_cls()
        result = run_backtest(args.pair, strat)
        print(f"  - {name}: {result}")


if __name__ == "__main__":
    main()
```



## app/select\_strategy\_cli.py

```python
"""CLI to select best strategy per selection policy (STUB)."""
import argparse
from src.selection.selector import select_best_strategy


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    return p.parse_args()


def main():
    args = parse_args()
    best = select_best_strategy(args.pair)
    print(f"[SELECT:STUB] Selected strategy for {args.pair}: {best}")


if __name__ == "__main__":
    main()
```



## app/forward\_test\_cli.py

```python
"""CLI for forward (paper) testing the selected strategy (STUB)."""
import argparse
from src.forward_test.runner import run_forward_test


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    p.add_argument("--mode", default="paper", choices=["paper", "live"])
    return p.parse_args()


def main():
    args = parse_args()
    print(f"[FORWARD:STUB] Running forward test for {args.pair} in {args.mode} mode …")
    run_forward_test(args.pair, args.mode)


if __name__ == "__main__":
    main()
```



## app/trade\_cli.py

```python
"""CLI to run live trading (guarded) (STUB)."""
import argparse
from src.execution.router import run_live_trading


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--pair", default="XXBTZUSD")
    p.add_argument("--confirm", action="store_true", help="Acknowledge live trading risk")
    return p.parse_args()


def main():
    args = parse_args()
    if not args.confirm:
        print("[LIVE] Refusing to run without --confirm flag. Exiting.")
        return
    print(f"[LIVE:STUB] Would start live trading loop for {args.pair} … (disabled in stub)")
    run_live_trading(args.pair)


if __name__ == "__main__":
    main()
```



## src/**init**.py

```python
"""Root package for Kraken trading application (STUB)."""
```

### src/core/**init**.py

```python
"""Core utilities: configs, IO, logging, time utils (STUB)."""
```

### src/core/configs.py

```python
"""Config loader (STUB).
In real code: merge YAMLs (base+env), validate via pydantic.
"""
from dataclasses import dataclass

@dataclass
class AppConfig:
    data_dir: str = "data"
    fees_bps: float = 5.0


def load_config(env: str = "dev") -> AppConfig:
    print(f"[CONFIG:STUB] Loading config for env={env}")
    return AppConfig()
```

### src/core/io.py

```python
"""Unified IO helpers (STUB)."""
from pathlib import Path


def ensure_dir(p: str | Path) -> Path:
    path = Path(p)
    path.mkdir(parents=True, exist_ok=True)
    return path
```

### src/core/logging.py

```python
"""Structured logging setup (STUB)."""
import logging

def get_logger(name: str = "kraken") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        h.setFormatter(fmt)
        logger.addHandler(h)
    return logger
```

### src/core/timeutils.py

```python
"""Time helpers (STUB)."""
from datetime import timezone, datetime

def now_utc() -> datetime:
    return datetime.now(timezone.utc)
```



### src/ingestion/**init**.py

```python
"""Data ingestion from Kraken (STUB)."""
```

### src/ingestion/kraken\_client.py

```python
"""Thin Kraken client (STUB)."""
from typing import Any

class KrakenClient:
    def __init__(self):
        pass

    def get_ohlc(self, pair: str, interval: int) -> list[dict[str, Any]]:
        print(f"[CLIENT:STUB] get_ohlc(pair={pair}, interval={interval})")
        return []

    def get_trades(self, pair: str) -> list[dict[str, Any]]:
        print(f"[CLIENT:STUB] get_trades(pair={pair})")
        return []
```

### src/ingestion/ohlc\_fetcher.py

```python
"""OHLC fetcher landing to Bronze (STUB)."""
from .kraken_client import KrakenClient
from src.core.io import ensure_dir


def fetch_ohlc_to_bronze(pair: str, interval: int) -> None:
    ensure_dir("data/bronze/ohlc")
    client = KrakenClient()
    rows = client.get_ohlc(pair, interval)
    print(f"[BRONZE:STUB] Would write {len(rows)} OHLC rows → data/bronze/ohlc/{pair}/{interval}/…")
```

### src/ingestion/trades\_fetcher.py

```python
"""Trades fetcher landing to Bronze (STUB)."""
from .kraken_client import KrakenClient
from src.core.io import ensure_dir


def fetch_trades_to_bronze(pair: str) -> None:
    ensure_dir("data/bronze/trades")
    client = KrakenClient()
    rows = client.get_trades(pair)
    print(f"[BRONZE:STUB] Would write {len(rows)} trades → data/bronze/trades/{pair}/…")
```

### src/ingestion/landing\_validator.py

```python
"""Landing validators (STUB)."""

def validate_partition(path: str) -> bool:
    print(f"[VALIDATE:STUB] Checking landing at {path}")
    return True
```



### src/preprocessing/**init**.py

```python
"""Cleaning, resampling, validation (STUB)."""
```

### src/preprocessing/clean.py

```python
"""Bronze → cleaned Silver (STUB)."""
from src.core.io import ensure_dir

def clean_bronze(pair: str, interval: int) -> None:
    ensure_dir("data/silver/candles")
    print(f"[SILVER:STUB] Cleaning bronze for {pair}@{interval}m → data/silver/candles …")
```

### src/preprocessing/resample.py

```python
"""Resampling candles (STUB)."""

def resample_candles(pair: str, interval: int) -> None:
    print(f"[SILVER:STUB] Resampling {pair}@{interval}m → various frames …")
```

### src/preprocessing/validate.py

```python
"""Schema validation (STUB)."""

def validate_silver(pair: str) -> bool:
    print(f"[SILVER:STUB] Validating silver data for {pair}")
    return True
```



### src/features/**init**.py

```python
"""Feature engineering modules (STUB)."""
```

### src/features/technicals.py

```python
"""Technical indicators (STUB)."""

def rsi_stub(window: int = 14):
    print(f"[FEATURE:STUB] RSI(window={window})")
```

### src/features/price\_volume.py

```python
"""Price-volume features (STUB)."""

def vwap_stub():
    print("[FEATURE:STUB] VWAP()")
```

### src/features/volatility.py

```python
"""Volatility features (STUB)."""

def realized_vol_stub(lookback: int = 30):
    print(f"[FEATURE:STUB] realized_vol(lookback={lookback})")
```

### src/features/pipeline.py

```python
"""Feature pipeline orchestrator (STUB)."""
from .technicals import rsi_stub
from .price_volume import vwap_stub
from .volatility import realized_vol_stub


def build_features(pair: str) -> None:
    print(f"[FEATURE:STUB] Building features for {pair} …")
    rsi_stub()
    vwap_stub()
    realized_vol_stub()
```



### src/labeling/**init**.py

```python
"""Targets and time splits (STUB)."""
```

### src/labeling/targets.py

```python
"""Label generation (STUB)."""

def make_labels(pair: str, target: str):
    print(f"[GOLD:STUB] Making labels type={target} for {pair} → data/gold/labels …")
```

### src/labeling/splits.py

```python
"""Time-based splits (STUB)."""

def rolling_windows_stub():
    print("[SPLIT:STUB] Generating rolling windows …")
```



### src/strategies/**init**.py

```python
"""Trading strategies (STUB)."""
```

### src/strategies/base.py

```python
from typing import Protocol

class Strategy(Protocol):
    name: str
    def prepare(self, features, config: dict) -> None: ...
    def signal(self, features): ...
```

### src/strategies/registry.py

```python
from .momentum import Momentum
from .mean_reversion import MeanReversion
from .breakout import Breakout

REGISTRY = {
    "momentum": Momentum,
    "mean_reversion": MeanReversion,
    "breakout": Breakout,
}
```

### src/strategies/momentum.py

```python
class Momentum:
    name = "momentum"

    def prepare(self, features, config: dict) -> None:
        print("[STRAT:STUB] Preparing Momentum …")

    def signal(self, features):
        print("[STRAT:STUB] Generating Momentum signals …")
        return []
```

### src/strategies/mean\_reversion.py

```python
class MeanReversion:
    name = "mean_reversion"

    def prepare(self, features, config: dict) -> None:
        print("[STRAT:STUB] Preparing Mean Reversion …")

    def signal(self, features):
        print("[STRAT:STUB] Generating Mean Reversion signals …")
        return []
```

### src/strategies/breakout.py

```python
class Breakout:
    name = "breakout"

    def prepare(self, features, config: dict) -> None:
        print("[STRAT:STUB] Preparing Breakout …")

    def signal(self, features):
        print("[STRAT:STUB] Generating Breakout signals …")
        return []
```



### src/backtesting/**init**.py

```python
"""Backtesting utilities (STUB)."""
```

### src/backtesting/engine.py

```python
"""Backtest runner (STUB)."""

def run_backtest(pair: str, strategy) -> dict:
    strategy.prepare(features=None, config={})
    sig = strategy.signal(features=None)
    print(f"[BACKTEST:STUB] Backtested {strategy.name} on {pair} (signals={len(sig)})")
    return {"strategy": strategy.name, "pair": pair, "sharpe": 0.0, "cagr": 0.0}
```

### src/backtesting/portfolio.py

```python
"""Portfolio and PnL (STUB)."""

def mark_to_market_stub():
    print("[PORT:STUB] mark_to_market …")
```

### src/backtesting/metrics.py

```python
"""Metrics (STUB)."""

def sharpe_stub():
    print("[METRIC:STUB] Sharpe …")
```

### src/backtesting/walk\_forward.py

```python
"""Walk-forward evaluation (STUB)."""

def walk_forward_stub():
    print("[WALK:STUB] walk-forward …")
```



### src/selection/**init**.py

```python
"""Strategy selection (STUB)."""
```

### src/selection/scorer.py

```python
"""Composite scoring (STUB)."""

def score_strategy_stub(metrics: dict) -> float:
    print("[SELECT:STUB] scoring …")
    return 0.0
```

### src/selection/selector.py

```python
"""Pick the best strategy (STUB)."""

def select_best_strategy(pair: str) -> str:
    print(f"[SELECT:STUB] Selecting best strategy for {pair} …")
    return "momentum"
```



### src/execution/**init**.py

```python
"""Order routing and risk (STUB)."""
```

### src/execution/adapter.py

```python
"""Broker adapter interface (STUB)."""

class BrokerAdapter:
    def place_order(self, *args, **kwargs): ...
    def cancel_order(self, *args, **kwargs): ...
    def get_positions(self): ...
```

### src/execution/kraken\_adapter.py

```python
"""Kraken REST adapter (STUB)."""
from .adapter import BrokerAdapter

class KrakenAdapter(BrokerAdapter):
    def __init__(self):
        print("[EXEC:STUB] KrakenAdapter init")
```

### src/execution/risk.py

```python
"""Pre-trade risk checks (STUB)."""

def pre_trade_checks_stub():
    print("[RISK:STUB] checks …")
```

### src/execution/router.py

```python
"""Turn signals → orders (STUB)."""

def run_live_trading(pair: str) -> None:
    print(f"[ROUTER:STUB] Live trading loop for {pair} (disabled in stub)")
```



### src/forward\_test/**init**.py

```python
"""Forward testing components (STUB)."""
```

### src/forward\_test/paper\_broker.py

```python
"""Paper broker (STUB)."""

class PaperBroker:
    def place_order(self, *args, **kwargs):
        print("[PAPER:STUB] place_order …")
```

### src/forward\_test/runner.py

```python
"""Forward test runner (STUB)."""
from .paper_broker import PaperBroker


def run_forward_test(pair: str, mode: str) -> None:
    print(f"[FORWARD:STUB] run_forward_test(pair={pair}, mode={mode})")
    if mode == "paper":
        PaperBroker().place_order("BUY", 1)
```



### src/utils/**init**.py

```python
"""Misc helpers (STUB)."""
```

### src/utils/cache.py

```python
"""Local cache helpers (STUB)."""

def cache_stub():
    print("[CACHE:STUB] …")
```

### src/utils/rate\_limit.py

```python
"""Rate limiting (STUB)."""

def rate_limit_stub():
    print("[RATE:STUB] …")
```



## Optional: Makefile (quality of life)

```make
.PHONY: ingest preprocess label backtest select forward live

ingest:
	python -m app.ingest_cli --pair XXBTZUSD --interval 1

preprocess:
	python -m app.preprocess_cli --pair XXBTZUSD

label:
	python -m app.label_cli --pair XXBTZUSD --target triple_barrier

backtest:
	python -m app.backtest_cli --pair XXBTZUSD --strategies momentum mean_reversion breakout

select:
	python -m app.select_strategy_cli --pair XXBTZUSD

forward:
	python -m app.forward_test_cli --pair XXBTZUSD --mode paper

live:
	python -m app.trade_cli --pair XXBTZUSD --confirm
```
