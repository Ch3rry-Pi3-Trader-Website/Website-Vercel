"""CLI: fetch equities OHLCV and land into Bronze."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import click

from src.core.configs import load_config, resolve_path
from src.ingestion.ohlc_fetcher import fetch_ohlcv_to_bronze
from src.ingestion.sp500_universe import load_sp500_symbols


@click.command()
@click.option("--env", "env_name", default=None, help="Config environment (dev/prod).")
@click.option("--symbol", default=None, help="Single symbol override (for example: AAPL).")
@click.option("--interval", default=None, help="Bar interval override (for example: 1d).")
@click.option("--lookback-days", type=int, default=None, help="Trailing lookback window.")
@click.option("--max-symbols", type=int, default=None, help="Limit universe size.")
@click.option("--refresh-universe-cache", is_flag=True, default=False)
def main(
    env_name: str | None,
    symbol: str | None,
    interval: str | None,
    lookback_days: int | None,
    max_symbols: int | None,
    refresh_universe_cache: bool,
) -> None:
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    bar_interval = interval or cfg.market.interval
    lookback = lookback_days if lookback_days is not None else cfg.market.lookback_days

    if symbol:
        symbols = [symbol.strip().upper()]
    else:
        cache_path = resolve_path(root, cfg.market.universe_cache_file)
        try:
            symbols = load_sp500_symbols(cache_path, refresh_cache=refresh_universe_cache)
        except Exception:
            symbols = cfg.market.fallback_symbols

    if max_symbols is not None and max_symbols > 0:
        symbols = symbols[:max_symbols]
    if not symbols:
        click.echo("[INGEST] No symbols selected.")
        return

    today_utc = datetime.now(timezone.utc).date()
    start_date = today_utc - timedelta(days=lookback)
    end_date_exclusive = today_utc + timedelta(days=1)

    bronze_ohlcv = resolve_path(root, f"{cfg.data.bronze_dir}/ohlcv")
    result = fetch_ohlcv_to_bronze(
        symbols=symbols,
        start_date=start_date,
        end_date_exclusive=end_date_exclusive,
        interval=bar_interval,
        out_base=bronze_ohlcv,
        run_date=today_utc,
        batch_size=cfg.ingestion.batch_size,
        auto_adjust=cfg.ingestion.auto_adjust,
        pause_seconds=cfg.ingestion.pause_seconds,
        max_retries=cfg.ingestion.max_retries,
    )
    click.echo(
        f"[INGEST] Universe={len(symbols)} interval={bar_interval} start={start_date} end_exclusive={end_date_exclusive}"
    )
    click.echo(
        "[INGEST] Wrote symbols={} rows={} failed_or_empty={}".format(
            result["symbols_written"], result["rows_written"], result["symbols_failed_or_empty"]
        )
    )


if __name__ == "__main__":
    main()
