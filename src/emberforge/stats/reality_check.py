"""White's Reality Check and Hansen's SPA test.

Both test the null hypothesis that the *best* factor among many has no genuine
superiority over a benchmark (here: zero performance), correcting for the fact
that the best of N tried candidates is upward-biased. They are the family-level
counterparts to the per-candidate Deflated Sharpe.

Input is a ``T x N`` matrix of per-period performance (higher = better; e.g. the
diagnostic long-short return of each candidate). The benchmark is 0 (no skill),
so a column's mean is its edge over the benchmark. Bootstrap is a circular block
bootstrap to respect serial correlation.

References: White (2000), "A Reality Check for Data Snooping"; Hansen (2005),
"A Test for Superior Predictive Ability".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RealityCheckResult:
    statistic: float
    p_value: float
    n_models: int
    n_obs: int
    method: str


def _block_bootstrap_indices(n: int, block_size: int, rng) -> np.ndarray:
    n_blocks = int(np.ceil(n / block_size))
    starts = rng.integers(0, n, size=n_blocks)
    idx = np.concatenate([(np.arange(s, s + block_size) % n) for s in starts])
    return idx[:n]


def _prep(perf_matrix) -> np.ndarray:
    X = np.asarray(perf_matrix, dtype=float)
    if X.ndim != 2:
        raise ValueError("perf_matrix must be 2-D (T x N)")
    return X[~np.isnan(X).any(axis=1)]


def whites_reality_check(perf_matrix, n_boot: int = 1000, block_size: int | None = None, seed: int = 0) -> RealityCheckResult:
    """White's Reality Check p-value for the best column's mean vs a zero benchmark."""
    X = _prep(perf_matrix)
    T, N = X.shape
    if T < 3 or N < 1:
        return RealityCheckResult(float("nan"), float("nan"), N, T, "whites_reality_check")
    means = X.mean(axis=0)
    V = np.sqrt(T) * means.max()
    if block_size is None:
        block_size = max(1, int(round(T ** (1 / 3))))
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_boot):
        idx = _block_bootstrap_indices(T, block_size, rng)
        boot_means = X[idx].mean(axis=0)
        Vstar = np.sqrt(T) * (boot_means - means).max()  # recentered
        if Vstar >= V:
            exceed += 1
    return RealityCheckResult(float(V), exceed / n_boot, N, T, "whites_reality_check")


def hansens_spa(perf_matrix, n_boot: int = 1000, block_size: int | None = None, seed: int = 0) -> RealityCheckResult:
    """Hansen's SPA test (consistent p-value); studentized, with poor models down-weighted."""
    X = _prep(perf_matrix)
    T, N = X.shape
    if T < 3 or N < 1:
        return RealityCheckResult(float("nan"), float("nan"), N, T, "hansens_spa")
    means = X.mean(axis=0)
    omega = X.std(axis=0, ddof=1)
    omega = np.where(omega == 0, np.nan, omega)
    z = np.sqrt(T) * means / omega
    T_spa = max(0.0, float(np.nanmax(z)))

    # recentering threshold: exclude clearly-inferior models from the null max
    loglog = max(np.log(np.log(T)) if T > np.e else 1e-6, 1e-6)
    threshold = -np.sqrt(2.0 * loglog)
    keep = z >= threshold  # models good enough to plausibly be the best
    g = np.where(keep, means, 0.0)

    if block_size is None:
        block_size = max(1, int(round(T ** (1 / 3))))
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(n_boot):
        idx = _block_bootstrap_indices(T, block_size, rng)
        boot_means = X[idx].mean(axis=0)
        zstar = np.sqrt(T) * (boot_means - g) / omega
        Tstar = max(0.0, float(np.nanmax(zstar)))
        if Tstar >= T_spa:
            exceed += 1
    return RealityCheckResult(float(T_spa), exceed / n_boot, N, T, "hansens_spa")


__all__ = ["whites_reality_check", "hansens_spa", "RealityCheckResult"]
