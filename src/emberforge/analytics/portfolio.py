"""Quantile analytics and *diagnostic* long-short portfolios.

These portfolios are diagnostics, NOT executable strategies. They exist to
summarize a factor's economic behavior and to produce the return series that
Deflated Sharpe / PBO consume. Emberforge never trades them.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def quantile_buckets(scores: pd.DataFrame, q: int = 5) -> pd.DataFrame:
    """Assign each (t, symbol) score to a quantile 0..q-1 within its row."""
    def _row(row: pd.Series) -> pd.Series:
        valid = row.dropna()
        if valid.nunique() < q:
            return pd.Series(np.nan, index=row.index)
        ranks = valid.rank(method="first")
        buckets = np.ceil(ranks / len(valid) * q) - 1
        return buckets.reindex(row.index)

    return scores.apply(_row, axis=1)


def quantile_returns(scores: pd.DataFrame, fwd_returns: pd.DataFrame, q: int = 5) -> pd.Series:
    """Mean forward return per quantile, averaged over time."""
    buckets = quantile_buckets(scores, q).reindex_like(fwd_returns)
    means = {}
    for b in range(q):
        mask = buckets == b
        means[b] = fwd_returns.where(mask).mean(axis=1).mean()
    return pd.Series(means, dtype=float)


def long_short_returns(scores: pd.DataFrame, fwd_returns: pd.DataFrame, q: int = 5) -> pd.Series:
    """Per-period return of a top-minus-bottom quantile diagnostic portfolio."""
    buckets = quantile_buckets(scores, q).reindex_like(fwd_returns)
    top = fwd_returns.where(buckets == q - 1).mean(axis=1)
    bottom = fwd_returns.where(buckets == 0).mean(axis=1)
    return (top - bottom).dropna()


def turnover(scores: pd.DataFrame, q: int = 5) -> float:
    """Average fraction of top-quantile names replaced period over period."""
    buckets = quantile_buckets(scores, q)
    top_sets = [set(row.index[row == q - 1]) for _, row in buckets.iterrows()]
    changes = []
    for prev, cur in zip(top_sets, top_sets[1:]):
        if prev:
            changes.append(len(prev - cur) / len(prev))
    return float(np.mean(changes)) if changes else float("nan")


def score_autocorr(scores: pd.DataFrame, lag: int = 1) -> float:
    a = scores.shift(lag)
    corrs = [scores.loc[t].corr(a.loc[t]) for t in scores.index if a.loc[t].notna().any()]
    corrs = [c for c in corrs if not np.isnan(c)]
    return float(np.mean(corrs)) if corrs else float("nan")


@dataclass(frozen=True)
class PortfolioStats:
    sharpe: float
    ann_return: float
    ann_vol: float
    turnover: float
    monotonicity: float           # Spearman rank of quantile -> return
    spread: float                 # top minus bottom mean return
    sharpe_after_cost: float


def _sharpe(returns: pd.Series) -> float:
    if returns.std(ddof=1) == 0 or len(returns) < 2:
        return float("nan")
    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def portfolio_stats(
    scores: pd.DataFrame,
    fwd_returns: pd.DataFrame,
    q: int = 5,
    cost_bps: float = 5.0,
) -> PortfolioStats:
    ls = long_short_returns(scores, fwd_returns, q)
    qret = quantile_returns(scores, fwd_returns, q)
    tvr = turnover(scores, q)
    cost_per_period = (cost_bps / 1e4) * (tvr if not np.isnan(tvr) else 0.0)
    ls_net = ls - cost_per_period
    mono = float(pd.Series(range(q)).corr(qret.reset_index(drop=True), method="spearman"))
    return PortfolioStats(
        sharpe=_sharpe(ls),
        ann_return=float(ls.mean() * TRADING_DAYS),
        ann_vol=float(ls.std(ddof=1) * np.sqrt(TRADING_DAYS)),
        turnover=tvr,
        monotonicity=mono,
        spread=float(qret.iloc[-1] - qret.iloc[0]),
        sharpe_after_cost=_sharpe(ls_net),
    )
