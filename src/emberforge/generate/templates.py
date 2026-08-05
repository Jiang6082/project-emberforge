"""Deterministic template generation.

Given a grammar of parametrized expression templates and a set of horizons, emit
validated :class:`FactorSpec` objects. Fully deterministic: same inputs, same
factors, in the same order — so a search family is reproducible.
"""

from __future__ import annotations

from ..dsl.spec import FactorSpec, make_factor

# name -> (expression template, expected_sign, family, hypothesis)
TEMPLATES = {
    "momentum": ("ts_returns(close,{w})", 1, "momentum",
                 "Recent winners keep winning over horizon {w}."),
    "reversal": ("neg(ts_returns(close,{w}))", 1, "reversal",
                 "Short-term {w}-bar moves overshoot and revert."),
    "volatility": ("neg(ts_std(ts_returns(close,1),{w}))", 1, "volatility",
                   "Lower {w}-bar realized volatility earns a premium."),
    "volume_trend": ("cs_rank(divide(volume,ts_mean(volume,{w})))", -1, "volume",
                     "Abnormal {w}-bar volume precedes mean reversion."),
    "price_trend": ("divide(close,ts_mean(close,{w}))", 1, "trend",
                    "Price above its {w}-bar average signals an uptrend."),
    "skewness": ("neg(ts_skew(ts_returns(close,1),{w}))", 1, "skewness",
                 "High positive {w}-bar return skew (lottery-like) underperforms."),
    "mean_reversion": ("neg(ts_zscore(close,{w}))", 1, "reversal",
                       "Price reverts toward its trailing {w}-bar mean."),
    "high_proximity": ("neg(ts_argmax(close,{w}))", 1, "trend",
                       "Proximity to the {w}-bar high predicts continuation."),
}


def generate_templates(horizons=(5, 10, 20, 60), which=None) -> list[FactorSpec]:
    which = which or list(TEMPLATES)
    factors: list[FactorSpec] = []
    for name in which:
        expr_tmpl, sign, family, hyp = TEMPLATES[name]
        for w in horizons:
            expr = expr_tmpl.format(w=w)
            try:
                factors.append(
                    make_factor(
                        factor_id=f"{name}_{w}",
                        expression=expr,
                        description=f"{name} template, window {w}",
                        economic_hypothesis=hyp.format(w=w),
                        expected_sign=sign,
                        generator="template",
                    )
                )
            except Exception:
                continue  # skip degenerate parameterizations
    return factors
