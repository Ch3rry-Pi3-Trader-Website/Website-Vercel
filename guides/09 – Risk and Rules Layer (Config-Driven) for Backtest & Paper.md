# 09 – Risk/Rules Layer (Config-Driven) for Backtest & Paper

This step adds:

* **Config-driven** risk/rule settings (no magic constants).
* **Flip throttle** (cooldown), **daily loss cap**, and **max position**.
* The **same rules** enforced in both **backtests** and **forward (paper)**.



## 1) Config: risk settings

### `config/base.yaml` (append)

```yaml
risk:
  max_position: 1.0         # absolute cap on |position| (1 = fully long/short)
  flip_cooldown_bars: 3     # wait this many bars after a flip before flipping again
  daily_loss_cap: 0.05      # stop trading rest of the day if DD from day open >= 5%
```

### `src/core/configs.py` (add model + field)

```python
# ...existing imports/models...

class RiskConfig(BaseModel):
    max_position: float = 1.0
    flip_cooldown_bars: int = 0
    daily_loss_cap: float = 0.0

class Config(BaseModel):
    app: AppConfig = AppConfig()
    data: DataConfig = DataConfig()
    kraken: KrakenConfig = KrakenConfig()
    fees: FeesConfig = FeesConfig()
    features: FeaturesConfig = FeaturesConfig()
    selection: SelectionConfig = SelectionConfig()
    runtime: RuntimeConfig = RuntimeConfig()
    labeling: LabelingConfig = LabelingConfig()
    risk: RiskConfig = RiskConfig()         # <-- add this
```



## 2) Rules engine (discrete signals → risk-adjusted)

### `src/execution/risk.py`

```python
from __future__ import annotations
import pandas as pd
import numpy as np

def apply_max_position(signals: pd.Series, cap: float) -> pd.Series:
    """Clamp signal/position to [-cap, cap]."""
    return signals.clip(lower=-abs(cap), upper=abs(cap))

def apply_flip_cooldown(signals: pd.Series, cooldown_bars: int) -> pd.Series:
    """
    Prevent immediate flip-flop: once direction changes sign, hold that side
    at least `cooldown_bars` bars before allowing another sign change.
    Works on integer signals in {-1,0,1}. Flats inherit last sign.
    """
    if cooldown_bars <= 0 or signals.empty:
        return signals.copy()

    s = signals.fillna(0).astype(int).to_numpy()
    last_flip_idx = -np.inf
    last_sign = 0
    for i in range(len(s)):
        sign = int(np.sign(s[i]))
        if sign != 0 and sign != last_sign:
            # if within cooldown, keep previous sign
            if i - last_flip_idx <= cooldown_bars:
                s[i] = last_sign
            else:
                last_flip_idx = i
                last_sign = sign
        else:
            if sign == 0:
                s[i] = last_sign
    return pd.Series(s, index=signals.index, name=signals.name)

def apply_daily_loss_cap(returns: pd.Series, cap: float) -> pd.Series:
    """
    If cumulative equity of the DAY drops below (1 - cap) from day-open equity,
    set subsequent returns for that day to 0 (flat) — i.e., stop trading for the day.
    Assumes `returns` are per-bar strategy returns (after fees).
    """
    if cap <= 0 or returns.empty:
        return returns.copy()

    out = returns.copy()

    # Day labels (UTC)
    idx = out.index
    ts = pd.to_datetime(idx, utc=True)
    day_labels = ts.date

    # Walk each day, zero out after breach
    for day in pd.unique(day_labels):
        mask = (day_labels == day)
        r = out[mask]
        eq = (1 + r).cumprod()
        dd_from_open = 1 - (eq / eq.iloc[0])
        hit = np.argmax(dd_from_open.values >= cap) if (dd_from_open >= cap).any() else -1
        if hit != -1:
            # zero returns AFTER the hit point
            out.iloc[np.where(mask)[0][hit+1:]] = 0.0
    return out
```



## 3) Backtest engine: apply rules

### `src/backtesting/engine.py` (replace)

```python
from __future__ import annotations
import pandas as pd
from src.execution.risk import apply_max_position, apply_flip_cooldown, apply_daily_loss_cap

def run_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    interval_min: int,
    taker_bps: int = 26,
    max_position: float = 1.0,
    flip_cooldown_bars: int = 0,
    daily_loss_cap: float = 0.0,
) -> dict:
    """
    Vectorised long/short backtest with risk rules:
    - Risk-adjust signals: cooldown + max_position
    - Execute next bar (signals shift by 1)
    - Taker fee on position-change events
    - Daily loss cap: stop trading for rest of day after cap breach
    """
    data = df.copy().reset_index(drop=True)
    data["ret"] = data["close"].pct_change().fillna(0.0)

    # Risk-adjust signals
    sig = signal.copy().astype(float).fillna(0.0)
    sig = apply_flip_cooldown(sig, flip_cooldown_bars)
    sig = apply_max_position(sig, max_position)

    # Execute next bar
    pos = sig.shift(1).fillna(0.0)

    # Position change costs
    turns = (pos.diff().abs().fillna(0.0) > 0).astype(int)
    tc = (taker_bps / 1e4) * turns

    strat_ret_gross = pos * data["ret"]
    strat_ret = strat_ret_gross - tc

    # Daily loss cap
    strat_ret_capped = apply_daily_loss_cap(strat_ret, daily_loss_cap)

    equity = (1.0 + strat_ret_capped).cumprod()

    return {
        "returns": strat_ret_capped,
        "equity": equity,
        "positions": pos,
        "interval_min": interval_min,
    }
```



## 4) Backtest CLI: pass risk params (config-first; flags override)

In your **`app/backtest_cli.py`**, add options:

```python
@click.option("--max-position", type=float, default=None, help="Override risk.max_position")
@click.option("--flip-cooldown", type=int, default=None, help="Override risk.flip_cooldown_bars")
@click.option("--daily-loss-cap", type=float, default=None, help="Override risk.daily_loss_cap (0.05 = 5%)")
```

Then resolve defaults from config:

```python
max_position   = cfg.risk.max_position        if max_position   is None else max_position
flip_cooldown  = cfg.risk.flip_cooldown_bars  if flip_cooldown  is None else flip_cooldown
daily_loss_cap = cfg.risk.daily_loss_cap      if daily_loss_cap is None else daily_loss_cap
```

And pass into `run_backtest(...)`:

```python
res = run_backtest(
    df=df,
    signal=sig,
    interval_min=interval,
    taker_bps=cfg.fees.taker_bps,
    max_position=max_position,
    flip_cooldown_bars=flip_cooldown,
    daily_loss_cap=daily_loss_cap,
)
```

*(Keep the rest of the file as-is.)*



## 5) Paper broker: same rules

### `src/forward_test/paper_broker.py` (replace)

```python
from __future__ import annotations
import pandas as pd
from src.execution.risk import apply_max_position, apply_flip_cooldown, apply_daily_loss_cap

class PaperBroker:
    """
    Simple paper broker with the same risk rules as backtest.
    Executes at next bar's close (signals shift by 1).
    """
    def __init__(self, initial_equity: float = 1.0):
        self.equity = initial_equity

    def run(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        taker_bps: int = 26,
        max_position: float = 1.0,
        flip_cooldown_bars: int = 0,
        daily_loss_cap: float = 0.0,
    ) -> pd.Series:
        # Risk-adjust signals
        sig = apply_flip_cooldown(signals.fillna(0.0).astype(float), flip_cooldown_bars)
        sig = apply_max_position(sig, max_position)

        # Execute next bar
        ret = df["close"].pct_change().fillna(0.0)
        pos = sig.shift(1).fillna(0.0)

        turns = (pos.diff().abs().fillna(0.0) > 0).astype(int)
        tc = (taker_bps / 1e4) * turns

        strat_ret = (pos * ret) - tc
        strat_ret = apply_daily_loss_cap(strat_ret, daily_loss_cap)

        equity = (self.equity * (1.0 + strat_ret).cumprod()).rename("equity_paper")
        return equity
```

### `src/forward_test/runner.py` (pass cfg.risk + cfg.fees)

Make sure you pass risk/fees into the broker:

```python
# inside run_forward_test(...)
eq = broker.run(
    df, sig,
    taker_bps=cfg.fees.taker_bps,
    max_position=cfg.risk.max_position,
    flip_cooldown_bars=cfg.risk.flip_cooldown_bars,
    daily_loss_cap=cfg.risk.daily_loss_cap,
)
```

If `cfg` isn’t in scope inside the runner, either:

* load it at the top of `run_forward_test(...)` with `load_config(root=Path.cwd())`, or
* pass `cfg` in from the CLI and use it directly.



## 6) Try it

```bash
# Backtest with config risk
python -m app.backtest_cli --env dev --strategy momentum

# Tighten rules and compare (fewer flips; capped intraday drawdowns)
python -m app.backtest_cli --env dev --strategy momentum --flip-cooldown 5 --daily-loss-cap 0.03

# Paper test after selection (uses risk from config)
python -m app.forward_test_cli --env dev
```
