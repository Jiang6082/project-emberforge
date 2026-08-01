"""Purged and embargoed K-fold cross-validation indices (López de Prado).

When labels span multiple bars (a forward return over ``horizon`` bars),
naive K-fold leaks: a training observation whose label window overlaps the test
fold has seen test-period information. Purging removes those overlapping training
observations; an embargo additionally drops a few observations immediately after
each test fold to kill serial-correlation leakage.

This is the concrete building block behind the "embargoed / purged CV" extension
point named in the roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Fold:
    train: np.ndarray
    test: np.ndarray


def purged_embargoed_kfold(
    n: int, k: int = 5, horizon: int = 1, embargo: int = 0
) -> list[Fold]:
    """Return ``k`` purged, embargoed train/test folds over ``n`` ordered observations."""
    if k < 2 or k > n:
        raise ValueError("k must be in [2, n]")
    indices = np.arange(n)
    test_folds = np.array_split(indices, k)
    folds: list[Fold] = []
    for test in test_folds:
        t0, t1 = int(test[0]), int(test[-1])
        # a training label at i spans [i, i+horizon]; purge if it overlaps the test block
        purge_lo = t0 - horizon
        purge_hi = t1 + horizon + embargo
        train = indices[(indices < purge_lo) | (indices > purge_hi)]
        folds.append(Fold(train=train, test=np.asarray(test)))
    return folds


__all__ = ["purged_embargoed_kfold", "Fold"]
