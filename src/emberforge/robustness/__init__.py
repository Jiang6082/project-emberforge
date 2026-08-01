"""Robustness, regime, and parameter-sensitivity analysis (Phase B).

A factor that only works in one stretch of history or at one exact parameter is
a red flag for overfitting. These tools quantify stability so the decision layer
can demand it — not just a good full-sample number.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..analytics.ic import ic_series
from ..compute import compute_factor
from ..data.schema import MarketData
from ..dsl.spec import FactorSpec, make_factor


@dataclass
class SubPeriodStability:
    fold_ics: list[float]
    mean_ic: float
    sign_consistency: float   # fraction of folds sharing the full-sample sign
    worst_fold_ic: float

    @property
    def stable(self) -> bool:
        return self.sign_consistency >= 0.75 and self.mean_ic != 0


def subperiod_stability(spec: FactorSpec, data: MarketData, k: int = 4, horizon: int = 1) -> SubPeriodStability:
    scores = compute_factor(spec, data)
    ic = ic_series(scores, data.forward_returns(horizon))
    if ic.empty:
        return SubPeriodStability([], float("nan"), float("nan"), float("nan"))
    folds = np.array_split(ic.values, k)
    fold_ics = [float(np.nanmean(f)) if len(f) else float("nan") for f in folds]
    overall = float(np.nanmean(ic.values))
    sign = np.sign(overall) if overall != 0 else 1
    consistent = np.mean([np.sign(f) == sign for f in fold_ics if f == f])
    return SubPeriodStability(fold_ics, overall, float(consistent), float(np.nanmin(fold_ics)))


@dataclass
class RegimeAnalysis:
    ic_by_regime: dict[str, float]

    @property
    def works_across_regimes(self) -> bool:
        vals = [v for v in self.ic_by_regime.values() if v == v]
        if len(vals) < 2:
            return False
        signs = {np.sign(v) for v in vals if v != 0}
        return len(signs) == 1


def _volatility_regime_labels(data: MarketData, window: int = 20) -> pd.Series:
    """Causal market-volatility regime label per timestamp (low/mid/high).

    Uses a trailing cross-sectional average of realized volatility, so the label
    at t depends only on data up to t.
    """
    rets = data.field("close").pct_change()
    market_vol = rets.rolling(window, min_periods=window).std().mean(axis=1)
    labels = pd.Series(index=market_vol.index, dtype=object)
    valid = market_vol.dropna()
    if valid.empty:
        return labels
    lo, hi = valid.quantile(1 / 3), valid.quantile(2 / 3)
    labels[market_vol <= lo] = "low_vol"
    labels[(market_vol > lo) & (market_vol <= hi)] = "mid_vol"
    labels[market_vol > hi] = "high_vol"
    return labels


def regime_analysis(spec: FactorSpec, data: MarketData, horizon: int = 1) -> RegimeAnalysis:
    scores = compute_factor(spec, data)
    ic = ic_series(scores, data.forward_returns(horizon))
    labels = _volatility_regime_labels(data).reindex(ic.index)
    out: dict[str, float] = {}
    for regime in ("low_vol", "mid_vol", "high_vol"):
        vals = ic[labels == regime]
        out[regime] = float(vals.mean()) if len(vals) else float("nan")
    return RegimeAnalysis(out)


@dataclass
class ParameterSensitivity:
    param_ics: dict[int, float]
    mean_ic: float
    ic_dispersion: float      # std of IC across neighboring params
    sign_consistency: float

    @property
    def robust(self) -> bool:
        return self.sign_consistency >= 0.75


def parameter_sensitivity(
    template: str,
    params: list[int],
    data: MarketData,
    horizon: int = 1,
    param_token: str = "{w}",
) -> ParameterSensitivity:
    """Vary one integer parameter in a template expression and measure IC stability.

    ``template`` contains ``param_token`` (default ``{w}``), e.g.
    ``"ts_returns(close,{w})"``.
    """
    ics: dict[int, float] = {}
    for p in params:
        expr = template.replace(param_token, str(p))
        try:
            spec = make_factor(f"param_{p}", expr)
            ic = ic_series(compute_factor(spec, data), data.forward_returns(horizon))
            ics[p] = float(ic.mean()) if len(ic) else float("nan")
        except Exception:
            ics[p] = float("nan")
    vals = np.array([v for v in ics.values() if v == v])
    if len(vals) == 0:
        return ParameterSensitivity(ics, float("nan"), float("nan"), float("nan"))
    mean = float(np.mean(vals))
    sign = np.sign(mean) if mean != 0 else 1
    consistency = float(np.mean([np.sign(v) == sign for v in vals]))
    return ParameterSensitivity(ics, mean, float(np.std(vals)), consistency)


@dataclass
class RobustnessReport:
    factor_id: str
    subperiod: SubPeriodStability
    regime: RegimeAnalysis
    sensitivity: ParameterSensitivity | None = None

    @property
    def passes(self) -> bool:
        ok = self.subperiod.stable and self.regime.works_across_regimes
        if self.sensitivity is not None:
            ok = ok and self.sensitivity.robust
        return ok

    def summary(self) -> dict:
        return {
            "subperiod_sign_consistency": self.subperiod.sign_consistency,
            "subperiod_worst_fold_ic": self.subperiod.worst_fold_ic,
            "regime_ic": self.regime.ic_by_regime,
            "works_across_regimes": self.regime.works_across_regimes,
            "param_sign_consistency": (self.sensitivity.sign_consistency if self.sensitivity else None),
            "passes_robustness": self.passes,
        }


def robustness_report(
    spec: FactorSpec,
    data: MarketData,
    horizon: int = 1,
    sensitivity_template: str | None = None,
    sensitivity_params: list[int] | None = None,
) -> RobustnessReport:
    sens = None
    if sensitivity_template and sensitivity_params:
        sens = parameter_sensitivity(sensitivity_template, sensitivity_params, data, horizon)
    return RobustnessReport(
        factor_id=spec.factor_id,
        subperiod=subperiod_stability(spec, data, horizon=horizon),
        regime=regime_analysis(spec, data, horizon=horizon),
        sensitivity=sens,
    )


__all__ = [
    "subperiod_stability", "SubPeriodStability",
    "regime_analysis", "RegimeAnalysis",
    "parameter_sensitivity", "ParameterSensitivity",
    "robustness_report", "RobustnessReport",
]
