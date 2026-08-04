"""Portfolio-construction hint + a portfolio-level research backtest.

Emberforge's core job is the *signal* (the factor). This module adds the small
*portfolio* layer on top: a declarative recommendation for how to turn factor
scores into positions, plus a research-grade backtest of that portfolio (equity
curve summary, drawdown, net-of-cost Sharpe).

It is deliberately a *research* backtest — cross-sectional, next-bar alignment,
flat bps costs — not an execution simulation. Realistic fills, slippage, and live
risk stay in the execution layer (Project Geld). This gives Geld a richer,
position-aware recipe without Emberforge taking over execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .costs import CostModel
from .portfolio import long_short_returns, turnover

TRADING_DAYS = 252


@dataclass(frozen=True)
class PortfolioSpec:
    """A declarative, data-only recommendation for turning scores into positions."""

    kind: str = "cross_sectional_quantile"
    quantiles: int = 5
    long_quantile: str = "top"
    short_quantile: str = "bottom"
    weighting: str = "equal"
    rebalance: str = "daily"
    neutralize: bool = False
    gross_exposure: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


def default_portfolio_spec(q: int = 5) -> PortfolioSpec:
    return PortfolioSpec(quantiles=q)


@dataclass(frozen=True)
class PortfolioBacktest:
    n_periods: int
    ann_return: float
    ann_vol: float
    sharpe: float           # net of costs
    max_drawdown: float
    turnover: float
    hit_rate: float
    total_return: float
    cost_bps: float

    def to_dict(self) -> dict:
        return asdict(self)


def backtest_portfolio(
    scores: pd.DataFrame,
    fwd_returns: pd.DataFrame,
    spec: PortfolioSpec | None = None,
    cost_model: CostModel | None = None,
    cost_bps: float = 5.0,
) -> PortfolioBacktest:
    """Backtest the long/short quantile portfolio implied by ``spec``.

    Returns net-of-cost equity-curve statistics (annualized return/vol/Sharpe,
    max drawdown, turnover, hit rate, cumulative return).
    """
    spec = spec or default_portfolio_spec()
    ls = long_short_returns(scores, fwd_returns, spec.quantiles)
    tvr = turnover(scores, spec.quantiles)
    tvr_eff = tvr if tvr == tvr else 0.0
    if cost_model is not None:
        cost = cost_model.per_period_cost(tvr_eff, participation=0.0)
    else:
        cost = (cost_bps / 1e4) * tvr_eff
    net = (ls - cost).dropna()
    if len(net) < 2 or net.std(ddof=1) == 0:
        return PortfolioBacktest(len(net), float("nan"), float("nan"), float("nan"),
                                 float("nan"), tvr_eff, float("nan"), float("nan"), cost_bps)
    equity = (1.0 + net).cumprod()
    drawdown = float((equity / equity.cummax() - 1.0).min())
    sharpe = float(net.mean() / net.std(ddof=1) * np.sqrt(TRADING_DAYS))
    return PortfolioBacktest(
        n_periods=int(len(net)),
        ann_return=float(net.mean() * TRADING_DAYS),
        ann_vol=float(net.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        sharpe=sharpe,
        max_drawdown=drawdown,
        turnover=float(tvr_eff),
        hit_rate=float((net > 0).mean()),
        total_return=float(equity.iloc[-1] - 1.0),
        cost_bps=float(cost_bps),
    )


__all__ = ["PortfolioSpec", "default_portfolio_spec", "PortfolioBacktest", "backtest_portfolio"]
