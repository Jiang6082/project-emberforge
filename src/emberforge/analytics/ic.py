"""Information-coefficient analytics.

IC at time ``t`` is the cross-sectional correlation between factor scores known
at ``t`` and the forward return from ``t`` to ``t+h``. Because the factor only
uses data up to ``t`` and the label looks strictly forward, the alignment is
causal by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def ic_series(scores: pd.DataFrame, fwd_returns: pd.DataFrame, method: str = "pearson") -> pd.Series:
    s = scores.reindex_like(fwd_returns)
    out = {}
    for ts in s.index:
        a = s.loc[ts]
        b = fwd_returns.loc[ts]
        pair = pd.concat([a, b], axis=1).dropna()
        if len(pair) >= 3:
            out[ts] = pair.iloc[:, 0].corr(pair.iloc[:, 1], method=method)
    return pd.Series(out, dtype=float).dropna()


@dataclass(frozen=True)
class ICStats:
    n: int
    mean_ic: float
    ic_std: float
    ic_ir: float          # information ratio = mean/std
    t_stat: float         # mean/std * sqrt(n), assumes iid periods (stated!)
    hit_rate: float       # fraction of periods with IC same sign as mean
    method: str


def ic_stats(scores: pd.DataFrame, fwd_returns: pd.DataFrame, method: str = "spearman") -> ICStats:
    ic = ic_series(scores, fwd_returns, method=method)
    n = int(ic.shape[0])
    if n == 0:
        return ICStats(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), method)
    mean = float(ic.mean())
    std = float(ic.std(ddof=1)) if n > 1 else float("nan")
    ir = mean / std if std and not np.isnan(std) else float("nan")
    t = ir * np.sqrt(n) if not np.isnan(ir) else float("nan")
    hit = float((np.sign(ic) == np.sign(mean)).mean()) if mean != 0 else float("nan")
    return ICStats(n, mean, std, ir, t, hit, method)


def ic_decay(scores: pd.DataFrame, data, horizons=(1, 2, 3, 5, 10), method: str = "spearman") -> dict[int, float]:
    """Mean IC at increasing forward horizons — the factor's shelf life."""
    out: dict[int, float] = {}
    for h in horizons:
        fwd = data.forward_returns(h)
        out[h] = float(ic_series(scores, fwd, method=method).mean())
    return out
