"""Deflated Sharpe Ratio (Bailey & López de Prado, 2014).

DSR discounts an observed Sharpe for (a) the number of trials that were run and
(b) the non-normality (skew/kurtosis) and length of the return series. It answers
"given that we tried N configurations, how surprising is this Sharpe?".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

EULER_MASCHERONI = 0.5772156649015329


@dataclass(frozen=True)
class DSRResult:
    observed_sharpe: float      # per-period (not annualized)
    expected_max_sharpe: float  # SR0 under N trials of null strategies
    dsr: float                  # probability the true Sharpe > 0 given the trials
    n_trials: int
    n_obs: int


def _sharpe_std(sr: float, n: int, skew: float, kurt: float) -> float:
    # Standard error of the Sharpe estimator with non-normal returns.
    return np.sqrt((1 - skew * sr + (kurt - 1) / 4.0 * sr**2) / (n - 1))


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected maximum Sharpe of ``n_trials`` independent null strategies."""
    if n_trials <= 1 or sr_variance <= 0:
        return 0.0
    e = EULER_MASCHERONI
    z1 = norm.ppf(1 - 1.0 / n_trials)
    z2 = norm.ppf(1 - 1.0 / (n_trials * np.e))
    return np.sqrt(sr_variance) * ((1 - e) * z1 + e * z2)


def deflated_sharpe(
    returns,
    n_trials: int,
    sr_variance: float | None = None,
) -> DSRResult:
    """Compute the Deflated Sharpe Ratio for a return series.

    ``sr_variance`` is the variance of the (per-period) Sharpe ratios across the
    trial family; if unknown it is approximated from the estimator variance.
    """
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return DSRResult(float("nan"), float("nan"), float("nan"), n_trials, n)

    sr = r.mean() / r.std(ddof=1)
    # sample skew/kurtosis (kurt is the full fourth moment, ~3 for normal)
    z = (r - r.mean()) / r.std(ddof=0)
    skew = float(np.mean(z**3))
    kurt = float(np.mean(z**4))

    if sr_variance is None:
        sr_variance = _sharpe_std(sr, n, skew, kurt) ** 2
    sr0 = expected_max_sharpe(n_trials, sr_variance)
    denom = _sharpe_std(sr, n, skew, kurt)
    dsr = float(norm.cdf((sr - sr0) / denom)) if denom > 0 else float("nan")
    return DSRResult(float(sr), float(sr0), dsr, n_trials, n)
