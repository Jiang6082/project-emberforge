"""Layer 2: empirical deduplication via aligned score correlation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CorrelationMatch:
    factor_id: str
    correlation: float
    overlap: int


def score_correlation(a: pd.DataFrame, b: pd.DataFrame, min_overlap: int = 30) -> tuple[float, int]:
    """Correlation of two factor-score matrices over their aligned cells."""
    a2, b2 = a.align(b, join="inner")
    x = a2.values.flatten()
    y = b2.values.flatten()
    mask = ~np.isnan(x) & ~np.isnan(y)
    overlap = int(mask.sum())
    if overlap < min_overlap:
        return float("nan"), overlap
    if np.std(x[mask]) == 0 or np.std(y[mask]) == 0:
        return float("nan"), overlap
    return float(np.corrcoef(x[mask], y[mask])[0, 1]), overlap


def find_correlated(
    candidate_scores: pd.DataFrame,
    existing_scores: dict[str, pd.DataFrame],
    threshold: float = 0.7,
    min_overlap: int = 30,
) -> list[CorrelationMatch]:
    matches = []
    for fid, scores in existing_scores.items():
        corr, overlap = score_correlation(candidate_scores, scores, min_overlap)
        if not np.isnan(corr) and abs(corr) >= threshold:
            matches.append(CorrelationMatch(fid, corr, overlap))
    return sorted(matches, key=lambda m: abs(m.correlation), reverse=True)
