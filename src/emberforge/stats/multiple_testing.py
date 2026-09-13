"""Family-wise and false-discovery multiple-testing corrections.

No single method is treated as proof of alpha. These adjust p-values across a
family of tested factors so that a candidate that only looks good because many
were tried is discounted accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Adjusted:
    p_raw: float
    p_adjusted: float
    reject: bool


def _validated_pvalues(pvalues, alpha):
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must be finite and in (0, 1)")
    p = np.asarray(pvalues, dtype=float)
    if p.ndim != 1:
        raise ValueError("pvalues must be one-dimensional")
    # A missing/invalid result remains a trial but carries no evidence.
    return np.where(np.isfinite(p) & (p >= 0) & (p <= 1), p, 1.0)


def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[Adjusted]:
    """Benjamini–Hochberg step-up FDR control at level ``alpha``."""
    p = _validated_pvalues(pvalues, alpha)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    # BH adjusted p-values with monotone enforcement (running min from the top).
    adj = ranked * m / (np.arange(1, m + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(m)
    out[order] = adj
    return [Adjusted(float(pv), float(a), bool(a <= alpha)) for pv, a in zip(p, out)]


def holm(pvalues: list[float], alpha: float = 0.05) -> list[Adjusted]:
    """Holm–Bonferroni step-down FWER control at level ``alpha``."""
    p = _validated_pvalues(pvalues, alpha)
    m = len(p)
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * (m - np.arange(m))
    adj = np.maximum.accumulate(adj)  # enforce monotonicity
    adj = np.clip(adj, 0, 1)
    out = np.empty(m)
    out[order] = adj
    return [Adjusted(float(pv), float(a), bool(a <= alpha)) for pv, a in zip(p, out)]
