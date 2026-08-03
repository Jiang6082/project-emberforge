"""Walk-forward (sequential out-of-sample) evaluation.

A single locked test gives one out-of-sample number. Walk-forward instead slides
through history: after an initial in-sample warm-up, the remaining timeline is cut
into contiguous OOS windows, and the factor's information coefficient and
diagnostic Sharpe are measured on each. Reading those windows in order shows a
factor *decaying* (or holding up) through time, which a single split hides.

For a fixed declarative factor there is no parameter fitting, so expanding- and
rolling-train schemes coincide; the window framing is the natural hook for a
future variant that re-selects parameters at each ``train_end``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..analytics.ic import ic_series
from ..analytics.portfolio import long_short_returns
from ..compute import compute_factor
from ..data.schema import MarketData
from ..dsl.spec import FactorSpec

TRADING_DAYS = 252


def _sharpe(x) -> float:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / x.std(ddof=1) * np.sqrt(TRADING_DAYS))


@dataclass(frozen=True)
class WalkForwardWindow:
    index: int
    test_start: str
    test_end: str
    n_obs: int
    mean_ic: float
    sharpe: float


@dataclass
class WalkForwardResult:
    horizon: int
    n_windows: int
    windows: list[WalkForwardWindow]
    oos_mean_ic: float
    oos_ic_ir: float
    oos_sign_consistency: float   # fraction of windows sharing the OOS mean-IC sign
    worst_window_ic: float
    oos_sharpe: float = field(default=float("nan"))

    @property
    def stable(self) -> bool:
        return self.oos_sign_consistency >= 0.75 and self.oos_mean_ic == self.oos_mean_ic

    def summary(self) -> dict:
        return {
            "n_windows": self.n_windows,
            "oos_mean_ic": self.oos_mean_ic,
            "oos_ic_ir": self.oos_ic_ir,
            "oos_sign_consistency": self.oos_sign_consistency,
            "worst_window_ic": self.worst_window_ic,
            "oos_sharpe": self.oos_sharpe,
            "window_ics": [w.mean_ic for w in self.windows],
        }


def walk_forward(
    spec: FactorSpec,
    data: MarketData,
    n_windows: int = 5,
    min_train: float = 0.3,
    horizon: int = 1,
) -> WalkForwardResult:
    """Evaluate ``spec`` over ``n_windows`` sequential out-of-sample windows.

    ``min_train`` is the fraction of the (causally computed) IC series reserved as
    the initial in-sample warm-up; the remainder is split into equal OOS windows.
    """
    scores = compute_factor(spec, data)
    fwd = data.forward_returns(horizon)
    ic = ic_series(scores, fwd)
    ls = long_short_returns(scores, fwd, q=5)
    if ic.empty:
        return WalkForwardResult(horizon, 0, [], float("nan"), float("nan"), float("nan"), float("nan"))

    start = int(len(ic) * min_train)
    oos_ic = ic.iloc[start:]
    if len(oos_ic) < n_windows:
        n_windows = max(1, len(oos_ic))

    windows: list[WalkForwardWindow] = []
    for i, block in enumerate(np.array_split(oos_ic.index.to_numpy(), n_windows)):
        if len(block) == 0:
            continue
        block_ic = ic.loc[block]
        block_ls = ls.reindex(block).dropna()
        windows.append(WalkForwardWindow(
            index=i,
            test_start=str(block[0]),
            test_end=str(block[-1]),
            n_obs=int(len(block_ic)),
            mean_ic=float(block_ic.mean()),
            sharpe=_sharpe(block_ls.to_numpy()),
        ))

    win_ics = np.array([w.mean_ic for w in windows], dtype=float)
    oos_mean = float(np.nanmean(oos_ic.to_numpy()))
    oos_std = float(np.nanstd(oos_ic.to_numpy(), ddof=1)) if len(oos_ic) > 1 else float("nan")
    oos_ir = oos_mean / oos_std if oos_std and not np.isnan(oos_std) else float("nan")
    sign = np.sign(oos_mean) if oos_mean != 0 else 1
    sign_consistency = float(np.mean([np.sign(v) == sign for v in win_ics if v == v])) if len(win_ics) else float("nan")
    worst = float(np.nanmin(win_ics)) if len(win_ics) else float("nan")
    oos_sharpe = _sharpe(ls.reindex(oos_ic.index).dropna().to_numpy())

    return WalkForwardResult(
        horizon=horizon,
        n_windows=len(windows),
        windows=windows,
        oos_mean_ic=oos_mean,
        oos_ic_ir=oos_ir,
        oos_sign_consistency=sign_consistency,
        worst_window_ic=worst,
        oos_sharpe=oos_sharpe,
    )


__all__ = ["walk_forward", "WalkForwardResult", "WalkForwardWindow"]
