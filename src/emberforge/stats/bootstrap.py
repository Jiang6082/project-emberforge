"""Time-aware (circular block) bootstrap confidence intervals.

Block resampling preserves short-horizon autocorrelation that an iid bootstrap
would destroy, giving more honest intervals for serially-correlated series such
as daily strategy returns or IC series.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class BootstrapCI:
    point: float
    lower: float
    upper: float
    level: float
    n_boot: int


def _sharpe(x: np.ndarray) -> float:
    sd = x.std(ddof=1)
    return float(x.mean() / sd) if sd > 0 else float("nan")


def circular_block_bootstrap(
    series,
    statistic: Callable[[np.ndarray], float] | str = "mean",
    block_size: int | None = None,
    n_boot: int = 1000,
    level: float = 0.95,
    seed: int = 0,
) -> BootstrapCI:
    x = np.asarray(series, dtype=float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 3:
        return BootstrapCI(float("nan"), float("nan"), float("nan"), level, n_boot)
    stat: Callable[[np.ndarray], float]
    if statistic == "mean":
        stat = lambda a: float(np.mean(a))
    elif statistic == "sharpe":
        stat = _sharpe
    else:
        stat = statistic  # type: ignore[assignment]

    if block_size is None:
        block_size = max(1, int(round(n ** (1 / 3))))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    ext = np.concatenate([x, x[: block_size]])  # wrap for circularity

    estimates = np.empty(n_boot)
    for i in range(n_boot):
        starts = rng.integers(0, n, size=n_blocks)
        sample = np.concatenate([ext[s : s + block_size] for s in starts])[:n]
        estimates[i] = stat(sample)

    a = (1 - level) / 2
    lo, hi = np.nanpercentile(estimates, [100 * a, 100 * (1 - a)])
    return BootstrapCI(stat(x), float(lo), float(hi), level, n_boot)
