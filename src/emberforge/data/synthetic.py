"""Deterministic synthetic market data with a *known* embedded signal.

The generator plants a genuine cross-sectional momentum effect: a symbol's next
return depends weakly on its own trailing 20-bar return. This lets the demo show
a real factor (momentum) beating noise factors, without any live data. Given the
same seed the output is byte-for-byte identical, so fixtures are reproducible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .schema import DatasetMetadata, MarketData


def make_synthetic(
    n_symbols: int = 12,
    n_days: int = 400,
    seed: int = 7,
    momentum_beta: float = 0.05,
    start: str = "2021-01-04",
) -> MarketData:
    rng = np.random.default_rng(seed)
    symbols = [f"SYM{i:02d}" for i in range(n_symbols)]
    dates = pd.bdate_range(start=start, periods=n_days, tz="UTC")

    drift = 0.0002
    vol = 0.015
    eps = rng.normal(0.0, vol, size=(n_days, n_symbols))
    returns = np.zeros((n_days, n_symbols))
    log_price = np.zeros((n_days, n_symbols))
    log_price[0] = np.log(rng.uniform(20, 200, size=n_symbols))

    look = 20
    for t in range(1, n_days):
        if t > look:
            trail = log_price[t - 1] - log_price[t - 1 - look]  # trailing 20d log-return
            z = (trail - trail.mean()) / (trail.std() + 1e-9)
            signal = momentum_beta * vol * z
        else:
            signal = 0.0
        returns[t] = drift + signal + eps[t]
        log_price[t] = log_price[t - 1] + returns[t]

    close = pd.DataFrame(np.exp(log_price), index=dates, columns=symbols)
    intraday = rng.uniform(0.0, 0.01, size=(n_days, n_symbols))
    high = close * (1 + intraday)
    low = close * (1 - intraday)
    open_ = close.shift(1).fillna(close.iloc[0]) * (1 + rng.normal(0, 0.002, (n_days, n_symbols)))
    volume = pd.DataFrame(
        rng.integers(1_000_000, 5_000_000, size=(n_days, n_symbols)).astype(float),
        index=dates, columns=symbols,
    )
    vwap = (high + low + close) / 3.0

    panels = {
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume, "vwap": vwap,
    }
    meta = DatasetMetadata(
        source="synthetic", frequency="daily", feed="synthetic",
        version=f"seed{seed}-n{n_symbols}-t{n_days}", adjustment="none",
    )
    return MarketData(panels, meta)
