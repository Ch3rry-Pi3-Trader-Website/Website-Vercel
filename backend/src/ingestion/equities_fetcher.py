from __future__ import annotations

from datetime import date
from pathlib import Path
from time import sleep

import pandas as pd
import yfinance as yf

from src.core.io import write_parquet_partition


def _chunk(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _normalize_symbol_frame(df: pd.DataFrame, symbol: str, interval: str) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out = out.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    out = out.reset_index()

    # yfinance index is usually "Date" or "Datetime".
    ts_col = "Date" if "Date" in out.columns else "Datetime"
    out = out.rename(columns={ts_col: "timestamp"})
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
    out["symbol"] = symbol
    out["interval"] = interval

    keep_cols = ["timestamp", "open", "high", "low", "close", "adj_close", "volume", "symbol", "interval"]
    out = out[[c for c in keep_cols if c in out.columns]]
    out = out.dropna(subset=["timestamp", "open", "high", "low", "close"]).sort_values("timestamp")
    out = out.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return out


def _download_batch(
    symbols: list[str],
    start_date: date,
    end_date_exclusive: date,
    interval: str,
    auto_adjust: bool,
) -> dict[str, pd.DataFrame]:
    if not symbols:
        return {}

    raw = yf.download(
        tickers=symbols,
        start=start_date.isoformat(),
        end=end_date_exclusive.isoformat(),
        interval=interval,
        auto_adjust=auto_adjust,
        group_by="ticker",
        progress=False,
        threads=False,
    )

    if raw.empty:
        return {sym: pd.DataFrame() for sym in symbols}

    frames: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for sym in symbols:
            if sym in raw.columns.get_level_values(0):
                frames[sym] = raw[sym].copy()
            else:
                frames[sym] = pd.DataFrame()
    else:
        # single symbol path
        frames[symbols[0]] = raw.copy()

    return frames


def fetch_and_persist_ohlcv(
    symbols: list[str],
    start_date: date,
    end_date_exclusive: date,
    interval: str,
    out_base: Path,
    run_date: date,
    batch_size: int = 50,
    auto_adjust: bool = True,
    pause_seconds: float = 0.1,
    max_retries: int = 2,
) -> dict[str, int]:
    rows_written = 0
    symbols_written = 0
    failed = 0

    for batch in _chunk(symbols, max(1, batch_size)):
        attempts = 0
        frames: dict[str, pd.DataFrame] = {}
        while attempts <= max_retries:
            try:
                frames = _download_batch(
                    symbols=batch,
                    start_date=start_date,
                    end_date_exclusive=end_date_exclusive,
                    interval=interval,
                    auto_adjust=auto_adjust,
                )
                break
            except Exception:
                attempts += 1
                if attempts > max_retries:
                    frames = {sym: pd.DataFrame() for sym in batch}
                    break
                sleep(0.4 * attempts)

        for sym in batch:
            normalized = _normalize_symbol_frame(frames.get(sym, pd.DataFrame()), sym, interval)
            if normalized.empty:
                failed += 1
                continue

            write_parquet_partition(
                df=normalized,
                out_base=out_base,
                symbol=sym,
                interval=interval,
                dt_str=run_date.isoformat(),
                prefix="ohlcv",
            )
            symbols_written += 1
            rows_written += int(len(normalized))

        if pause_seconds > 0:
            sleep(pause_seconds)

    return {
        "symbols_requested": len(symbols),
        "symbols_written": symbols_written,
        "rows_written": rows_written,
        "symbols_failed_or_empty": failed,
    }
