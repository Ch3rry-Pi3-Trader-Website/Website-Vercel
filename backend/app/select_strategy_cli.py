"""CLI: choose best strategy by selection policy and persist the decision."""
from __future__ import annotations

import json
from pathlib import Path

import click

from src.core.configs import load_config, resolve_path
from src.selection.selector import select_best_strategy


@click.command()
@click.option("--env", "env_name", default=None)
@click.option("--symbol", default=None)
@click.option("--interval", default=None)
def main(env_name, symbol, interval) -> None:
    root = Path.cwd()
    cfg = load_config(env=env_name, root=root)

    symbol = (symbol or cfg.market.default_symbol).upper()
    interval = interval or cfg.market.interval

    signals_root = resolve_path(root, f"{cfg.data.gold_dir}/signals")
    policy_file = resolve_path(root, cfg.selection.policy_file)

    best = select_best_strategy(signals_root, policy_file, symbol, interval)
    if not best:
        click.echo("[SELECT] No candidates found.")
        return

    out_dir = resolve_path(root, f"{cfg.data.gold_dir}/selection") / symbol / interval
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "current_strategy.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(best, f, indent=2)

    click.echo(f"[SELECT] Selected: {best.get('strategy')} with score={best.get('_score'):.4f}")
    click.echo(f"[SELECT] Saved -> {out_path}")


if __name__ == "__main__":
    main()
