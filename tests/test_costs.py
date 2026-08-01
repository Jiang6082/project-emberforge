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
