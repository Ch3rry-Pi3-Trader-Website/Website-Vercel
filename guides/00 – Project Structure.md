
# 00 – Project Structure

This document describes the initial directory structure of the **crypto trading bot** project.
The bot is designed to ingest market data from Kraken, preprocess it into feature-rich datasets, generate trading signals through multiple strategies, backtest them, and finally deploy selected strategies into forward testing or live trading.

A well-organised project layout ensures:

* Clear separation of concerns (ingestion, preprocessing, strategies, execution).
* Smooth transitions between the **Bronze → Silver → Gold** data layers.
* Reproducibility and maintainability across development, testing, and production.



## Project Tree

```text
strategybot/
├── app/
│   ├── ingest_cli.py              # CLI: pull OHLC/trades, land to Bronze
│   ├── preprocess_cli.py          # CLI: Bronze -> Silver (clean/feature)
│   ├── label_cli.py               # CLI: generate labels/targets for backtests
│   ├── backtest_cli.py            # CLI: run backtests & walk-forward
│   ├── select_strategy_cli.py     # CLI: choose best strategy by policy
│   ├── forward_test_cli.py        # CLI: paper/live forward test runner
│   └── trade_cli.py               # CLI: live trading loop (prod switch guard)
│
├── config/
│   ├── base.yaml                  # Defaults shared by all envs
│   ├── dev.yaml                   # Dev overrides
│   ├── prod.yaml                  # Prod overrides (never secrets)
│   ├── connections/
│   │   └── kraken.yaml            # REST/WebSocket endpoints, rate limits
│   ├── features/
│   │   └── pipeline.yaml          # Feature pipeline steps & windows
│   ├── strategies/
│   │   ├── momentum.yaml
│   │   ├── mean_reversion.yaml
│   │   └── breakout.yaml
│   └── selection_policy.yaml      # How to pick “best” strategy (metrics, decay)
│
├── data/
│   ├── bronze/                    # Raw immutable landings
│   │   ├── ohlc/                  # e.g., pair=XXBTZUSD, interval=1m
│   │   └── trades/
│   ├── silver/                    # Cleaned, typed, gap-handled, features
│   │   ├── candles/               # resampled & validated
│   │   └── features/              # engineered features store
│   └── gold/                      # Ready-to-use signal/labels
│       ├── labels/                # targets for backtests
│       └── signals/               # strategy signals, weights, risk
│
├── docs/
│   └── architecture.md
│
├── flows/                         # Orchestration (Prefect/Airflow)
│   ├── daily_ingest_flow.py
│   ├── feature_build_flow.py
│   ├── nightly_backtest_flow.py
│   └── forward_test_flow.py
│
├── notebooks/                     # Exploratory work
│
├── scripts/                       # One-off utilities, migrations, seeders
│
├── src/
│   ├── core/
│   │   ├── configs.py             # Load/merge base+env YAML, pydantic models
│   │   ├── io.py                  # Uniform read/write (parquet/csv/json)
│   │   ├── timeutils.py
│   │   └── logging.py             # Structured logging setup
│   │
│   ├── ingestion/
│   │   ├── kraken_client.py       # Thin REST/WebSocket client (retry, backoff)
│   │   ├── ohlc_fetcher.py        # Pull OHLC -> bronze/ohlc/…
│   │   ├── trades_fetcher.py      # Pull trades -> bronze/trades/…
│   │   └── landing_validator.py   # Schema/dup checks, partitioning
│   │
│   ├── preprocessing/
│   │   ├── clean.py               # Typing, timezone, dedup, gap fill
│   │   ├── resample.py            # 1m→5m→1h aggregation
│   │   └── validate.py            # Great Expectations/ pandera schemas
│   │
│   ├── features/
│   │   ├── technicals.py          # RSI, MACD, BB, ATR, OBV, etc.
│   │   ├── price_volume.py        # price–volume interactions, VPT, VWAP
│   │   ├── volatility.py          # realized vol, range measures
│   │   └── pipeline.py            # Orchestrates feature steps from YAML
│   │
│   ├── labeling/
│   │   ├── targets.py             # forward returns, triple-barrier, side
│   │   └── splits.py              # time-series CV, walk-forward windows
│   │
│   ├── strategies/
│   │   ├── base.py                # Strategy interface (fit/prepare/signal)
│   │   ├── registry.py            # Register & load strategies by name
│   │   ├── momentum.py
│   │   ├── mean_reversion.py
│   │   └── breakout.py
│   │
│   ├── backtesting/
│   │   ├── engine.py              # Event/loop; slippage, fees, latency
│   │   ├── portfolio.py           # Position sizing, cash, PnL
│   │   ├── metrics.py             # CAGR, Sharpe, Sortino, MaxDD, hit-rate
│   │   └── walk_forward.py        # Train/validate by rolling windows
│   │
│   ├── selection/
│   │   ├── scorer.py              # Composite score with metric weights/decay
│   │   └── selector.py            # Pick best per market/regime & persist
│   │
│   ├── execution/
│   │   ├── adapter.py             # Broker interface (place/cancel/query)
│   │   ├── kraken_adapter.py      # Kraken REST trading adapter
│   │   ├── risk.py                # Pre-trade checks, caps, circuit breakers
│   │   └── router.py              # Turn signals -> orders (throttled)
│   │
│   ├── forward_test/
│   │   ├── paper_broker.py        # Paper trade adapter with same interface
│   │   └── runner.py              # Run selected strategy in paper/live
│   │
│   └── utils/
│       ├── cache.py               # local caches, memoisation
│       └── rate_limit.py          # global/per-endpoint rate limiting
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── .env.example                   # KRAKEN_KEY=... (example only)
├── pyproject.toml                 # project deps & tools
├── README.md
└── Makefile                       # make ingest/backtest/forward/live
```



## Directory Overview

* **`app/`** – Command-line entrypoints for each stage: ingest, preprocess, label, backtest, select, forward test, and live trade.
* **`config/`** – Centralised configuration in YAML: environment defaults, feature pipelines, strategies, and selection policies.
* **`data/`** – Structured in **Bronze (raw)** → **Silver (cleaned/features)** → **Gold (labels/signals)** layers.
* **`docs/`** – Markdown documentation including architecture diagrams and guides.
* **`flows/`** – Orchestration scripts for scheduling (e.g., Prefect or Airflow).
* **`notebooks/`** – For exploration, prototyping strategies, and data analysis.
* **`scripts/`** – One-off helper utilities or migrations.
* **`src/`** – Main Python source code, broken down by function (core utilities, ingestion, preprocessing, feature engineering, strategies, backtesting, selection, execution, forward testing, utilities).
* **`tests/`** – Unit and integration tests to ensure code quality and reliability.
* **Project root files** – Environment variables, dependency definitions, project README, and Makefile shortcuts.
