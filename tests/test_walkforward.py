import numpy as np

from emberforge.dsl import make_factor
from emberforge.research import walk_forward


def test_walk_forward_shape(data):
    r = walk_forward(make_factor("m", "ts_returns(close,20)"), data, n_windows=5)
    assert r.n_windows == 5
    assert len(r.windows) == 5
    # windows are contiguous and ordered
    assert all(a.test_end <= b.test_start for a, b in zip(r.windows, r.windows[1:]))


def test_walk_forward_momentum_is_positive_and_stable(data):
    # the embedded 20-bar momentum should show a positive, sign-consistent OOS IC
    r = walk_forward(make_factor("m", "ts_returns(close,20)", expected_sign=1), data, n_windows=5)
    assert r.oos_mean_ic > 0
    assert r.oos_sign_consistency >= 0.6
    assert not np.isnan(r.oos_sharpe)


def test_walk_forward_noise_less_stable(data):
    mom = walk_forward(make_factor("m", "ts_returns(close,20)"), data, n_windows=5)
    noise = walk_forward(make_factor("n", "ts_returns(close,1)"), data, n_windows=5)
    assert mom.oos_sign_consistency >= noise.oos_sign_consistency


def test_walk_forward_summary_keys(data):
    r = walk_forward(make_factor("m", "ts_returns(close,20)"), data)
    s = r.summary()
    assert {"oos_mean_ic", "oos_sign_consistency", "worst_window_ic", "window_ics"} <= s.keys()
    assert len(s["window_ics"]) == r.n_windows
