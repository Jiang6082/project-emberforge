"""Factor deduplication and novelty analysis (syntactic, empirical, semantic)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..dsl.spec import FactorSpec
from .empirical import CorrelationMatch, find_correlated, score_correlation
from .semantic import FAMILIES, classify
from .syntactic import find_syntactic_duplicates, is_syntactic_duplicate

__all__ = [
    "is_syntactic_duplicate", "find_syntactic_duplicates",
    "score_correlation", "find_correlated", "CorrelationMatch",
    "classify", "FAMILIES",
    "NoveltyReport", "novelty_report",
]


@dataclass
class NoveltyReport:
    factor_id: str
    family: str
    syntactic_duplicates: list[str] = field(default_factory=list)
    correlated: list[CorrelationMatch] = field(default_factory=list)
    is_duplicate: bool = False

    @property
    def nearest(self) -> CorrelationMatch | None:
        return self.correlated[0] if self.correlated else None


def novelty_report(
    candidate: FactorSpec,
    candidate_scores: pd.DataFrame,
    existing: list[FactorSpec],
    existing_scores: dict[str, pd.DataFrame],
    corr_threshold: float = 0.7,
    min_overlap: int = 30,
) -> NoveltyReport:
    syn = find_syntactic_duplicates(candidate, existing)
    corr = find_correlated(candidate_scores, existing_scores, corr_threshold, min_overlap)
    return NoveltyReport(
        factor_id=candidate.factor_id,
        family=classify(candidate),
        syntactic_duplicates=syn,
        correlated=corr,
        is_duplicate=bool(syn) or bool(corr),
    )
