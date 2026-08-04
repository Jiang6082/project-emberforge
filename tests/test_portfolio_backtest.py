import numpy as np

from emberforge.analytics import (
    backtest_portfolio,
    default_portfolio_spec,
    evaluate_factor,
)
from emberforge.analytics.costs import CostModel
from emberforge.compute import compute_factor
from emberforge.dsl import make_factor


def test_backtest_produces_equity_stats(data):
    scores = compute_factor(make_factor("m", "ts_returns(close,20)"), data)
    pb = backtest_portfolio(scores, data.forward_returns(1), default_portfolio_spec())
    assert pb.n_periods > 50
    assert np.isfinite(pb.sharpe)
    assert pb.max_drawdown <= 0.0        # drawdown is non-positive
    assert 0.0 <= pb.hit_rate <= 1.0


def test_higher_cost_lowers_net_sharpe(data):
    scores = compute_factor(make_factor("m", "ts_returns(close,20)"), data)
    fwd = data.forward_returns(1)
    cheap = backtest_portfolio(scores, fwd, cost_model=CostModel(commission_bps=0.1, half_spread_bps=0.1))
    pricey = backtest_portfolio(scores, fwd, cost_model=CostModel(commission_bps=25, half_spread_bps=25))
    assert cheap.sharpe > pricey.sharpe


def test_spec_is_data_only_and_safe():
    spec = default_portfolio_spec().to_dict()
    assert spec["kind"] == "cross_sectional_quantile"
    # keys must be plain data (used inside a Geld-bound bundle) — no code-ish tokens
    forbidden = {"python", "pickle", "lambda", "exec", "eval", "callable",
                 "entrypoint", "shell", "script", "command", "reduce"}
    for k in spec:
        assert not (set(k.lower().replace("_", " ").split()) & forbidden)


def test_evaluation_exposes_portfolio_backtest(data):
    ev = evaluate_factor(make_factor("m", "ts_returns(close,20)", expected_sign=1), data)
    m = ev.to_metrics()
    assert m["portfolio_spec"]["quantiles"] == 5
    assert "sharpe" in m["portfolio_backtest"]
