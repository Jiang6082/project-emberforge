import numpy as np

from emberforge.analytics import evaluate_factor
from emberforge.analytics.costs import CostModel, cost_sensitivity, estimate_capacity
from emberforge.dsl import make_factor


def test_cost_increases_with_participation():
    m = CostModel()
    low = m.per_period_cost(turnover=0.2, participation=0.001)
    high = m.per_period_cost(turnover=0.2, participation=0.05)
    assert high > low  # market impact grows with participation


def test_borrow_only_when_short():
    long_only = CostModel(has_short_leg=False).per_period_cost(0.0, 0.0)
    with_short = CostModel(has_short_leg=True).per_period_cost(0.0, 0.0)
    assert with_short > long_only
    assert long_only == 0.0


def test_capacity_zero_when_no_alpha():
    cap = estimate_capacity(gross_alpha_per_period=-0.001, adv_usd=1e7, turnover=0.2, n_positions=10)
    assert cap.capacity_usd == 0.0


def test_capacity_positive_and_finite_for_real_alpha():
    cap = estimate_capacity(gross_alpha_per_period=0.002, adv_usd=5e6, turnover=0.2, n_positions=10)
    assert cap.capacity_usd > 0
    assert np.isfinite(cap.capacity_usd)


def test_capacity_scales_with_liquidity():
    small = estimate_capacity(0.002, adv_usd=1e6, turnover=0.2, n_positions=10).capacity_usd
    large = estimate_capacity(0.002, adv_usd=1e8, turnover=0.2, n_positions=10).capacity_usd
    assert large > small  # more liquid names support more capital


def test_per_name_adv_least_liquid_dominates():
    # a portfolio that must trade one thin name caps out below its median ADV
    uniform = estimate_capacity(0.002, adv_usd=[5e6] * 10, turnover=0.2).capacity_usd
    with_thin = estimate_capacity(0.002, adv_usd=[5e6] * 9 + [1e5], turnover=0.2).capacity_usd
    assert with_thin < uniform


def test_higher_volatility_lowers_capacity():
    calm = estimate_capacity(0.002, adv_usd=[5e6] * 10, turnover=0.2, daily_vol=0.01).capacity_usd
    wild = estimate_capacity(0.002, adv_usd=[5e6] * 10, turnover=0.2, daily_vol=0.05).capacity_usd
    assert wild < calm  # more volatile names have higher impact


def test_scalar_adv_still_supported():
    cap = estimate_capacity(0.002, adv_usd=5e6, turnover=0.2, n_positions=10)
    assert cap.capacity_usd > 0


def test_cost_sensitivity_monotone_decreasing():
    sens = cost_sensitivity(gross_sharpe=2.0, gross_alpha_per_period=0.001,
                            ann_vol=0.1, turnover=0.3, cost_bps_levels=(0.0, 5.0, 20.0))
    vals = [sens[0.0], sens[5.0], sens[20.0]]
    assert vals[0] >= vals[1] >= vals[2]


def test_evaluation_exposes_capacity_and_cost_sensitivity(data):
    ev = evaluate_factor(make_factor("m", "ts_returns(close,20)", expected_sign=1), data)
    metrics = ev.to_metrics()
    assert "capacity_usd" in metrics
    assert "cost_sensitivity" in metrics and metrics["cost_sensitivity"]


def test_capacity_tracks_recent_liquidity_not_full_history(data):
    # a liquidity dry-up in the recent window should lower the capacity estimate,
    # even though the full-history median is unchanged.
    from copy import deepcopy

    from emberforge.data.schema import MarketData

    ev_full = evaluate_factor(make_factor("m", "ts_returns(close,20)"), data, adv_window=63)

    panels = {k: v.copy() for k, v in data.panels.items()}
    panels["volume"].iloc[-63:] *= 0.05  # recent volume collapses
    thin = MarketData(panels, data.metadata)
    ev_thin = evaluate_factor(make_factor("m", "ts_returns(close,20)"), thin, adv_window=63)

    assert ev_thin.capacity_usd < ev_full.capacity_usd


def test_portfolio_stats_uses_cost_model_for_net_sharpe(data):
    from emberforge.analytics import portfolio_stats
    from emberforge.analytics.costs import CostModel
    from emberforge.compute import compute_factor

    scores = compute_factor(make_factor("m", "ts_returns(close,20)"), data)
    fwd = data.forward_returns(1)
    cheap = portfolio_stats(scores, fwd, cost_model=CostModel(commission_bps=0.5, half_spread_bps=0.5))
    pricey = portfolio_stats(scores, fwd, cost_model=CostModel(commission_bps=20, half_spread_bps=20))
    # gross sharpe identical; higher modeled cost gives a lower net sharpe
    assert cheap.sharpe == pricey.sharpe
    assert cheap.sharpe_after_cost > pricey.sharpe_after_cost
