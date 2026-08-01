"""Cross-sectional factor analytics and evaluation orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from ..compute import PreprocessConfig, compute_factor
from ..data.schema import MarketData
from ..dsl.spec import FactorSpec
from .ic import ICStats, ic_decay, ic_series, ic_stats
from .portfolio import (
    PortfolioStats,
    long_short_returns,
    portfolio_stats,
    quantile_returns,
    score_autocorr,
    turnover,
)

__all__ = [
    "ic_series", "ic_stats", "ic_decay", "ICStats",
    "quantile_returns", "long_short_returns", "turnover", "score_autocorr",
    "portfolio_stats", "PortfolioStats",
    "FactorEvaluation", "evaluate_factor",
]


@dataclass
class FactorEvaluation:
    factor_id: str
    expression_hash: str
    ic: ICStats
    ic_decay: dict
    portfolio: PortfolioStats
    coverage: float
    autocorr: float
    ls_returns: pd.Series = field(repr=False)

    def to_metrics(self) -> dict:
        """Flat, JSON-serializable metric dict for the registry and reports."""
        return {
            "n_periods": self.ic.n,
            "mean_ic": self.ic.mean_ic,
            "ic_ir": self.ic.ic_ir,
            "ic_t_stat": self.ic.t_stat,
            "ic_hit_rate": self.ic.hit_rate,
            "sharpe": self.portfolio.sharpe,
            "sharpe_after_cost": self.portfolio.sharpe_after_cost,
            "ann_return": self.portfolio.ann_return,
            "ann_vol": self.portfolio.ann_vol,
            "turnover": self.portfolio.turnover,
            "monotonicity": self.portfolio.monotonicity,
            "spread": self.portfolio.spread,
            "coverage": self.coverage,
            "autocorr": self.autocorr,
            "ic_decay": self.ic_decay,
        }


def evaluate_factor(
    spec: FactorSpec,
    data: MarketData,
    horizon: int = 1,
    q: int = 5,
    cost_bps: float = 5.0,
    preprocess: PreprocessConfig = PreprocessConfig(),
) -> FactorEvaluation:
    """Compute and evaluate a factor end-to-end (analytics only, no stats gates)."""
    scores = compute_factor(spec, data, preprocess)
    fwd = data.forward_returns(horizon)
    return FactorEvaluation(
        factor_id=spec.factor_id,
        expression_hash=spec.expression_hash,
        ic=ic_stats(scores, fwd),
        ic_decay=ic_decay(scores, data),
        portfolio=portfolio_stats(scores, fwd, q=q, cost_bps=cost_bps),
        coverage=float(scores.notna().mean(axis=1).mean()),
        autocorr=score_autocorr(scores),
        ls_returns=long_short_returns(scores, fwd, q),
    )
