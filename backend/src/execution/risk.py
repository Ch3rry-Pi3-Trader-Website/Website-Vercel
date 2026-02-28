from __future__ import annotations

import numpy as np
import pandas as pd


def apply_max_position(signals: pd.Series, cap: float) -> pd.Series:
    return signals.clip(lower=-abs(cap), upper=abs(cap))


def apply_flip_cooldown(signals: pd.Series, cooldown_bars: int) -> pd.Series:
    if cooldown_bars <= 0 or signals.empty:
        return signals.copy()

    s = signals.fillna(0).astype(float).to_numpy(copy=True)
    if not s.flags.writeable:
        s = s.copy()
    last_flip_idx = -np.inf
    last_sign = 0.0
    for i in range(len(s)):
        sign = float(np.sign(s[i]))
        if sign != 0.0 and sign != last_sign:
            if i - last_flip_idx <= cooldown_bars:
                s[i] = last_sign
            else:
                last_flip_idx = i
                last_sign = sign
        elif sign == 0.0:
            s[i] = last_sign
    return pd.Series(s, index=signals.index, name=signals.name)


def apply_daily_loss_cap(returns: pd.Series, cap: float) -> pd.Series:
    if cap <= 0 or returns.empty:
        return returns.copy()

    out = returns.copy()
    ts = pd.to_datetime(out.index, utc=True, errors="coerce")
    if ts.isna().all():
        return out
    day_labels = ts.date

    for day in pd.unique(day_labels):
        mask = day_labels == day
        r = out[mask]
        if r.empty:
            continue
        eq = (1 + r).cumprod()
        dd_from_open = 1 - (eq / eq.iloc[0])
        hit = np.argmax(dd_from_open.values >= cap) if (dd_from_open >= cap).any() else -1
        if hit != -1:
            out.iloc[np.where(mask)[0][hit + 1 :]] = 0.0
    return out
