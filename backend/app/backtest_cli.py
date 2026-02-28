"""CLI: run strategy backtest on latest Silver candles."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import click
import pandas as pd

from src.backtesting.engine import run_backtest
from src.backtesting.metrics import cagr, max_drawdown, sharpe
from src.backtesting.persist import timestamp_utc_str, write_metrics_json, write_timeseries_csv
from src.core.configs import load_config, load_strategy_params, resolve_path
from src.core.io import latest_partition, read_parquet_many
from src.core.logging import setup_logging
from src.core.timeutils import interval_to_minutes
from src.persistence.metrics_store import is_database_configured, persist_backtest_metric
from src.strategies.registry import REGISTRY


@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--symbol", default=None, help="Symbol override.")
@click.option("--interval", default=None, help="Interval override.")
@click.option("--strategy", type=click.Choice(["momentum", "mean_reversion", "breakout"]), default="momentum")
@click.option("--fast", type=int, default=None, help="EMA fast")
@click.option("--slow", type=int, default=None, help="EMA slow")
@click.option("--bb-window", type=int, default=None, help="Bollinger window")
@click.option("--bb-k", type=float, default=None, help="Bollinger k")
@click.option("--max-position", type=float, default=None, help="Override risk.max_position")
@click.option("--flip-cooldown", type=int, default=None, help="Override risk.flip_cooldown_bars")
@click.option("--daily-loss-cap", type=float, default=None, help="Override risk.daily_loss_cap")
@click.option("--log-level", default="INFO")
def main(
    env_name,
    symbol,
    interval,
    strategy,
    fast,
    slow,
    bb_window,
    bb_k,
    max_position,
    flip_cooldown,
    daily_loss_cap,
    log_level,
) -> None:
    setup_logging(log_level)
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    symbol = (symbol or cfg.market.default_symbol).upper()
    interval = interval or cfg.market.interval

    defaults = load_strategy_params(root, strategy)
    if strategy == "momentum":
        params = {
            "fast": fast if fast is not None else int(defaults.get("fast", 20)),
            "slow": slow if slow is not None else int(defaults.get("slow", 50)),
        }
    elif strategy == "mean_reversion":
        params = {
            "window": bb_window if bb_window is not None else int(defaults.get("window", 20)),
            "k": bb_k if bb_k is not None else float(defaults.get("k", 2.0)),
        }
    else:
        params = {"window": int(defaults.get("window", 20))}

    max_position = cfg.risk.max_position if max_position is None else max_position
    flip_cooldown = cfg.risk.flip_cooldown_bars if flip_cooldown is None else flip_cooldown
    daily_loss_cap = cfg.risk.daily_loss_cap if daily_loss_cap is None else daily_loss_cap

    silver = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    part = latest_partition(silver, symbol, interval)
    if part is None:
        click.echo(f"[BACKTEST] No Silver partition at {silver}/symbol={symbol}/interval={interval}")
        return

    files = list(part.glob("*.parquet"))
    df = read_parquet_many(files)
    if df.empty:
        click.echo("[BACKTEST] Silver empty.")
        return

    Strat = REGISTRY[strategy]
    strat = Strat(**params) if params else Strat()
    strat.prepare(df)
    sig = strat.signal(df)

    interval_min = interval_to_minutes(interval)
    res = run_backtest(
        df=df,
        signal=sig,
        interval_min=interval_min,
        taker_bps=cfg.fees.taker_bps,
        max_position=max_position,
        flip_cooldown_bars=flip_cooldown,
        daily_loss_cap=daily_loss_cap,
    )
    r, eq = res["returns"], res["equity"]
    buy_hold_return = float(df["close"].iloc[-1] / df["close"].iloc[0] - 1.0)

    m = {
        "strategy": strategy,
        "symbol": symbol,
        "interval": interval,
        "params": params,
        "bars": int(len(df)),
        "cagr": float(cagr(eq, interval_min)),
        "sharpe": float(sharpe(r, interval_min)),
        "max_drawdown": float(max_drawdown(eq)),
        "buy_hold_return": buy_hold_return,
        "risk": {
            "max_position": max_position,
            "flip_cooldown_bars": flip_cooldown,
            "daily_loss_cap": daily_loss_cap,
        },
    }
    click.echo(
        f"[BACKTEST] {strategy} | Bars={m['bars']} | CAGR={m['cagr']:.2%} | "
        f"Sharpe={m['sharpe']:.2f} | MaxDD={m['max_drawdown']:.2%} | "
        f"BuyHold={m['buy_hold_return']:.2%}"
    )

    dt_str = pd.to_datetime(df["timestamp"].iloc[-1], utc=True).date().isoformat()
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/signals") / strategy / symbol / interval / f"dt={dt_str}"
    ts = timestamp_utc_str()
    write_metrics_json(m, out_dir, filename=f"metrics-{ts}.json")
    write_timeseries_csv(eq.rename("equity"), out_dir, filename=f"equity-{ts}.csv")
    write_timeseries_csv(r.rename("returns"), out_dir, filename=f"returns-{ts}.csv")
    click.echo(f"[BACKTEST] Saved artefacts -> {out_dir}")

    if is_database_configured():
        ok, status = persist_backtest_metric(
            metric=m,
            run_id=ts,
            run_at=datetime.now(timezone.utc),
        )
        if ok:
            click.echo("[BACKTEST] Persisted metrics -> postgres.backtest_metrics")
        else:
            click.echo(f"[BACKTEST] Postgres persistence skipped/failed: {status}")


if __name__ == "__main__":
    main()
