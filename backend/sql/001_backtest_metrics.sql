CREATE TABLE IF NOT EXISTS backtest_metrics (
  id BIGSERIAL PRIMARY KEY,
  run_id TEXT NOT NULL,
  run_at TIMESTAMPTZ NOT NULL,
  strategy TEXT NOT NULL,
  symbol TEXT NOT NULL,
  interval TEXT NOT NULL,
  params JSONB NOT NULL DEFAULT '{}'::jsonb,
  bars INTEGER NOT NULL,
  cagr DOUBLE PRECISION NOT NULL,
  sharpe DOUBLE PRECISION NOT NULL,
  max_drawdown DOUBLE PRECISION NOT NULL,
  buy_hold_return DOUBLE PRECISION NOT NULL DEFAULT 0,
  risk JSONB NOT NULL DEFAULT '{}'::jsonb,
  source TEXT NOT NULL DEFAULT 'python-backend',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(run_id, strategy, symbol, interval)
);

ALTER TABLE backtest_metrics
ADD COLUMN IF NOT EXISTS buy_hold_return DOUBLE PRECISION NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_backtest_metrics_symbol_strategy_runat
ON backtest_metrics(symbol, strategy, run_at DESC);
