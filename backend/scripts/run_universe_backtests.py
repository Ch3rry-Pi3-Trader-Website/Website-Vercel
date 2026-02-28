"""Batch preprocess + backtest runner across all ingested symbols."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_module(backend_root: Path, module: str, args: list[str]) -> bool:
    cmd = [sys.executable, "-m", module, *args]
    completed = subprocess.run(cmd, cwd=backend_root)
    return completed.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run preprocess + strategy backtests for symbols found in Bronze data."
    )
    parser.add_argument("--env", dest="env_name", default="prod")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--max-symbols", type=int, default=0)
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
    print(f"[BATCH] Env={args.env_name} Interval={args.interval}")

    for symbol in symbols:
        print("")
        print(f"[BATCH] Processing {symbol}")

        ok = _run_module(
            backend_root,
            "app.preprocess_cli",
            ["--env", args.env_name, "--symbol", symbol, "--interval", args.interval],
        )
        if not ok:
            print(f"[BATCH] Preprocess failed for {symbol}. Skipping backtests.", file=sys.stderr)
            continue

        for strategy in ["momentum", "mean_reversion"]:
            ok = _run_module(
                backend_root,
                "app.backtest_cli",
                [
                    "--env",
                    args.env_name,
                    "--symbol",
                    symbol,
                    "--interval",
                    args.interval,
                    "--strategy",
                    strategy,
                ],
            )
            if not ok:
                print(f"[BATCH] {strategy} failed for {symbol}.", file=sys.stderr)

        if args.include_breakout:
            ok = _run_module(
                backend_root,
                "app.backtest_cli",
                [
                    "--env",
                    args.env_name,
                    "--symbol",
                    symbol,
                    "--interval",
                    args.interval,
                    "--strategy",
                    "breakout",
                ],
            )
            if not ok:
                print(f"[BATCH] breakout failed for {symbol}.", file=sys.stderr)

    print("")
    print("[BATCH] Completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
