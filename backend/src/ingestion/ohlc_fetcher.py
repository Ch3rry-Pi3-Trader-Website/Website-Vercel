from __future__ import annotations

from datetime import date
from pathlib import Path

from src.ingestion.equities_fetcher import fetch_and_persist_ohlcv


def fetch_ohlcv_to_bronze(
    symbols: list[str],
    start_date: date,
    end_date_exclusive: date,
    interval: str,
    out_base: Path,
    run_date: date,
    batch_size: int,
    auto_adjust: bool,
    pause_seconds: float,
    max_retries: int,
) -> dict[str, int]:
    return fetch_and_persist_ohlcv(
        symbols=symbols,
        start_date=start_date,
        end_date_exclusive=end_date_exclusive,
        interval=interval,
        out_base=out_base,
        run_date=run_date,
        batch_size=batch_size,
        auto_adjust=auto_adjust,
        pause_seconds=pause_seconds,
        max_retries=max_retries,
    )
