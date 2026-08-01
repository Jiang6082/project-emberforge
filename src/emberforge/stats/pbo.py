"""Probability of Backtest Overfitting via Combinatorially-Symmetric CV.

Implementation of the CSCV procedure (Bailey, Borwein, López de Prado, Zhu 2017)
as a documented approximation. Input is a matrix of per-period returns with one
column per candidate strategy. PBO estimates how often the in-sample best
strategy underperforms out-of-sample — a high PBO means the selection process is
overfit.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np


@dataclass(frozen=True)
class PBOResult:
    pbo: float             # probability of backtest overfitting in [0, 1]
    n_combinations: int
    n_strategies: int
    note: str = "CSCV approximation"


def _sharpe(x: np.ndarray) -> np.ndarray:
    mu = x.mean(axis=0)
    sd = x.std(axis=0, ddof=1)
    sd = np.where(sd == 0, np.nan, sd)
    return mu / sd


def pbo_cscv(returns_matrix, n_splits: int = 10) -> PBOResult:
    """Estimate PBO from a (T x N) return matrix using CSCV.

    ``n_splits`` (S) must be even; the T rows are cut into S contiguous blocks and
    every way of choosing S/2 blocks as in-sample (rest out-of-sample) is tried.
    """
    M = np.asarray(returns_matrix, dtype=float)
    M = M[~np.isnan(M).any(axis=1)]
    T, N = M.shape
    if N < 2:
        return PBOResult(float("nan"), 0, N, "need >= 2 strategies")
    if n_splits % 2 == 1:
        n_splits += 1
    S = min(n_splits, T)
    S -= S % 2
    if S < 2:
        return PBOResult(float("nan"), 0, N, "not enough observations")

    blocks = np.array_split(np.arange(T), S)
    logits = []
    for is_idx in combinations(range(S), S // 2):
        is_rows = np.concatenate([blocks[b] for b in is_idx])
        oos_rows = np.concatenate([blocks[b] for b in range(S) if b not in is_idx])
        is_perf = _sharpe(M[is_rows])
        oos_perf = _sharpe(M[oos_rows])
        best = int(np.nanargmax(is_perf))
        # relative rank of the IS-best strategy out-of-sample, in (0, 1)
        oos_rank = (np.sum(oos_perf <= oos_perf[best]) ) / (N + 1)
        oos_rank = min(max(oos_rank, 1e-6), 1 - 1e-6)
        logits.append(np.log(oos_rank / (1 - oos_rank)))

    logits = np.asarray(logits)
    pbo = float(np.mean(logits <= 0))  # fraction where IS-best is below OOS median
    return PBOResult(pbo, len(logits), N)
