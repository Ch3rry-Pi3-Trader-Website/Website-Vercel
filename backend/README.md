# PI3 Investor Backend

Python backend reproducing the original guide-driven pipeline, adapted for equities:

- Config-first environments (`base.yaml` + `dev/prod` overlays + CLI overrides)
- Bronze -> Silver -> Gold data flow
- Labels, strategies, backtests, persistence, selection, forward paper test
- Risk/rules layer applied to backtest and paper run
- S&P 500 ingestion with default trailing 30-day persistence

## Windows quickstart (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

## End-to-end commands

```powershell
cd backend

# 1) Ingest trailing month (defaults to S&P 500 universe)
python -m app.ingest_cli --env dev

# 2) Bronze -> Silver for one symbol
python -m app.preprocess_cli --env dev --symbol SPY

# 3) Backtest strategies (persist artefacts)
python -m app.backtest_cli --env dev --symbol SPY --strategy momentum
python -m app.backtest_cli --env dev --symbol SPY --strategy mean_reversion

# 4) Select best strategy snapshot
python -m app.select_strategy_cli --env dev --symbol SPY

# 5) Forward paper test using selected strategy
python -m app.forward_test_cli --env dev --symbol SPY
```

## Generate richer rankings

For stronger strategy ranking output, pull a longer window and run backtests across many symbols.

If run on February 28, 2026:

- `--lookback-days 365` covers roughly February 28, 2025 -> March 1, 2026 (end exclusive).

```powershell
cd backend

# 1) Pull longer history
python -m app.ingest_cli --env prod --lookback-days 365 --max-symbols 40

# 2) Run preprocess + momentum + mean_reversion over all ingested symbols
powershell -ExecutionPolicy Bypass -File .\scripts\run_universe_backtests.ps1 -EnvName prod -Interval 1d -MaxSymbols 40
```

## Production persistence (Postgres)

`backtest_cli` now writes metrics to Postgres when `PI3_DATABASE_URL` (or `DATABASE_URL`) is set.

```powershell
$env:PI3_DATABASE_URL="postgres://USER:PASSWORD@HOST:5432/DBNAME"
python -m app.backtest_cli --env prod --symbol SPY --strategy momentum
```

Notes:

- Table is auto-created on first write: `backtest_metrics`.
- SQL reference is available at `sql/001_backtest_metrics.sql`.
- Use the same database for frontend Vercel reads.

## Data persistence

- Bronze OHLCV:
  `data/bronze/ohlcv/symbol=<TICKER>/interval=<INTERVAL>/dt=<YYYY-MM-DD>/`
- Silver candles:
  `data/silver/candles/symbol=<TICKER>/interval=<INTERVAL>/dt=<YYYY-MM-DD>/`
- Gold backtest outputs:
  `data/gold/signals/<strategy>/<symbol>/<interval>/dt=<YYYY-MM-DD>/`
- Gold selection:
  `data/gold/selection/<symbol>/<interval>/current_strategy.json`
- Gold forward tests:
  `data/gold/forward_tests/`
