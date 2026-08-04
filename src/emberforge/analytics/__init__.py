"""Cross-sectional factor analytics and evaluation orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..compute import PreprocessConfig, compute_factor
from ..data.schema import MarketData
from ..dsl.spec import FactorSpec
from .costs import CapacityEstimate, CostModel, cost_sensitivity, estimate_capacity
from .ic import ICStats, ic_decay, ic_series, ic_stats
from .portfolio import (
    PortfolioStats,
    long_short_returns,
    portfolio_stats,
    quantile_returns,
    score_autocorr,
    turnover,
)
from .portfolio_backtest import (
    PortfolioBacktest,
    PortfolioSpec,
    backtest_portfolio,
    default_portfolio_spec,
)

TRADING_DAYS = 252

__all__ = [
    "ic_series", "ic_stats", "ic_decay", "ICStats",
    "quantile_returns", "long_short_returns", "turnover", "score_autocorr",
    "portfolio_stats", "PortfolioStats",
    "CostModel", "CapacityEstimate", "estimate_capacity", "cost_sensitivity",
    "PortfolioSpec", "PortfolioBacktest", "backtest_portfolio", "default_portfolio_spec",
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
    capacity_usd: float = float("nan")
    cost_sensitivity: dict = field(default_factory=dict)
    portfolio_spec: dict = field(default_factory=dict)
    portfolio_backtest: dict = field(default_factory=dict)

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
            "capacity_usd": self.capacity_usd,
            "cost_sensitivity": self.cost_sensitivity,
            "portfolio_spec": self.portfolio_spec,
            "portfolio_backtest": self.portfolio_backtest,
            "ic_decay": self.ic_decay,
        }


def evaluate_factor(
    spec: FactorSpec,
    data: MarketData,
    horizon: int = 1,
    q: int = 5,
    cost_bps: float = 5.0,
    preprocess: PreprocessConfig = PreprocessConfig(),
    universe=None,
    adv_window: int = 63,
) -> FactorEvaluation:
    """Compute and evaluate a factor end-to-end (analytics only, no stats gates).

    If ``universe`` is given, its point-in-time-safe eligibility mask is applied.
    ``adv_window`` is the trailing window (in bars) used to estimate each name's
    recent average daily dollar volume for the capacity calc, so capacity tracks
    *current* liquidity rather than a full-history snapshot.
    """
    eligibility = None
    if universe is not None:
        eligibility = universe.eligibility(data.index, data.symbols)
    scores = compute_factor(spec, data, preprocess, eligibility=eligibility)
    fwd = data.forward_returns(horizon)
    # one CostModel drives the headline net Sharpe, capacity, and cost sensitivity.
    cost_model = CostModel()
    pstats = portfolio_stats(scores, fwd, q=q, cost_bps=cost_bps, cost_model=cost_model)
    ls = long_short_returns(scores, fwd, q)

    # capacity & cost sensitivity from a per-name liquidity/volatility profile
    gross = float(ls.mean()) if len(ls) else float("nan")
    tvr = pstats.turnover if pstats.turnover == pstats.turnover else 0.5
    try:
        dollar_vol = data.field("volume") * data.field("close")
        if eligibility is not None:
            dollar_vol = dollar_vol.where(eligibility.reindex_like(dollar_vol).fillna(False))
        recent = dollar_vol.tail(adv_window)                  # trailing window → current liquidity
        adv_series = recent.median(axis=0).dropna()
        adv_per_name = adv_series.values                      # per-symbol recent ADV ($)
        vol_per_name = data.field("close").pct_change().tail(adv_window).std(axis=0)
        vol_per_name = vol_per_name.reindex(adv_series.index).values
        if adv_per_name.size == 0:
            adv_per_name, vol_per_name = float("nan"), None
    except Exception:
        adv_per_name, vol_per_name = float("nan"), None
    cap = estimate_capacity(gross, adv_per_name, tvr, model=cost_model, daily_vol=vol_per_name)
    cost_sens = cost_sensitivity(pstats.sharpe, gross, pstats.ann_vol, tvr)

    # portfolio-construction hint + a portfolio-level (net) backtest
    pspec = default_portfolio_spec(q)
    pbt = backtest_portfolio(scores, fwd, spec=pspec, cost_model=cost_model)

    return FactorEvaluation(
        factor_id=spec.factor_id,
        expression_hash=spec.expression_hash,
        ic=ic_stats(scores, fwd),
        ic_decay=ic_decay(scores, data),
        portfolio=pstats,
        coverage=float(scores.notna().mean(axis=1).mean()),
        autocorr=score_autocorr(scores),
        ls_returns=ls,
        capacity_usd=cap.capacity_usd,
        cost_sensitivity={str(k): v for k, v in cost_sens.items()},
        portfolio_spec=pspec.to_dict(),
        portfolio_backtest=pbt.to_dict(),
    )
