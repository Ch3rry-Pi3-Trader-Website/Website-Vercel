from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict

import psycopg
from psycopg.types.json import Jsonb


def _database_url() -> str:
    raw = (os.getenv("PI3_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        raw = raw[1:-1].strip()
    return raw


def is_database_configured() -> bool:
    return bool(_database_url())


def _ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
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
              buy_hold_cagr DOUBLE PRECISION NOT NULL DEFAULT 0,
              log_sharpe DOUBLE PRECISION NOT NULL DEFAULT 0,
              log_sortino DOUBLE PRECISION NOT NULL DEFAULT 0,
              log_vol_ann DOUBLE PRECISION NOT NULL DEFAULT 0,
              risk JSONB NOT NULL DEFAULT '{}'::jsonb,
              source TEXT NOT NULL DEFAULT 'python-backend',
              created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
              UNIQUE(run_id, strategy, symbol, interval)
            )
            """
        )
        cur.execute(
            """
            ALTER TABLE backtest_metrics
            ADD COLUMN IF NOT EXISTS buy_hold_return DOUBLE PRECISION NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            ALTER TABLE backtest_metrics
            ADD COLUMN IF NOT EXISTS buy_hold_cagr DOUBLE PRECISION NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            ALTER TABLE backtest_metrics
            ADD COLUMN IF NOT EXISTS log_sharpe DOUBLE PRECISION NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            ALTER TABLE backtest_metrics
            ADD COLUMN IF NOT EXISTS log_sortino DOUBLE PRECISION NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            ALTER TABLE backtest_metrics
            ADD COLUMN IF NOT EXISTS log_vol_ann DOUBLE PRECISION NOT NULL DEFAULT 0
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_backtest_metrics_symbol_strategy_runat
            ON backtest_metrics(symbol, strategy, run_at DESC)
            """
        )


def persist_backtest_metric(
    metric: Dict[str, Any],
    run_id: str,
    run_at: datetime | None = None,
) -> tuple[bool, str]:
    db_url = _database_url()
    if not db_url:
        return False, "database_not_configured"

    run_at = run_at or datetime.now(timezone.utc)

    try:
        with psycopg.connect(db_url, autocommit=True) as conn:
            _ensure_schema(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO backtest_metrics (
                      run_id, run_at, strategy, symbol, interval, params, bars,
                      cagr, sharpe, max_drawdown, buy_hold_return, buy_hold_cagr,
                      log_sharpe, log_sortino, log_vol_ann, risk, source
                    )
                    VALUES (
                      %(run_id)s, %(run_at)s, %(strategy)s, %(symbol)s, %(interval)s, %(params)s,
                      %(bars)s, %(cagr)s, %(sharpe)s, %(max_drawdown)s, %(buy_hold_return)s, %(buy_hold_cagr)s,
                      %(log_sharpe)s, %(log_sortino)s, %(log_vol_ann)s, %(risk)s, %(source)s
                    )
                    ON CONFLICT (run_id, strategy, symbol, interval)
                    DO UPDATE SET
                      run_at = EXCLUDED.run_at,
                      params = EXCLUDED.params,
                      bars = EXCLUDED.bars,
                      cagr = EXCLUDED.cagr,
                      sharpe = EXCLUDED.sharpe,
                      max_drawdown = EXCLUDED.max_drawdown,
                      buy_hold_return = EXCLUDED.buy_hold_return,
                      buy_hold_cagr = EXCLUDED.buy_hold_cagr,
                      log_sharpe = EXCLUDED.log_sharpe,
                      log_sortino = EXCLUDED.log_sortino,
                      log_vol_ann = EXCLUDED.log_vol_ann,
                      risk = EXCLUDED.risk,
                      source = EXCLUDED.source
                    """,
                    {
                        "run_id": run_id,
                        "run_at": run_at,
                        "strategy": str(metric.get("strategy", "")),
                        "symbol": str(metric.get("symbol", "")),
                        "interval": str(metric.get("interval", "")),
                        "params": Jsonb(metric.get("params", {}) or {}),
                        "bars": int(metric.get("bars", 0)),
                        "cagr": float(metric.get("cagr", 0.0)),
                        "sharpe": float(metric.get("sharpe", 0.0)),
                        "max_drawdown": float(metric.get("max_drawdown", 0.0)),
                        "buy_hold_return": float(metric.get("buy_hold_return", 0.0)),
                        "buy_hold_cagr": float(metric.get("buy_hold_cagr", 0.0)),
                        "log_sharpe": float(metric.get("log_sharpe", 0.0)),
                        "log_sortino": float(metric.get("log_sortino", 0.0)),
                        "log_vol_ann": float(metric.get("log_vol_ann", 0.0)),
                        "risk": Jsonb(metric.get("risk", {}) or {}),
                        "source": "python-backend",
                    },
                )
        return True, "ok"
    except Exception as exc:
        return False, f"database_write_failed:{exc}"
