from __future__ import annotations

from pathlib import Path
import json
from datetime import datetime, timezone

import pandas as pd


WIKI_SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def _sanitize_symbol(sym: str) -> str:
    # Yahoo Finance uses BRK-B / BF-B style instead of BRK.B / BF.B
    return sym.strip().upper().replace(".", "-")


def load_sp500_symbols_from_web() -> list[str]:
    tables = pd.read_html(WIKI_SP500_URL)
    if not tables:
        raise RuntimeError("No tables found when loading S&P 500 symbols.")

    table = tables[0]
    if "Symbol" not in table.columns:
        raise RuntimeError("S&P 500 symbol column not found.")

    symbols = sorted({_sanitize_symbol(s) for s in table["Symbol"].astype(str).tolist() if s})
    if not symbols:
        raise RuntimeError("No S&P 500 symbols parsed from source.")
    return symbols


def load_cached_symbols(cache_path: Path) -> list[str]:
    if not cache_path.exists():
        return []
    with cache_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return [str(s).upper() for s in payload.get("symbols", [])]


def write_cached_symbols(cache_path: Path, symbols: list[str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": WIKI_SP500_URL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "count": len(symbols),
        "symbols": symbols,
    }
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_sp500_symbols(cache_path: Path, refresh_cache: bool = False) -> list[str]:
    if not refresh_cache:
        cached = load_cached_symbols(cache_path)
        if cached:
            return cached

    symbols = load_sp500_symbols_from_web()
    write_cached_symbols(cache_path, symbols)
    return symbols
