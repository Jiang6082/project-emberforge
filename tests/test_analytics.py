import numpy as np

from emberforge.analytics import evaluate_factor, ic_stats
from emberforge.analytics.portfolio import long_short_returns, quantile_buckets, turnover
from emberforge.compute import compute_factor
from emberforge.dsl import make_factor


def test_momentum_has_positive_ic(data):
    # The synthetic data embeds 20-bar momentum; the factor should have IC > 0.
    ev = evaluate_factor(make_factor("m", "ts_returns(close, 20)", expected_sign=1), data)
    assert ev.ic.mean_ic > 0
    assert ev.ic.n > 50


def test_noise_factor_has_near_zero_ic(data):
    ev = evaluate_factor(make_factor("n", "ts_returns(close, 1)"), data)
    assert abs(ev.ic.mean_ic) < abs(
        evaluate_factor(make_factor("m", "ts_returns(close, 20)"), data).ic.mean_ic
    )


def test_quantile_buckets_range(data):
    scores = compute_factor(make_factor("m", "ts_returns(close, 20)"), data)
    buckets = quantile_buckets(scores, q=5)
    vals = buckets.stack().unique()
    assert set(np.unique(vals[~np.isnan(vals)])).issubset({0, 1, 2, 3, 4})


def test_long_short_returns_length(data):
    scores = compute_factor(make_factor("m", "ts_returns(close, 20)"), data)
    ls = long_short_returns(scores, data.forward_returns(1), q=5)
    assert len(ls) > 0


def test_turnover_between_zero_and_one(data):
    scores = compute_factor(make_factor("m", "ts_returns(close, 20)"), data)
    t = turnover(scores, q=5)
    assert 0.0 <= t <= 1.0


def test_ic_tstat_sign_matches_mean(data):
    scores = compute_factor(make_factor("m", "ts_returns(close, 20)"), data)
    stats = ic_stats(scores, data.forward_returns(1))
    assert np.sign(stats.t_stat) == np.sign(stats.mean_ic)
