"""Causal factor computation engine."""

from .engine import (
    PreprocessConfig,
    assert_no_lookahead,
    compute_factor,
    coverage_series,
    evaluate,
)

__all__ = [
    "PreprocessConfig", "compute_factor", "evaluate",
    "coverage_series", "assert_no_lookahead",
]
