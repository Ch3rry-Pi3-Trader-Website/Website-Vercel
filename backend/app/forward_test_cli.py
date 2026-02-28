"""CLI: run forward paper test using selected strategy."""
from __future__ import annotations

from pathlib import Path

import click

from src.core.configs import load_config, resolve_path
from src.forward_test.runner import run_forward_test


@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--symbol", default=None)
@click.option("--interval", default=None)
def main(env_name, symbol, interval) -> None:
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    symbol = (symbol or cfg.market.default_symbol).upper()
    interval = interval or cfg.market.interval

    silver_root = resolve_path(root, f"{cfg.data.silver_dir}/candles")
    selection_file = (
        resolve_path(root, f"{cfg.data.gold_dir}/selection") / symbol / interval / "current_strategy.json"
    )
    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/forward_tests")

    try:
        out_path = run_forward_test(
            silver_root=silver_root,
            selection_file=selection_file,
            out_dir=out_dir,
            taker_bps=cfg.fees.taker_bps,
            max_position=cfg.risk.max_position,
            flip_cooldown_bars=cfg.risk.flip_cooldown_bars,
            daily_loss_cap=cfg.risk.daily_loss_cap,
        )
        click.echo(f"[FORWARD] Paper equity saved -> {out_path}")
    except Exception as exc:
        click.echo(f"[FORWARD] Failed: {exc}")


if __name__ == "__main__":
    main()
