"""Combinatorial Purged Cross-Validation (CPCV).

CPCV (López de Prado, *Advances in Financial Machine Learning*, 2018) partitions
the timeline into ``n_groups`` contiguous groups and tests every combination of
``n_test_groups`` groups at once, purging and embargoing training observations
whose label windows overlap the test groups. Because each group appears in many
combinations, CPCV yields **many** backtest paths rather than one, which is a
more robust basis for an overfit estimate than the single-path CSCV.

Two uses are provided:

* :func:`cpcv_splits` — the raw purged/embargoed train/test index folds, one per
  combination (an alternative to :func:`emberforge.stats.cv.purged_embargoed_kfold`);
* :func:`pbo_cpcv` — a Probability-of-Backtest-Overfitting estimate that
  generalizes CSCV to ``k`` test groups, computed over a ``T x N`` matrix of
  candidate return series.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

import numpy as np

from .cv import Fold


def _groups(n: int, n_groups: int) -> list[np.ndarray]:
    return [g for g in np.array_split(np.arange(n), n_groups) if len(g)]


def cpcv_splits(
    n: int, n_groups: int = 6, n_test_groups: int = 2, horizon: int = 1, embargo: int = 0
) -> list[Fold]:
    """Return one purged/embargoed :class:`Fold` per combination of test groups."""
    if not (1 <= n_test_groups < n_groups <= n):
        raise ValueError("require 1 <= n_test_groups < n_groups <= n")
    groups = _groups(n, n_groups)
    all_idx = np.arange(n)
    folds: list[Fold] = []
    for combo in combinations(range(len(groups)), n_test_groups):
        test = np.concatenate([groups[g] for g in combo])
        # purge training obs whose [i, i+horizon] window overlaps any test block,
        # plus an embargo after each test block.
        banned = np.zeros(n, dtype=bool)
        for g in combo:
            lo, hi = int(groups[g][0]), int(groups[g][-1])
            banned[max(0, lo - horizon): hi + horizon + embargo + 1] = True
        train = all_idx[~banned]
        train = train[~np.isin(train, test)]
        folds.append(Fold(train=train, test=np.asarray(test)))
    return folds


def n_backtest_paths(n_groups: int, n_test_groups: int) -> int:
    """Number of distinct backtest paths CPCV produces."""
    return comb(n_groups, n_test_groups) * n_test_groups // n_groups


@dataclass(frozen=True)
class CPCVResult:
    pbo: float
    n_combinations: int
    n_paths: int
    n_strategies: int
    note: str = "CPCV overfit estimate"


def _sharpe(x: np.ndarray) -> np.ndarray:
    mu = x.mean(axis=0)
    sd = x.std(axis=0, ddof=1)
    sd = np.where(sd == 0, np.nan, sd)
    return mu / sd


def pbo_cpcv(
    returns_matrix, n_groups: int = 6, n_test_groups: int = 2, horizon: int = 1, embargo: int = 0
) -> CPCVResult:
    """PBO estimate over a ``T x N`` return matrix using combinatorial paths.

    For each combination: rank strategies in-sample (the non-test groups) and
    out-of-sample (the test groups); the fraction of combinations where the
    in-sample-best strategy lands below the OOS median is the overfit estimate.
    """
    M = np.asarray(returns_matrix, dtype=float)
    M = M[~np.isnan(M).any(axis=1)]
    T, N = M.shape
    if N < 2:
        return CPCVResult(float("nan"), 0, 0, N, "need >= 2 strategies")
    if not (1 <= n_test_groups < n_groups <= T):
        return CPCVResult(float("nan"), 0, 0, N, "not enough observations")

    folds = cpcv_splits(T, n_groups, n_test_groups, horizon, embargo)
    below = 0
    used = 0
    for fold in folds:
        if len(fold.train) < 2 or len(fold.test) < 2:
            continue
        is_perf = _sharpe(M[fold.train])
        oos_perf = _sharpe(M[fold.test])
        if np.all(np.isnan(is_perf)) or np.all(np.isnan(oos_perf)):
            continue
        best = int(np.nanargmax(is_perf))
        oos_rank = np.sum(oos_perf <= oos_perf[best]) / (N + 1)
        below += int(oos_rank <= 0.5)
        used += 1
    pbo = (below / used) if used else float("nan")
    return CPCVResult(pbo, used, n_backtest_paths(n_groups, n_test_groups), N)


__all__ = ["cpcv_splits", "pbo_cpcv", "n_backtest_paths", "CPCVResult"]
