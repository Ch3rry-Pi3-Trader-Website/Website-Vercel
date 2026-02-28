"""CLI for live trading guardrail."""
from __future__ import annotations

import click

from src.execution.router import run_live_trading


@click.command()
@click.option("--symbol", default="SPY")
@click.option("--confirm", is_flag=True, help="Acknowledge live trading risk.")
def main(symbol: str, confirm: bool) -> None:
    if not confirm:
        click.echo("[LIVE] Refusing to run without --confirm.")
        return
    try:
        run_live_trading(symbol)
    except Exception as exc:
        click.echo(f"[LIVE] Disabled: {exc}")


if __name__ == "__main__":
    main()
