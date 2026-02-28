"""Batch preprocess + backtest runner across all ingested symbols."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run_module(backend_root: Path, module: str, args: list[str]) -> bool:
    cmd = [sys.executable, "-m", module, *args]
    completed = subprocess.run(cmd, cwd=backend_root)
    return completed.returncode == 0


def _process_symbol(
    backend_root: Path,
    env_name: str,
    interval: str,
    symbol: str,
    include_breakout: bool,
) -> dict[str, Any]:
    errors: list[str] = []

    ok = _run_module(
        backend_root,
        "app.preprocess_cli",
        ["--env", env_name, "--symbol", symbol, "--interval", interval],
    )
    if not ok:
        return {"symbol": symbol, "ok": False, "errors": ["preprocess_failed"]}

    for strategy in ["momentum", "mean_reversion"]:
        ok = _run_module(
            backend_root,
            "app.backtest_cli",
            [
                "--env",
                env_name,
                "--symbol",
                symbol,
                "--interval",
                interval,
                "--strategy",
                strategy,
            ],
        )
        if not ok:
            errors.append(f"{strategy}_failed")

    if include_breakout:
        ok = _run_module(
            backend_root,
            "app.backtest_cli",
            [
                "--env",
                env_name,
                "--symbol",
                symbol,
                "--interval",
                interval,
                "--strategy",
                "breakout",
            ],
        )
        if not ok:
            errors.append("breakout_failed")

    return {"symbol": symbol, "ok": len(errors) == 0, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run preprocess + strategy backtests for symbols found in Bronze data."
    )
    parser.add_argument("--env", dest="env_name", default="prod")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1, help="Number of symbols to process in parallel.")
    parser.add_argument("--include-breakout", action="store_true")
    args = parser.parse_args()

    backend_root = Path(__file__).resolve().parents[1]
    bronze_root = backend_root / "data" / "bronze" / "ohlcv"
    if not bronze_root.exists():
        print(f"[BATCH] Bronze directory not found: {bronze_root}", file=sys.stderr)
        return 1

    symbol_dirs = sorted([p for p in bronze_root.glob("symbol=*") if p.is_dir()], key=lambda p: p.name)
    symbols = [p.name[7:] for p in symbol_dirs if p.name.startswith("symbol=")]
    if args.max_symbols > 0:
        symbols = symbols[: args.max_symbols]
    if not symbols:
        print(f"[BATCH] No symbols found under {bronze_root}", file=sys.stderr)
        return 1

    print(f"[BATCH] Symbols to process: {len(symbols)}")
    workers = max(1, int(args.workers))
    print(f"[BATCH] Env={args.env_name} Interval={args.interval} Workers={workers}")

    failures: list[dict[str, Any]] = []
    if workers == 1:
        for symbol in symbols:
            print("")
            print(f"[BATCH] Processing {symbol}")
            result = _process_symbol(
                backend_root=backend_root,
                env_name=args.env_name,
                interval=args.interval,
                symbol=symbol,
                include_breakout=args.include_breakout,
            )
            if not result["ok"]:
                failures.append(result)
                print(f"[BATCH] Failures for {symbol}: {', '.join(result['errors'])}", file=sys.stderr)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            fut_map = {
                pool.submit(
                    _process_symbol,
                    backend_root,
                    args.env_name,
                    args.interval,
                    symbol,
                    args.include_breakout,
                ): symbol
                for symbol in symbols
            }
            for fut in as_completed(fut_map):
                symbol = fut_map[fut]
                print("")
                print(f"[BATCH] Completed {symbol}")
                try:
                    result = fut.result()
                except Exception as exc:
                    result = {"symbol": symbol, "ok": False, "errors": [f"exception:{exc}"]}
                if not result["ok"]:
                    failures.append(result)
                    print(f"[BATCH] Failures for {symbol}: {', '.join(result['errors'])}", file=sys.stderr)

    print("")
    print(f"[BATCH] Completed. failures={len(failures)}")
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
